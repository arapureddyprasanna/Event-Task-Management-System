from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from .models import EmailOTP, Profile


User = get_user_model()


class Phase3AuthTests(TestCase):
    login_url = '/api/auth/login/'
    refresh_url = '/api/auth/token/refresh/'
    logout_url = '/api/auth/logout/'
    protected_url = '/api/auth/protected/'
    forgot_url = '/api/auth/forgot-password/'
    reset_url = '/api/auth/reset-password/'
    password = 'Complex#Pass987!'
    new_password = 'Another#Strong987!'

    def setUp(self):
        self.client = APIClient()

    def create_user(self, username='member', email='member@example.com', **kwargs):
        user = User.objects.create_user(
            username=username,
            email=email,
            password=self.password,
            is_staff=kwargs.pop('is_staff', False),
            is_active=kwargs.pop('is_active', True),
        )
        Profile.objects.create(
            user=user,
            is_email_verified=kwargs.pop('verified', True),
            role=Profile.Role.ADMIN if user.is_staff else Profile.Role.USER,
        )
        return user

    def tokens_for(self, user):
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token), str(refresh)

    def issue_reset_otp(self, user):
        return EmailOTP.issue(
            user.email,
            user=user,
            purpose=EmailOTP.Purpose.RESET_PASSWORD,
        )

    def login(self, identifier='member'):
        return self.client.post(
            self.login_url,
            {'identifier': identifier, 'password': self.password},
            format='json',
        )

    def reset(self, user, code, password=None):
        password = password or self.new_password
        return self.client.post(
            self.reset_url,
            {
                'email': user.email,
                'otp': code,
                'new_password': password,
                'password_confirm': password,
            },
            format='json',
        )

    def authenticate_client(self, access):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

    def test_login_accepts_username_and_returns_server_user_metadata(self):
        user = self.create_user(is_staff=True)

        response = self.client.post(
            self.login_url,
            {'identifier': user.username, 'password': self.password, 'is_staff': False},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['access'])
        self.assertTrue(response.data['refresh'])
        self.assertEqual(response.data['user']['id'], user.pk)
        self.assertTrue(response.data['is_staff'])
        self.assertTrue(response.data['is_email_verified'])

    def test_login_accepts_case_insensitive_email(self):
        user = self.create_user(email='Member@Example.com')

        response = self.login('MEMBER@example.COM')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user']['id'], user.pk)

    def test_wrong_password_and_unknown_user_have_same_generic_401(self):
        self.create_user()
        wrong_password = self.client.post(
            self.login_url,
            {'identifier': 'member', 'password': 'wrong'},
            format='json',
        )
        unknown_user = self.client.post(
            self.login_url,
            {'identifier': 'unknown@example.com', 'password': 'wrong'},
            format='json',
        )

        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(unknown_user.status_code, 401)
        self.assertEqual(wrong_password.data, unknown_user.data)

    def test_unverified_login_returns_planned_error_code(self):
        self.create_user(verified=False)

        response = self.login()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'email_not_verified')

    def test_inactive_user_cannot_login(self):
        self.create_user(is_active=False)

        response = self.login()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data['detail'], 'Invalid username/email or password.')

    def test_jwt_lifetimes_and_rotation_configuration(self):
        self.assertEqual(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'], timedelta(minutes=15))
        self.assertEqual(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'], timedelta(days=7))
        self.assertTrue(settings.SIMPLE_JWT['ROTATE_REFRESH_TOKENS'])
        self.assertTrue(settings.SIMPLE_JWT['BLACKLIST_AFTER_ROTATION'])

    def test_refresh_rotates_and_blacklists_previous_token(self):
        user = self.create_user()
        _, old_refresh = self.tokens_for(user)

        response = self.client.post(
            self.refresh_url, {'refresh': old_refresh}, format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['access'])
        new_refresh = response.data['refresh']
        self.assertNotEqual(old_refresh, new_refresh)
        self.assertEqual(
            self.client.post(
                self.refresh_url, {'refresh': old_refresh}, format='json'
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                self.refresh_url, {'refresh': new_refresh}, format='json'
            ).status_code,
            200,
        )

    def test_refresh_rejects_inactive_user(self):
        user = self.create_user()
        _, refresh = self.tokens_for(user)
        User.objects.filter(pk=user.pk).update(is_active=False)

        response = self.client.post(
            self.refresh_url, {'refresh': refresh}, format='json'
        )

        self.assertEqual(response.status_code, 401)

    def test_refresh_rejects_unverified_user(self):
        user = self.create_user(verified=False)
        _, refresh = self.tokens_for(user)

        response = self.client.post(
            self.refresh_url, {'refresh': refresh}, format='json'
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'email_not_verified')

    def test_logout_requires_authentication(self):
        response = self.client.post(self.logout_url, {}, format='json')

        self.assertEqual(response.status_code, 401)

    def test_logout_blacklists_submitted_refresh_token(self):
        user = self.create_user()
        access, refresh = self.tokens_for(user)
        self.authenticate_client(access)

        response = self.client.post(
            self.logout_url, {'refresh': refresh}, format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.post(
                self.refresh_url, {'refresh': refresh}, format='json'
            ).status_code,
            401,
        )

    def test_protected_endpoint_requires_verified_active_jwt_user(self):
        self.assertEqual(self.client.get(self.protected_url).status_code, 401)

        verified_user = self.create_user()
        access, _ = self.tokens_for(verified_user)
        self.authenticate_client(access)
        self.assertEqual(self.client.get(self.protected_url).status_code, 200)

        unverified_user = self.create_user(
            username='unverified', email='unverified@example.com', verified=False
        )
        unverified_access, _ = self.tokens_for(unverified_user)
        self.authenticate_client(unverified_access)
        self.assertEqual(self.client.get(self.protected_url).status_code, 403)

        inactive_user = self.create_user(
            username='inactive', email='inactive@example.com'
        )
        inactive_access, _ = self.tokens_for(inactive_user)
        User.objects.filter(pk=inactive_user.pk).update(is_active=False)
        self.authenticate_client(inactive_access)
        self.assertEqual(self.client.get(self.protected_url).status_code, 401)

    def test_forgot_password_response_is_generic_and_creates_hashed_reset_otp(self):
        from unittest.mock import patch

        user = self.create_user()
        with patch('backend.accounts.auth_views.send_otp_email') as send_email:
            existing = self.client.post(
                self.forgot_url, {'email': user.email.upper()}, format='json'
            )
            unknown = self.client.post(
                self.forgot_url, {'email': 'missing@example.com'}, format='json'
            )

        self.assertEqual(existing.status_code, 200)
        self.assertEqual(existing.data, unknown.data)
        self.assertNotIn('otp', existing.data)
        otp = EmailOTP.objects.get(user=user)
        self.assertEqual(otp.purpose, EmailOTP.Purpose.RESET_PASSWORD)
        self.assertNotEqual(otp.code_hash, send_email.call_args.args[1])
        send_email.assert_called_once_with(user.email, send_email.call_args.args[1])

    def test_forgot_password_unknown_email_does_not_send(self):
        from unittest.mock import patch

        with patch('backend.accounts.auth_views.send_otp_email') as send_email:
            response = self.client.post(
                self.forgot_url, {'email': 'missing@example.com'}, format='json'
            )

        self.assertEqual(response.status_code, 200)
        send_email.assert_not_called()
        self.assertEqual(EmailOTP.objects.count(), 0)

    def test_reset_password_wrong_otp_records_attempt_and_rejects(self):
        user = self.create_user()
        otp, _ = self.issue_reset_otp(user)

        response = self.reset(user, '000000')

        self.assertEqual(response.status_code, 400)
        otp.refresh_from_db()
        self.assertEqual(otp.verification_attempts, 1)
        self.assertFalse(otp.verified_at)

    def test_reset_password_rejects_expired_otp(self):
        user = self.create_user()
        otp, code = self.issue_reset_otp(user)
        otp.expires_at = timezone.now() - timedelta(seconds=1)
        otp.save(update_fields=('expires_at', 'updated_at'))

        response = self.reset(user, code)

        self.assertEqual(response.status_code, 400)
        otp.refresh_from_db()
        self.assertFalse(otp.verified_at)
        self.assertEqual(otp.verification_attempts, 0)

    def test_reset_password_rejects_verification_purpose_otp(self):
        user = self.create_user()
        otp, code = EmailOTP.issue(
            user.email, user=user, purpose=EmailOTP.Purpose.VERIFY_EMAIL
        )

        response = self.reset(user, code)

        self.assertEqual(response.status_code, 400)
        otp.refresh_from_db()
        self.assertFalse(otp.verified_at)

    def test_invalid_new_password_does_not_consume_otp(self):
        user = self.create_user()
        otp, code = self.issue_reset_otp(user)

        response = self.reset(user, code, password='short')

        self.assertEqual(response.status_code, 400)
        otp.refresh_from_db()
        self.assertFalse(otp.verified_at)
        self.assertEqual(otp.verification_attempts, 0)

    def test_successful_reset_is_single_use_and_revokes_user_tokens(self):
        user = self.create_user()
        access, first_refresh = self.tokens_for(user)
        rotated = self.client.post(
            self.refresh_url, {'refresh': first_refresh}, format='json'
        )
        self.assertEqual(rotated.status_code, 200)
        second_access = rotated.data['access']
        second_refresh = rotated.data['refresh']
        otp, code = self.issue_reset_otp(user)

        response = self.reset(user, code)

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password(self.new_password))
        otp.refresh_from_db()
        self.assertTrue(otp.verified_at)
        self.assertEqual(
            self.reset(user, code).status_code,
            400,
        )
        self.authenticate_client(access)
        self.assertEqual(self.client.get(self.protected_url).status_code, 401)
        self.authenticate_client(second_access)
        self.assertEqual(self.client.get(self.protected_url).status_code, 401)
        for refresh in (first_refresh, second_refresh):
            self.assertEqual(
                self.client.post(
                    self.refresh_url, {'refresh': refresh}, format='json'
                ).status_code,
                401,
            )

    def test_password_change_blacklists_refresh_and_revokes_access(self):
        user = self.create_user()
        access, refresh = self.tokens_for(user)

        user.set_password(self.new_password)
        user.save(update_fields=('password',))

        self.authenticate_client(access)
        self.assertEqual(self.client.get(self.protected_url).status_code, 401)
        self.assertEqual(
            self.client.post(
                self.refresh_url, {'refresh': refresh}, format='json'
            ).status_code,
            401,
        )

    def test_admin_deactivation_blacklists_refresh_tokens(self):
        user = self.create_user()
        _, refresh = self.tokens_for(user)

        user.is_active = False
        user.save(update_fields=('is_active',))

        self.assertEqual(
            self.client.post(
                self.refresh_url, {'refresh': refresh}, format='json'
            ).status_code,
            401,
        )
