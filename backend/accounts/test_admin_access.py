from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import AdminAccessRequest, EmailOTP, Profile


User = get_user_model()


class AdminAccessRequestTests(TestCase):
    register_url = '/api/auth/register/'
    login_url = '/api/auth/login/'
    refresh_url = '/api/auth/token/refresh/'
    request_url = '/api/auth/admin-requests/'
    password = 'Complex#Pass987!'

    def setUp(self):
        self.client = APIClient()
        self.superuser = User.objects.create_superuser(
            username='root', email='root@example.com', password=self.password
        )
        Profile.objects.create(
            user=self.superuser,
            role=Profile.Role.ADMIN,
            is_email_verified=True,
        )

    def registration_payload(self, role='admin', username='applicant'):
        return {
            'username': username,
            'email': f'{username}@example.com',
            'password': self.password,
            'password_confirm': self.password,
            'first_name': 'Example',
            'last_name': 'Applicant',
            'role': role,
        }

    def register(self, role='admin', username='applicant'):
        with patch('backend.accounts.views.send_otp_email') as send_email:
            response = self.client.post(
                self.register_url,
                self.registration_payload(role=role, username=username),
                format='json',
            )
        code = send_email.call_args.args[1]
        return response, code

    def create_user(self, username, *, verified=True, staff=False):
        user = User.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password=self.password,
            is_staff=staff,
        )
        Profile.objects.create(
            user=user,
            is_email_verified=verified,
            role=Profile.Role.ADMIN if staff else Profile.Role.USER,
        )
        return user

    def sign_in_as(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def decide(self, admin_request, action, *, reason=''):
        return self.client.post(
            f'{self.request_url}{admin_request.pk}/{action}/',
            {'reason': reason},
            format='json',
        )

    def login(self, username='applicant'):
        return self.client.post(
            self.login_url,
            {'identifier': username, 'password': self.password},
            format='json',
        )

    def test_normal_user_registration_keeps_demo_access_and_creates_no_request(self):
        response, _ = self.register(role='user')

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username='applicant')
        self.assertTrue(user.profile.registration_demo_access)
        self.assertFalse(user.is_staff)
        self.assertEqual(user.profile.role, Profile.Role.USER)
        self.assertFalse(AdminAccessRequest.objects.filter(requester=user).exists())
        self.assertTrue(EmailOTP.objects.filter(user=user).exists())

    def test_admin_registration_creates_pending_request_without_privileges(self):
        response, _ = self.register()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['admin_request_status'], 'pending')
        user = User.objects.get(username='applicant')
        admin_request = AdminAccessRequest.objects.get(requester=user)
        self.assertEqual(admin_request.status, AdminAccessRequest.Status.PENDING)
        self.assertFalse(user.is_staff)
        self.assertEqual(user.profile.role, Profile.Role.USER)
        self.assertFalse(user.profile.registration_demo_access)
        self.assertFalse(user.profile.is_email_verified)
        self.assertTrue(EmailOTP.objects.filter(user=user).exists())

    def test_unsupported_role_value_is_rejected(self):
        response = self.client.post(
            self.register_url,
            self.registration_payload(role='superuser'),
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('role', response.data)
        self.assertEqual(User.objects.filter(username='applicant').count(), 0)

    def test_pending_admin_request_blocks_login_with_clear_error(self):
        self.register()

        response = self.login()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'admin_request_pending')
        self.assertIn('pending', response.data['detail'].lower())

    def test_rejected_admin_request_blocks_login_and_grants_no_privileges(self):
        self.register()
        admin_request = AdminAccessRequest.objects.get(requester__username='applicant')
        self.sign_in_as(self.superuser)
        decision = self.decide(admin_request, 'reject', reason='Not approved.')

        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.data['status'], AdminAccessRequest.Status.REJECTED)
        self.assertEqual(decision.data['decision_reason'], 'Not approved.')
        admin_request.requester.refresh_from_db()
        admin_request.requester.profile.refresh_from_db()
        self.assertFalse(admin_request.requester.is_staff)
        self.assertEqual(admin_request.requester.profile.role, Profile.Role.USER)
        self.client.credentials()
        login = self.login()
        self.assertEqual(login.status_code, 403)
        self.assertEqual(login.data['code'], 'admin_request_rejected')

    def test_approved_admin_can_login_after_email_verification(self):
        _, code = self.register()
        user = User.objects.get(username='applicant')
        verified = self.client.post(
            '/api/auth/verify-email/',
            {'email': user.email, 'otp': code},
            format='json',
        )
        self.assertEqual(verified.status_code, 200)
        admin_request = AdminAccessRequest.objects.get(requester=user)
        self.sign_in_as(self.superuser)

        approval = self.decide(admin_request, 'approve')

        self.assertEqual(approval.status_code, 200)
        self.assertEqual(approval.data['status'], AdminAccessRequest.Status.APPROVED)
        self.assertEqual(approval.data['reviewer']['id'], self.superuser.pk)
        self.assertIsNotNone(approval.data['reviewed_at'])
        user.refresh_from_db()
        user.profile.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertEqual(user.profile.role, Profile.Role.ADMIN)
        self.client.credentials()
        login = self.login()
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.data['is_staff'])

    def test_approved_but_unverified_admin_still_cannot_login(self):
        self.register()
        user = User.objects.get(username='applicant')
        admin_request = AdminAccessRequest.objects.get(requester=user)
        self.sign_in_as(self.superuser)
        approval = self.decide(admin_request, 'approve')
        self.assertEqual(approval.status_code, 200)
        self.client.credentials()

        login = self.login()

        self.assertEqual(login.status_code, 403)
        self.assertEqual(login.data['code'], 'email_not_verified')

    def test_ordinary_user_login_is_unaffected_by_admin_request_workflow(self):
        self.register(role='user')

        response = self.login()

        self.assertEqual(response.status_code, 200)

    def test_only_superusers_can_list_or_decide_requests(self):
        self.register()
        admin_request = AdminAccessRequest.objects.get(requester__username='applicant')
        for user in (
            self.create_user('member'),
            self.create_user('staffmember', staff=True),
        ):
            self.sign_in_as(user)
            self.assertEqual(self.client.get(self.request_url).status_code, 403)
            self.assertEqual(self.decide(admin_request, 'approve').status_code, 403)
            self.assertEqual(self.decide(admin_request, 'reject').status_code, 403)

    def test_superuser_can_list_pending_requests_and_filter_status(self):
        self.register()
        self.sign_in_as(self.superuser)

        pending = self.client.get(self.request_url)
        all_requests = self.client.get(self.request_url, {'status': 'all'})
        invalid = self.client.get(self.request_url, {'status': 'unknown'})

        self.assertEqual(pending.status_code, 200)
        self.assertEqual(pending.data['count'], 1)
        self.assertEqual(pending.data['results'][0]['status'], 'pending')
        self.assertEqual(all_requests.data['count'], 1)
        self.assertEqual(invalid.status_code, 400)

    def test_superuser_cannot_review_own_request(self):
        admin_request = AdminAccessRequest.objects.create(requester=self.superuser)
        self.sign_in_as(self.superuser)

        response = self.decide(admin_request, 'approve')

        self.assertEqual(response.status_code, 403)
        admin_request.refresh_from_db()
        self.assertEqual(admin_request.status, AdminAccessRequest.Status.PENDING)

    def test_reviewed_request_cannot_be_decided_twice(self):
        self.register()
        admin_request = AdminAccessRequest.objects.get(requester__username='applicant')
        self.sign_in_as(self.superuser)
        self.assertEqual(self.decide(admin_request, 'reject').status_code, 200)

        second_decision = self.decide(admin_request, 'approve')

        self.assertEqual(second_decision.status_code, 409)

    def test_database_prevents_multiple_pending_requests_for_one_user(self):
        user = self.create_user('duplicate')
        AdminAccessRequest.objects.create(requester=user)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AdminAccessRequest.objects.create(requester=user)

    def test_pending_and_rejected_requests_block_jwt_refresh(self):
        self.register()
        user = User.objects.get(username='applicant')
        refresh = str(RefreshToken.for_user(user))
        pending_refresh = self.client.post(
            self.refresh_url, {'refresh': refresh}, format='json'
        )
        self.assertEqual(pending_refresh.status_code, 403)
        self.assertEqual(pending_refresh.data['code'], 'admin_request_pending')

        admin_request = AdminAccessRequest.objects.get(requester=user)
        self.sign_in_as(self.superuser)
        self.assertEqual(self.decide(admin_request, 'reject').status_code, 200)
        self.client.credentials()
        rejected_refresh = self.client.post(
            self.refresh_url, {'refresh': refresh}, format='json'
        )
        self.assertEqual(rejected_refresh.status_code, 403)
        self.assertEqual(rejected_refresh.data['code'], 'admin_request_rejected')
