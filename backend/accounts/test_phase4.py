from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import EmailOTP, Profile
from .services.email import EmailDeliveryError


User = get_user_model()


class Phase4ProfileAndPasswordTests(TestCase):
    profile_url = '/api/auth/profile/'
    password_url = '/api/auth/change-password/'
    password = 'Complex#Pass987!'
    new_password = 'Fresh#Password234!'

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user()
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        self.refresh_token = str(refresh)
        self.authenticate(self.access_token)

    def create_user(self, username='member', email='member@example.com', **kwargs):
        user = User.objects.create_user(
            username=username,
            email=email,
            password=kwargs.pop('password', self.password),
            is_staff=kwargs.pop('is_staff', False),
            is_active=kwargs.pop('is_active', True),
        )
        Profile.objects.create(
            user=user,
            is_email_verified=kwargs.pop('verified', True),
            role=Profile.Role.ADMIN if user.is_staff else Profile.Role.USER,
        )
        return user

    def authenticate(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_profile_get_exposes_safe_user_and_verification_data(self):
        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.user.pk)
        self.assertEqual(response.data['email'], self.user.email)
        self.assertTrue(response.data['is_email_verified'])
        self.assertFalse({'password', 'role', 'groups', 'user_permissions'} & set(response.data))

    def test_profile_requires_authentication_and_verified_account(self):
        self.client.credentials()
        self.assertEqual(self.client.get(self.profile_url).status_code, 401)

        unverified = self.create_user(
            'unverified', 'unverified@example.com', verified=False
        )
        self.authenticate(str(RefreshToken.for_user(unverified).access_token))
        self.assertEqual(self.client.get(self.profile_url).status_code, 403)

    def test_profile_patch_updates_only_permitted_fields(self):
        response = self.client.patch(
            self.profile_url,
            {'first_name': 'Updated', 'last_name': 'Name'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.last_name), ('Updated', 'Name'))
        self.assertTrue(self.user.profile.is_email_verified)

    def test_profile_cannot_change_staff_or_verification_status(self):
        response = self.client.patch(
            self.profile_url,
            {'first_name': 'Ignored', 'is_staff': True, 'is_email_verified': True},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertEqual(self.user.first_name, '')
        self.assertTrue(self.user.profile.is_email_verified)

    def test_profile_rejects_case_insensitive_duplicate_email(self):
        self.create_user('other', 'taken@example.com')

        response = self.client.patch(
            self.profile_url, {'email': 'TAKEN@example.com'}, format='json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'member@example.com')

    @patch('backend.accounts.services.profiles.send_otp_email')
    def test_email_change_sends_hashed_otp_to_new_address_and_requires_verification(
        self, send_email
    ):
        response = self.client.patch(
            self.profile_url, {'email': 'NewAddress@example.com'}, format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['email'], 'newaddress@example.com')
        self.assertFalse(response.data['is_email_verified'])
        otp = EmailOTP.objects.get(user=self.user, purpose=EmailOTP.Purpose.VERIFY_EMAIL)
        send_email.assert_called_once_with('newaddress@example.com', send_email.call_args.args[1])
        self.assertNotEqual(otp.code_hash, send_email.call_args.args[1])

        verify = self.client.post(
            '/api/auth/verify-email/',
            {'email': 'newaddress@example.com', 'otp': send_email.call_args.args[1]},
            format='json',
        )
        self.assertEqual(verify.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.is_email_verified)

    @patch(
        'backend.accounts.services.profiles.send_otp_email',
        side_effect=EmailDeliveryError('failed'),
    )
    def test_email_change_delivery_failure_rolls_back_email_and_otp(self, _send_email):
        response = self.client.patch(
            self.profile_url, {'email': 'new@example.com'}, format='json'
        )

        self.assertEqual(response.status_code, 503)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'member@example.com')
        self.assertTrue(self.user.profile.is_email_verified)
        self.assertEqual(EmailOTP.objects.filter(user=self.user).count(), 0)

    def test_password_change_rejects_wrong_current_password(self):
        response = self.client.post(
            self.password_url,
            {
                'current_password': 'incorrect',
                'new_password': self.new_password,
                'password_confirm': self.new_password,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_password_change_rejects_mismatch_and_django_weak_passwords(self):
        mismatch = self.client.post(
            self.password_url,
            {
                'current_password': self.password,
                'new_password': self.new_password,
                'password_confirm': 'Different#Password234!',
            },
            format='json',
        )
        weak = self.client.post(
            self.password_url,
            {
                'current_password': self.password,
                'new_password': 'password',
                'password_confirm': 'password',
            },
            format='json',
        )

        self.assertEqual(mismatch.status_code, 400)
        self.assertIn('password_confirm', mismatch.data)
        self.assertEqual(weak.status_code, 400)
        self.assertIn('new_password', weak.data)

    def test_password_change_revokes_existing_access_and_refresh_tokens(self):
        response = self.client.post(
            self.password_url,
            {
                'current_password': self.password,
                'new_password': self.new_password,
                'password_confirm': self.new_password,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/auth/protected/').status_code, 401)
        with self.assertRaises(TokenError):
            RefreshToken(self.refresh_token)
        login = self.client.post(
            '/api/auth/login/',
            {'identifier': self.user.username, 'password': self.new_password},
            format='json',
        )
        self.assertEqual(login.status_code, 200)


class Phase4AdminUserManagementTests(TestCase):
    list_url = '/api/users/'
    password = 'Complex#Pass987!'

    def setUp(self):
        self.client = APIClient()
        self.admin = self.create_user('admin', 'admin@example.com', is_staff=True)
        self.regular = self.create_user('member', 'member@example.com')
        self.admin_access, _ = self.tokens_for(self.admin)
        self.regular_access, self.regular_refresh = self.tokens_for(self.regular)

    def create_user(self, username, email, *, is_staff=False, is_active=True, verified=True):
        user = User.objects.create_user(
            username=username,
            email=email,
            password=self.password,
            is_staff=is_staff,
            is_active=is_active,
        )
        Profile.objects.create(
            user=user,
            is_email_verified=verified,
            role=Profile.Role.ADMIN if is_staff else Profile.Role.USER,
        )
        return user

    @staticmethod
    def tokens_for(user):
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token), str(refresh)

    def authenticate(self, access_token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

    def test_admin_list_is_staff_only_paginated_and_contains_safe_fields(self):
        self.authenticate(self.regular_access)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)

        self.authenticate(self.admin_access)
        for index in range(22):
            self.create_user(f'person{index}', f'person{index}@example.com')
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 24)
        self.assertEqual(len(response.data['results']), 20)
        self.assertIsNotNone(response.data['next'])
        self.assertNotIn('password', response.data['results'][0])
        self.assertNotIn('user_permissions', response.data['results'][0])

    def test_admin_list_search_and_boolean_filters(self):
        inactive = self.create_user(
            'inactiveperson', 'inactive@example.com', is_active=False, verified=False
        )
        staff = self.create_user('staffperson', 'staff@example.com', is_staff=True)
        self.authenticate(self.admin_access)

        search = self.client.get(self.list_url, {'search': 'inactiveperson'})
        filters = self.client.get(
            self.list_url,
            {'is_active': 'false', 'is_staff': 'false', 'is_email_verified': 'false'},
        )
        invalid_filter = self.client.get(self.list_url, {'is_active': 'sometimes'})

        self.assertEqual(search.status_code, 200)
        self.assertEqual([row['id'] for row in search.data['results']], [inactive.pk])
        self.assertEqual(filters.status_code, 200)
        self.assertEqual([row['id'] for row in filters.data['results']], [inactive.pk])
        self.assertEqual(invalid_filter.status_code, 400)
        self.assertTrue(staff.is_staff)

    def test_admin_detail_is_safe_and_non_staff_is_forbidden(self):
        self.authenticate(self.regular_access)
        self.assertEqual(
            self.client.get(f'{self.list_url}{self.regular.pk}/').status_code, 403
        )

        self.authenticate(self.admin_access)
        response = self.client.get(f'{self.list_url}{self.regular.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.regular.pk)
        self.assertIn('is_active', response.data)
        self.assertNotIn('password', response.data)

    def test_activation_endpoint_only_accepts_is_active(self):
        self.authenticate(self.admin_access)
        forbidden = self.client.patch(
            f'{self.list_url}{self.regular.pk}/activation/',
            {'is_active': True, 'is_staff': True},
            format='json',
        )
        self.assertEqual(forbidden.status_code, 400)
        self.regular.refresh_from_db()
        self.assertFalse(self.regular.is_staff)

    def test_deactivation_blacklists_refresh_and_blocks_user_then_reactivation_allows_login(self):
        self.authenticate(self.admin_access)
        deactivated = self.client.patch(
            f'{self.list_url}{self.regular.pk}/activation/',
            {'is_active': False},
            format='json',
        )
        self.assertEqual(deactivated.status_code, 200)
        self.assertFalse(deactivated.data['is_active'])

        self.authenticate(self.regular_access)
        self.assertEqual(self.client.get('/api/auth/protected/').status_code, 401)
        with self.assertRaises(TokenError):
            RefreshToken(self.regular_refresh)
        denied_login = self.client.post(
            '/api/auth/login/',
            {'identifier': self.regular.username, 'password': self.password},
            format='json',
        )
        self.assertEqual(denied_login.status_code, 401)

        self.authenticate(self.admin_access)
        reactivated = self.client.patch(
            f'{self.list_url}{self.regular.pk}/activation/',
            {'is_active': True},
            format='json',
        )
        self.assertEqual(reactivated.status_code, 200)
        allowed_login = self.client.post(
            '/api/auth/login/',
            {'identifier': self.regular.username, 'password': self.password},
            format='json',
        )
        self.assertEqual(allowed_login.status_code, 200)

    def test_reactivation_does_not_bypass_email_verification(self):
        unverified = self.create_user(
            'notverified', 'notverified@example.com', is_active=False, verified=False
        )
        self.authenticate(self.admin_access)
        response = self.client.patch(
            f'{self.list_url}{unverified.pk}/activation/',
            {'is_active': True},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        login = self.client.post(
            '/api/auth/login/',
            {'identifier': unverified.username, 'password': self.password},
            format='json',
        )
        self.assertEqual(login.status_code, 403)
        self.assertEqual(login.data['code'], 'email_not_verified')
