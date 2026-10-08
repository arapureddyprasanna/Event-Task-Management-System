from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import patch
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import EmailOTP, Profile


class DirectAdminCreationTests(TestCase):
    url = '/api/auth/admin/create/'
    payload = {
        'username': 'newadmin', 'email': 'newadmin@example.com',
        'password': 'Safe-Admin-Pass-492!', 'password_confirm': 'Safe-Admin-Pass-492!',
        'first_name': 'New', 'last_name': 'Admin',
    }

    def setUp(self):
        self.client = APIClient()
        self.User = get_user_model()
        self.superuser = self.User.objects.create_superuser(
            username='root', email='root@example.com', password='Root-Pass-492!'
        )
        Profile.objects.create(user=self.superuser, is_email_verified=True)

    def test_anonymous_and_non_superusers_cannot_create_admin(self):
        self.assertEqual(self.client.post(self.url, self.payload, format='json').status_code, 401)
        for username, staff in (('member', False), ('staff', True)):
            user = self.User.objects.create_user(
                username=username, email=f'{username}@example.com', password='User-Pass-492!',
                is_staff=staff,
            )
            Profile.objects.create(user=user, role=Profile.Role.ADMIN if staff else Profile.Role.USER,
                                   is_email_verified=True)
            self.client.force_authenticate(user)
            self.assertEqual(self.client.post(self.url, self.payload, format='json').status_code, 403)

    @patch('backend.accounts.views.send_otp_email')
    def test_superuser_creates_staff_admin_with_verification_required_and_safe_response(self, send_email):
        self.client.force_authenticate(self.superuser)
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertNotIn('password', response.data)
        self.assertNotIn('access', response.data)
        self.assertNotIn('refresh', response.data)
        created = self.User.objects.get(username='newadmin')
        self.assertTrue(created.is_staff)
        self.assertFalse(created.is_superuser)
        self.assertEqual(created.profile.role, Profile.Role.ADMIN)
        self.assertFalse(created.profile.is_email_verified)
        self.assertFalse(created.profile.registration_demo_access)
        self.assertTrue(EmailOTP.objects.filter(user=created, purpose=EmailOTP.Purpose.VERIFY_EMAIL).exists())
        self.client.force_authenticate(user=None)
        self.client.credentials()
        login = self.client.post('/api/auth/login/', {
            'identifier': 'newadmin', 'password': self.payload['password'],
        }, format='json')
        self.assertEqual(login.status_code, 403)
        self.assertEqual(login.data['code'], 'email_not_verified')
        created.profile.is_email_verified = True
        created.profile.save(update_fields=('is_email_verified', 'updated_at'))
        token = RefreshToken.for_user(created).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        event = self.client.post('/api/events/', {
            'title': 'Admin hosted event', 'description': 'A verified admin can create events.',
            'location': 'Community Hall', 'start_at': '2030-05-01T10:00:00Z',
            'end_at': '2030-05-01T12:00:00Z', 'capacity': 50,
        }, format='json')
        self.assertEqual(event.status_code, 201)

    def test_password_confirmation_is_validated(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.post(self.url, {**self.payload, 'password_confirm': 'different'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('password_confirm', response.data)
