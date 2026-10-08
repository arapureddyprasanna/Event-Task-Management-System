from datetime import timedelta
import re
import smtplib

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from unittest.mock import patch
from rest_framework.test import APIClient

from .services.email import EmailDeliveryError, send_otp_email

from .models import EmailOTP, Profile


User = get_user_model()


class EmailServiceTests(TestCase):
    @override_settings(DEFAULT_FROM_EMAIL='notifications@example.com')
    @patch('backend.accounts.services.email.send_mail', return_value=1)
    def test_send_otp_email_uses_recipient_address(self, mocked_send_mail):
        recipient = 'registrant@example.net'

        send_otp_email(recipient, '123456')

        mocked_send_mail.assert_called_once()
        self.assertEqual(mocked_send_mail.call_args.args[2], 'notifications@example.com')
        self.assertEqual(mocked_send_mail.call_args.args[3], [recipient])

    @override_settings(
        DEBUG=True,
        MAILERS={'default': {'OPTIONS': {'password': 'resend-secret-test-value'}}},
    )
    @patch(
        'backend.accounts.services.email.send_mail',
        side_effect=RuntimeError(
            'Resend rejected resend-secret-test-value for user@example.net with OTP 123456'
        ),
    )
    def test_development_email_error_log_redacts_secrets_and_otp(
        self, mocked_send_mail
    ):
        with self.assertLogs('django', level='ERROR') as captured:
            with self.assertRaises(EmailDeliveryError):
                send_otp_email('user@example.net', '123456')

        message = '\n'.join(captured.output)
        self.assertIn('RuntimeError', message)
        self.assertIn('Resend rejected', message)
        self.assertNotIn('resend-secret-test-value', message)
        self.assertNotIn('123456', message)
        self.assertNotIn('user@example.net', message)
        mocked_send_mail.assert_called_once()


class ProfileTests(TestCase):
    def test_profile_defaults_to_regular_user(self):
        user = User.objects.create_user(username='member', password='test-password')
        profile = Profile.objects.create(user=user)

        self.assertEqual(profile.role, Profile.Role.USER)

    def test_email_verification_defaults_to_false(self):
        user = User.objects.create_user(username='unverified', password='test-password')
        profile = Profile.objects.create(user=user)

        self.assertFalse(profile.is_email_verified)

    def test_admin_role_requires_staff_account(self):
        user = User.objects.create_user(username='member', password='test-password')

        with self.assertRaises(ValidationError):
            Profile.objects.create(user=user, role=Profile.Role.ADMIN)

        user.is_staff = True
        user.save(update_fields=('is_staff',))
        profile = Profile.objects.create(user=user, role=Profile.Role.ADMIN)
        self.assertEqual(profile.role, Profile.Role.ADMIN)


class EmailOTPTests(TestCase):
    def test_purpose_is_stored(self):
        otp, _ = EmailOTP.issue(
            'person@example.com', purpose=EmailOTP.Purpose.RESET_PASSWORD
        )

        self.assertEqual(otp.purpose, EmailOTP.Purpose.RESET_PASSWORD)

    def test_issue_hashes_code_and_verification_consumes_it(self):
        otp, code = EmailOTP.issue(' PERSON@example.com ')

        self.assertNotEqual(otp.code_hash, code)
        self.assertTrue(otp.verify(code))
        self.assertIsNotNone(otp.verified_at)
        self.assertFalse(otp.verify(code))

    def test_invalid_attempts_are_counted_and_capped(self):
        otp, _ = EmailOTP.issue('person@example.com')

        for _ in range(EmailOTP.MAX_VERIFY_ATTEMPTS):
            self.assertFalse(otp.verify('000000'))

        self.assertEqual(otp.verification_attempts, EmailOTP.MAX_VERIFY_ATTEMPTS)
        self.assertFalse(otp.verify('000000'))

    def test_expired_code_cannot_be_verified(self):
        otp, code = EmailOTP.issue('person@example.com')
        otp.expires_at = timezone.now() - timedelta(seconds=1)
        otp.save(update_fields=('expires_at', 'updated_at'))

        self.assertFalse(otp.verify(code))

    def test_resend_rotates_code_and_enforces_limit(self):
        otp, first_code = EmailOTP.issue('person@example.com')
        new_code = otp.resend()

        self.assertNotEqual(first_code, new_code)
        self.assertFalse(otp.verify(first_code))
        self.assertTrue(otp.verify(new_code))

        for _ in range(EmailOTP.MAX_RESENDS - 1):
            other, _ = EmailOTP.issue(f'{_ + 1}@example.com')
            for _attempt in range(EmailOTP.MAX_RESENDS):
                other.resend()
            with self.assertRaises(ValidationError):
                other.resend()


