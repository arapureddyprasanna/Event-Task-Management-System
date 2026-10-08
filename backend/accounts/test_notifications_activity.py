from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from backend.accounts.models import Activity, AdminAccessRequest, Notification, Profile
from backend.accounts.services.activities import create_activity
from backend.accounts.services.notifications import create_notification
from backend.events.models import Event, EventRegistration
from backend.events.models import EventStatus
from backend.tasks.models import Task


User = get_user_model()


class NotificationActivityAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = self.create_user('owner')
        self.target = self.create_user('target')
        self.other = self.create_user('other')
        self.superuser = User.objects.create_superuser(
            username='root', email='root@example.com', password='Complex#Pass987!'
        )
        Profile.objects.create(
            user=self.superuser,
            role=Profile.Role.ADMIN,
            is_email_verified=True,
        )

    @staticmethod
    def create_user(username):
        user = User.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password='Complex#Pass987!',
        )
        Profile.objects.create(user=user, is_email_verified=True)
        return user

    def test_notification_service_creates_user_scoped_records(self):
        own = create_notification(
            self.owner,
            Notification.Category.SYSTEM,
            'For owner',
            'Own message',
        )
        create_notification(
            self.target,
            Notification.Category.SYSTEM,
            'For target',
            'Private message',
        )
        self.client.force_authenticate(self.owner)

        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], own.pk)
        self.assertEqual(
            self.client.get('/api/notifications/?unread=true').data['count'],
            1,
        )
        self.assertEqual(
            self.client.get('/api/notifications/?unread=false').data['count'],
            0,
        )
        self.assertEqual(
            self.client.get('/api/notifications/?unread=invalid').status_code,
            400,
        )

    def test_notification_read_endpoints_are_recipient_scoped(self):
        own = create_notification(
            self.owner,
            Notification.Category.SYSTEM,
            'Own',
            'Own message',
        )
        other = create_notification(
            self.target,
            Notification.Category.SYSTEM,
            'Other',
            'Private message',
        )
        self.client.force_authenticate(self.owner)

        marked = self.client.post(f'/api/notifications/{own.pk}/read/')
        self.assertEqual(marked.status_code, 200)
        own.refresh_from_db()
        self.assertTrue(own.is_read)
        self.assertEqual(self.client.post(f'/api/notifications/{other.pk}/read/').status_code, 404)

        create_notification(
            self.owner,
            Notification.Category.SYSTEM,
            'Another',
            'Second message',
        )
        response = self.client.post('/api/notifications/read-all/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['updated'], 1)
        self.assertEqual(
            Notification.objects.filter(recipient=self.target, is_read=False).count(), 1
        )

    def test_activity_service_and_api_visibility(self):
        own = create_activity(
            self.owner,
            Activity.Action.USER_REGISTERED_FOR_EVENT,
            'Owner registered.',
            target_user=self.owner,
        )
        targeted = create_activity(
            self.owner,
            Activity.Action.TASK_ASSIGNED,
            'Task assigned to target.',
            target_user=self.target,
        )
        self.client.force_authenticate(self.target)

        response = self.client.get('/api/activity/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], targeted.pk)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get('/api/activity/').data['count'], 0)
        self.client.force_authenticate(self.superuser)
        self.assertEqual(self.client.get('/api/activity/').data['count'], 2)
        self.assertNotEqual(own.pk, targeted.pk)


class NotificationActivityIntegrationTests(TestCase):
    password = 'Complex#Pass987!'

    def setUp(self):
        self.client = APIClient()
        self.organizer = self.create_user('organizer', staff=True)
        self.attendee = self.create_user('attendee')
        self.other_attendee = self.create_user('other-attendee')
        self.superuser = User.objects.create_superuser(
            username='root', email='root@example.com', password=self.password
        )
        Profile.objects.create(
            user=self.superuser,
            role=Profile.Role.ADMIN,
            is_email_verified=True,
        )

    def create_user(self, username, *, staff=False):
        user = User.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password=self.password,
            is_staff=staff,
        )
        Profile.objects.create(
            user=user,
            is_email_verified=True,
            role=Profile.Role.ADMIN if staff else Profile.Role.USER,
        )
        return user

    def create_event(self):
        now = timezone.now()
        event = Event.objects.create(
            title='Community gathering',
            description='A real event for integration tests.',
            organizer=self.organizer,
            location='Main hall',
            start_at=now + timedelta(days=2),
            end_at=now + timedelta(days=2, hours=2),
        )
        event.status = EventStatus.PUBLISHED
        event.save(update_fields=('status', 'updated_at'))
        return event

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def test_registration_and_cancellation_create_records_only_on_transitions(self):
        event = self.create_event()
        self.authenticate(self.attendee)

        registered = self.client.post(f'/api/events/{event.pk}/register/', {}, format='json')

        self.assertEqual(registered.status_code, 201)
        registration_id = registered.data['id']
        self.assertTrue(Notification.objects.filter(
            recipient=self.attendee,
            category=Notification.Category.EVENT_REGISTRATION,
            related_id=registration_id,
        ).exists())
        self.assertTrue(Activity.objects.filter(
            actor=self.attendee,
            action_type=Activity.Action.USER_REGISTERED_FOR_EVENT,
            target_registration_id=registration_id,
        ).exists())
        self.assertEqual(
            self.client.post(f'/api/events/{event.pk}/register/', {}, format='json').status_code,
            409,
        )
        self.assertEqual(Notification.objects.filter(recipient=self.attendee).count(), 1)
        self.assertEqual(Activity.objects.filter(actor=self.attendee).count(), 1)

        cancelled = self.client.post(f'/api/events/{event.pk}/register/cancel/', {})
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.data['status'], EventRegistration.Status.CANCELLED)
        self.client.post(f'/api/events/{event.pk}/register/cancel/', {})
        self.assertEqual(Notification.objects.filter(recipient=self.attendee).count(), 2)
        self.assertEqual(Activity.objects.filter(actor=self.attendee).count(), 2)

    def test_admin_access_request_and_decisions_create_records(self):
        payload = {
            'username': 'admin-applicant',
            'email': 'admin-applicant@example.com',
            'password': self.password,
            'password_confirm': self.password,
            'role': 'admin',
        }
        with patch('backend.accounts.views.send_otp_email'):
            response = self.client.post('/api/auth/register/', payload, format='json')
        applicant = User.objects.get(username='admin-applicant')
        request = AdminAccessRequest.objects.get(requester=applicant)
        superuser_notice = Notification.objects.get(
            recipient=self.superuser,
            category=Notification.Category.ADMIN_ACCESS_REQUEST,
            related_id=request.pk,
        )
        self.assertIn('admin-applicant', superuser_notice.message)
        self.assertTrue(Activity.objects.filter(
            action_type=Activity.Action.ADMIN_ACCESS_REQUESTED,
            actor=applicant,
        ).exists())
        self.assertEqual(response.status_code, 201)

        self.authenticate(self.superuser)
        approval = self.client.post(
            f'/api/auth/admin-requests/{request.pk}/approve/', {}, format='json'
        )
        self.assertEqual(approval.status_code, 200)
        self.assertTrue(Notification.objects.filter(
            recipient=applicant,
            category=Notification.Category.ADMIN_ACCESS_APPROVED,
            related_id=request.pk,
        ).exists())
        self.assertTrue(Activity.objects.filter(
            action_type=Activity.Action.ADMIN_ACCESS_APPROVED,
            target_user=applicant,
        ).exists())

        rejected_payload = {**payload, 'username': 'rejected-applicant', 'email': 'rejected@example.com'}
        with patch('backend.accounts.views.send_otp_email'):
            self.client.force_authenticate(None)
            self.client.post('/api/auth/register/', rejected_payload, format='json')
        rejected_user = User.objects.get(username='rejected-applicant')
        rejected_request = AdminAccessRequest.objects.get(requester=rejected_user)
        self.authenticate(self.superuser)
        rejection = self.client.post(
            f'/api/auth/admin-requests/{rejected_request.pk}/reject/', {}, format='json'
        )
        self.assertEqual(rejection.status_code, 200)
        self.assertTrue(Notification.objects.filter(
            recipient=rejected_user,
            category=Notification.Category.ADMIN_ACCESS_REJECTED,
            related_id=rejected_request.pk,
        ).exists())
        self.assertTrue(Activity.objects.filter(
            action_type=Activity.Action.ADMIN_ACCESS_REJECTED,
            target_user=rejected_user,
        ).exists())

    def test_task_create_assignment_status_and_meaningful_updates_create_records(self):
        event = self.create_event()
        EventRegistration.objects.create(event=event, user=self.attendee)
        EventRegistration.objects.create(event=event, user=self.other_attendee)
        self.authenticate(self.organizer)
        response = self.client.post(
            f'/api/events/{event.pk}/tasks/',
            {
                'title': 'Prepare welcome table',
                'description': 'Set up before doors open.',
                'priority': 'high',
                'assignee_id': self.attendee.pk,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        task = Task.objects.get(pk=response.data['id'])
        self.assertTrue(Notification.objects.filter(
            recipient=self.attendee,
            category=Notification.Category.TASK_ASSIGNED,
            related_id=task.pk,
        ).exists())
        self.assertTrue(Activity.objects.filter(
            action_type=Activity.Action.TASK_CREATED,
            target_task=task,
        ).exists())
        self.assertTrue(Activity.objects.filter(
            action_type=Activity.Action.TASK_ASSIGNED,
            target_task=task,
        ).exists())

        status_change = self.client.patch(
            f'/api/tasks/{task.pk}/', {'status': 'in_progress'}, format='json'
        )
        self.assertEqual(status_change.status_code, 200)
        self.assertTrue(Activity.objects.filter(
            action_type=Activity.Action.TASK_STATUS_CHANGED,
            target_task=task,
        ).exists())
        self.assertTrue(Notification.objects.filter(
            recipient=self.attendee,
            category=Notification.Category.TASK_UPDATED,
            related_id=task.pk,
        ).exists())

        before_activities = Activity.objects.filter(target_task=task).count()
        before_notifications = Notification.objects.filter(related_type='task', related_id=task.pk).count()
        unchanged = self.client.patch(
            f'/api/tasks/{task.pk}/', {'status': 'in_progress'}, format='json'
        )
        self.assertEqual(unchanged.status_code, 200)
        self.assertEqual(Activity.objects.filter(target_task=task).count(), before_activities)
        self.assertEqual(
            Notification.objects.filter(related_type='task', related_id=task.pk).count(),
            before_notifications,
        )

        assignment = self.client.patch(
            f'/api/tasks/{task.pk}/', {'assignee_id': self.other_attendee.pk}, format='json'
        )
        self.assertEqual(assignment.status_code, 200)
        self.assertTrue(Notification.objects.filter(
            recipient=self.other_attendee,
            category=Notification.Category.TASK_ASSIGNED,
            related_id=task.pk,
        ).exists())