class RegistrationAPITests(TestCase):
    register_url = '/api/auth/register/'
    verify_url = '/api/auth/verify-email/'
    resend_url = '/api/auth/resend-otp/'

    def setUp(self):
        self.client = APIClient()

    @staticmethod
    def registration_payload(username='newmember', email='new@example.com'):
        return {
            'username': username,
            'email': email,
            'password': 'Complex#Pass987!',
            'password_confirm': 'Complex#Pass987!',
            'first_name': 'New',
            'last_name': 'Member',
        }

    def register(self, username='newmember', email='new@example.com'):
        send_patch = patch('backend.accounts.views.send_otp_email')
        mocked_send = send_patch.start()
        self.addCleanup(send_patch.stop)
        response = self.client.post(
            self.register_url,
            self.registration_payload(username=username, email=email),
            format='json',
        )
        return response, mocked_send

    def test_successful_registration_creates_user_profile_and_hashed_verify_otp(self):
        response, mocked_send = self.register()

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username='newmember')
        self.assertTrue(user.check_password('Complex#Pass987!'))
        self.assertNotEqual(user.password, 'Complex#Pass987!')
        self.assertFalse(user.profile.is_email_verified)
        self.assertTrue(user.profile.registration_demo_access)
        otp = EmailOTP.objects.get(user=user)
        self.assertEqual(otp.purpose, EmailOTP.Purpose.VERIFY_EMAIL)
        self.assertNotEqual(otp.code_hash, mocked_send.call_args.args[1])
        mocked_send.assert_called_once_with('new@example.com', mocked_send.call_args.args[1])

    @override_settings(
        MAILERS={
            'default': {
                'BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
            },
        }
    )
    def test_registration_delivers_generated_otp_through_email_service(self):
        response = self.client.post(
            self.register_url,
            self.registration_payload(),
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        user = User.objects.get(username='newmember')
        self.assertEqual(mail.outbox[0].to, [user.email])
        self.assertNotEqual(mail.outbox[0].to, [mail.outbox[0].from_email])
        otp = EmailOTP.objects.get(email='new@example.com')
        code_match = re.search(r'\b\d{6}\b', mail.outbox[0].body)
        self.assertIsNotNone(code_match)
        self.assertTrue(otp.verify(code_match.group()))

    def test_invalid_registration_data_returns_validation_errors(self):
        payload = self.registration_payload()
        payload['email'] = 'not-an-email'

        response = self.client.post(self.register_url, payload, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.data)
        self.assertEqual(User.objects.count(), 0)

    def test_password_mismatch_returns_validation_error(self):
        payload = self.registration_payload()
        payload['password_confirm'] = 'different-password'

        response = self.client.post(self.register_url, payload, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('password_confirm', response.data)

    def test_duplicate_email_and_username_are_rejected(self):
        response, _ = self.register()
        self.assertEqual(response.status_code, 201)

        duplicate_email = self.client.post(
            self.register_url,
            self.registration_payload(username='different', email='NEW@example.com'),
            format='json',
        )
        duplicate_username = self.client.post(
            self.register_url,
            self.registration_payload(username='NEWMEMBER', email='other@example.com'),
            format='json',
        )

        self.assertEqual(duplicate_email.status_code, 400)
        self.assertIn('email', duplicate_email.data)
        self.assertEqual(duplicate_username.status_code, 400)
        self.assertIn('username', duplicate_username.data)
        self.assertEqual(User.objects.count(), 1)

    def test_registration_email_failure_rolls_back_new_account(self):
        with patch(
            'backend.accounts.views.send_otp_email',
            side_effect=EmailDeliveryError('failed'),
        ):
            response = self.client.post(
                self.register_url, self.registration_payload(), format='json'
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(EmailOTP.objects.count(), 0)

    @override_settings(DEBUG=True)
    def test_unverified_development_sender_domain_does_not_fail_registration(self):
        def fail_with_unverified_sender(*args, **kwargs):
            try:
                raise smtplib.SMTPDataError(
                    550, b'The gmail.com domain is not verified.'
                )
            except smtplib.SMTPDataError as cause:
                raise EmailDeliveryError(
                    'Verification email could not be sent.'
                ) from cause

        with patch(
            'backend.accounts.views.send_otp_email',
            side_effect=fail_with_unverified_sender,
        ):
            response = self.client.post(
                self.register_url, self.registration_payload(), format='json'
            )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['email_delivery_deferred'])
        user = User.objects.get(username='newmember')
        self.assertTrue(user.profile.registration_demo_access)
        self.assertFalse(user.profile.is_email_verified)
        self.assertEqual(
            EmailOTP.objects.get(user=user).purpose, EmailOTP.Purpose.VERIFY_EMAIL
        )

    @override_settings(DEBUG=True)
    def test_other_smtp_550_failures_still_fail_registration(self):
        def fail_for_other_reason(*args, **kwargs):
            try:
                raise smtplib.SMTPDataError(550, b'Mailbox unavailable.')
            except smtplib.SMTPDataError as cause:
                raise EmailDeliveryError(
                    'Verification email could not be sent.'
                ) from cause

        with patch(
            'backend.accounts.views.send_otp_email',
            side_effect=fail_for_other_reason,
        ):
            response = self.client.post(
                self.register_url, self.registration_payload(), format='json'
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(EmailOTP.objects.count(), 0)

    def test_successful_email_verification_marks_profile_verified(self):
        response, mocked_send = self.register()
        self.assertEqual(response.status_code, 201)
        code = mocked_send.call_args.args[1]

        response = self.client.post(
            self.verify_url,
            {'email': 'NEW@example.com', 'otp': code},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username='newmember')
        self.assertTrue(user.profile.is_email_verified)
        self.assertFalse(user.profile.registration_demo_access)
        self.assertIsNotNone(EmailOTP.objects.get(user=user).verified_at)

    def test_registration_demo_account_can_login_and_access_protected_features(self):
        self.register()

        login = self.client.post(
            '/api/auth/login/',
            {'identifier': 'newmember', 'password': 'Complex#Pass987!'},
            format='json',
        )

        self.assertEqual(login.status_code, 200)
        self.assertFalse(login.data['is_email_verified'])
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}"
        )
        self.assertEqual(self.client.get('/api/auth/protected/').status_code, 200)

        refreshed = self.client.post(
            '/api/auth/token/refresh/',
            {'refresh': login.data['refresh']},
            format='json',
        )
        self.assertEqual(refreshed.status_code, 200)

    def test_invalid_otp_increments_attempts(self):
        self.register()
        otp = EmailOTP.objects.get(email='new@example.com')

        response = self.client.post(
            self.verify_url, {'email': 'new@example.com', 'otp': '000000'}, format='json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(EmailOTP.objects.get(pk=otp.pk).verification_attempts, 1)

    def test_expired_otp_returns_expired_error(self):
        self.register()
        otp = EmailOTP.objects.get(email='new@example.com')
        otp.expires_at = timezone.now() - timedelta(seconds=1)
        otp.save(update_fields=('expires_at', 'updated_at'))

        response = self.client.post(
            self.verify_url, {'email': 'new@example.com', 'otp': '123456'}, format='json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('expired', response.data['detail'].lower())
        self.assertEqual(EmailOTP.objects.get(pk=otp.pk).verification_attempts, 0)

    def test_verification_attempt_limit_returns_too_many_requests(self):
        self.register()
        otp = EmailOTP.objects.get(email='new@example.com')
        otp.verification_attempts = EmailOTP.MAX_VERIFY_ATTEMPTS
        otp.save(update_fields=('verification_attempts', 'updated_at'))

        response = self.client.post(
            self.verify_url, {'email': 'new@example.com', 'otp': '123456'}, format='json'
        )

        self.assertEqual(response.status_code, 429)
        self.assertIn('attempt limit', response.data['detail'].lower())

    def test_already_verified_email_returns_error(self):
        self.register()
        user = User.objects.get(username='newmember')
        user.profile.is_email_verified = True
        user.profile.save(update_fields=('is_email_verified', 'updated_at'))

        response = self.client.post(
            self.verify_url, {'email': 'new@example.com', 'otp': '123456'}, format='json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('already verified', response.data['detail'].lower())

    def test_resend_rotates_hashed_otp_and_sends_new_code(self):
        self.register()
        otp = EmailOTP.objects.get(email='new@example.com')
        old_hash = otp.code_hash
        otp.verification_attempts = 2
        otp.save(update_fields=('verification_attempts', 'updated_at'))
        with patch('backend.accounts.views.send_otp_email') as mocked_send:
            response = self.client.post(
                self.resend_url, {'email': 'NEW@example.com'}, format='json'
            )

        self.assertEqual(response.status_code, 200)
        otp.refresh_from_db()
        self.assertEqual(otp.resend_attempts, 1)
        self.assertEqual(otp.verification_attempts, 0)
        self.assertNotEqual(otp.code_hash, old_hash)
        self.assertNotEqual(otp.code_hash, mocked_send.call_args.args[1])
        mocked_send.assert_called_once_with('new@example.com', mocked_send.call_args.args[1])

    def test_resend_limit_returns_too_many_requests(self):
        self.register()
        otp = EmailOTP.objects.get(email='new@example.com')
        otp.resend_attempts = EmailOTP.MAX_RESENDS
        otp.save(update_fields=('resend_attempts', 'updated_at'))
        with patch('backend.accounts.views.send_otp_email') as mocked_send:
            response = self.client.post(
                self.resend_url, {'email': 'new@example.com'}, format='json'
            )

        self.assertEqual(response.status_code, 429)
        self.assertIn('resend', response.data['detail'].lower())
        mocked_send.assert_not_called()

    def test_resend_email_failure_does_not_rotate_stored_code(self):
        self.register()
        otp = EmailOTP.objects.get(email='new@example.com')
        original_hash = otp.code_hash
        with patch(
            'backend.accounts.views.send_otp_email',
            side_effect=EmailDeliveryError('failed'),
        ):
            response = self.client.post(
                self.resend_url, {'email': 'new@example.com'}, format='json'
            )

        self.assertEqual(response.status_code, 503)
        otp.refresh_from_db()
        self.assertEqual(otp.code_hash, original_hash)
        self.assertEqual(otp.resend_attempts, 0)
