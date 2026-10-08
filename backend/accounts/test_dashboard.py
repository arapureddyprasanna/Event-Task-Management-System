from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from backend.accounts.models import Activity, AdminAccessRequest, Notification, Profile
from backend.events.models import Event, EventRegistration
from backend.tasks.models import Task, TaskStatus


User = get_user_model()


class DashboardAPITests(TestCase):
    password = 'Complex#Pass987!'

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user('dashboard-user')
        self.other = self.create_user('other-user')
        self.staff = self.create_user('dashboard-staff', staff=True)
        self.superuser = User.objects.create_superuser(
            username='dashboard-root',
            email='dashboard-root@example.com',
            password=self.password,
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
            role=Profile.Role.ADMIN if staff else Profile.Role.USER,
            is_email_verified=True,
        )
        return user

    def create_event(self, title, *, start_at=None, capacity=4):
        start_at = start_at or timezone.now() + timedelta(days=2)
        event = Event.objects.create(
            title=title,
            description=f'{title} description',
            organizer=self.staff,
            location='Main Hall',
            start_at=start_at,
            end_at=start_at + timedelta(hours=2),
            capacity=capacity,
        )
        event.status = Event.Status.PUBLISHED
        event.save(update_fields=('status', 'updated_at'))
        return event

    @staticmethod
    def create_task(event, assignee, *, status=TaskStatus.TODO, due_at=None, title='Task'):
        task = Task.objects.create(
            event=event,
            assignee=assignee,
            title=title,
            description=f'{title} details',
            due_at=due_at,
        )
        for next_status in {
            TaskStatus.IN_PROGRESS: (TaskStatus.IN_PROGRESS,),
            TaskStatus.COMPLETED: (TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED),
        }.get(status, ()):
            task.status = next_status
            task.save()
        return task

    def test_user_dashboard_aggregates_only_current_users_records(self):
        upcoming = self.create_event('Registered event')
        cancelled_event = self.create_event('Cancelled registration event')
        unregistered_event = self.create_event('Not registered event')
        EventRegistration.objects.create(event=upcoming, user=self.user)
        EventRegistration.objects.create(
            event=cancelled_event,
            user=self.user,
            status=EventRegistration.Status.CANCELLED,
        )
        other_event = self.create_event('Other user event')
        EventRegistration.objects.create(event=other_event, user=self.other)

        self.create_task(upcoming, self.user, title='Pending task')
        self.create_task(
            upcoming,
            self.user,
            status=TaskStatus.IN_PROGRESS,
            due_at=timezone.now() - timedelta(hours=1),
            title='Overdue task',
        )
        self.create_task(
            upcoming,
            self.user,
            status=TaskStatus.COMPLETED,
            due_at=timezone.now() - timedelta(days=1),
            title='Completed task',
        )
        self.create_task(other_event, self.other, title='Private task')

        own_notice = Notification.objects.create(
            recipient=self.user,
            category=Notification.Category.SYSTEM,
            title='Own notice',
            message='For this user',
        )
        Notification.objects.create(
            recipient=self.other,
            category=Notification.Category.SYSTEM,
            title='Private notice',
            message='For another user',
        )
        own_activity = Activity.objects.create(
            actor=self.user,
            target_user=self.user,
            action_type=Activity.Action.USER_REGISTERED_FOR_EVENT,
            description='Own activity',
        )
        Activity.objects.create(
            actor=self.other,
            target_user=self.other,
            action_type=Activity.Action.USER_REGISTERED_FOR_EVENT,
            description='Private activity',
        )

        self.client.force_authenticate(self.user)
        response = self.client.get('/api/dashboard/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['registrations'], {
            'total': 2,
            'active': 1,
            'upcoming': 1,
            'cancelled': 1,
        })
        self.assertEqual(response.data['tasks'], {
            'total': 3,
            'pending': 1,
            'in_progress': 1,
            'completed': 1,
            'overdue': 1,
        })
        self.assertEqual(response.data['unread_notifications'], 1)
        self.assertEqual(response.data['recent_notifications'][0]['id'], own_notice.pk)
        self.assertEqual(response.data['recent_activity'][0]['id'], own_activity.pk)
        self.assertEqual(
            {event['id'] for event in response.data['upcoming_events']},
            {upcoming.pk, cancelled_event.pk, unregistered_event.pk, other_event.pk},
        )

    def test_admin_dashboard_counts_and_access_boundaries(self):
        upcoming = self.create_event('Admin upcoming event')
        past = self.create_event('Admin past event', start_at=timezone.now() - timedelta(days=3))
        EventRegistration.objects.create(event=upcoming, user=self.user)
        EventRegistration.objects.create(event=upcoming, user=self.other)
        EventRegistration.objects.create(
            event=past,
            user=self.other,
            status=EventRegistration.Status.CANCELLED,
        )
        self.create_task(upcoming, self.user, title='Admin pending task')
        self.create_task(
            upcoming,
            self.other,
            status=TaskStatus.COMPLETED,
            title='Admin completed task',
        )
        AdminAccessRequest.objects.create(requester=self.user)
        Notification.objects.create(
            recipient=self.superuser,
            category=Notification.Category.ADMIN_ACCESS_REQUEST,
            title='Admin notice',
            message='Pending admin request',
        )
        Notification.objects.create(
            recipient=self.user,
            category=Notification.Category.ADMIN_ACCESS_REQUEST,
            title='Not an admin notice',
            message='Private notice',
        )
        Activity.objects.create(
            actor=self.user,
            target_user=self.user,
            action_type=Activity.Action.ADMIN_ACCESS_REQUESTED,
            description='System admin activity',
        )

        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/admin/dashboard/').status_code, 403)

        self.client.force_authenticate(self.superuser)
        response = self.client.get('/api/admin/dashboard/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['users']['total'], 4)
        self.assertEqual(response.data['events'], {'total': 2, 'published': 2})
        self.assertEqual(response.data['registrations'], {'total': 3, 'active': 2})
        self.assertEqual(response.data['tasks'], {
            'total': 2,
            'pending': 1,
            'in_progress': 0,
            'completed': 1,
            'overdue': 0,
        })
        self.assertEqual(response.data['pending_admin_access_requests'], 1)
        self.assertEqual(response.data['unread_admin_notifications'], 1)
        self.assertEqual(len(response.data['recent_activity']), 1)
        self.assertEqual(
            [event['id'] for event in response.data['upcoming_events']], [upcoming.pk]
        )

    def test_admin_staff_role_can_access_admin_dashboard(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get('/api/admin/dashboard/').status_code, 200)

    def test_upcoming_event_filter_and_capacity_fields_are_authoritative(self):
        full = self.create_event('Full event', capacity=1)
        EventRegistration.objects.create(event=full, user=self.user)
        EventRegistration.objects.create(
            event=full,
            user=self.other,
            status=EventRegistration.Status.CANCELLED,
        )
        unlimited = self.create_event('Unlimited event', capacity=None)
        available = self.create_event('Available event', capacity=3)
        EventRegistration.objects.create(event=available, user=self.user)
        EventRegistration.objects.create(
            event=available,
            user=self.other,
            status=EventRegistration.Status.CANCELLED,
        )
        cancelled = self.create_event('Cancelled event')
        cancelled.status = Event.Status.CANCELLED
        cancelled.save(update_fields=('status', 'updated_at'))

        response = self.client.get('/api/events/', {'upcoming': 'true'})

        self.assertEqual(response.status_code, 200)
        rows = {row['id']: row for row in response.data['results']}
        self.assertEqual(rows[full.pk]['registration_count'], 1)
        self.assertEqual(rows[full.pk]['remaining_seats'], 0)
        self.assertEqual(rows[full.pk]['availability'], 'full')
        self.assertEqual(rows[available.pk]['registration_count'], 1)
        self.assertEqual(rows[available.pk]['remaining_seats'], 2)
        self.assertEqual(rows[available.pk]['availability'], 'available')
        self.assertIsNone(rows[unlimited.pk]['remaining_seats'])
        self.assertEqual(rows[unlimited.pk]['availability'], 'available')
        self.assertNotIn(cancelled.pk, rows)
        self.assertEqual(self.client.get('/api/events/', {'upcoming': 'invalid'}).status_code, 400)

        past = self.create_event('Past event', start_at=timezone.now() - timedelta(days=1))
        past_response = self.client.get(f'/api/events/{past.pk}/')
        cancelled_response = self.client.get(f'/api/events/{cancelled.pk}/')
        self.assertEqual(past_response.data['availability'], 'registration_closed')
        self.assertEqual(cancelled_response.data['availability'], 'cancelled')

        draft = Event.objects.create(
            title='Draft event',
            description='Not published',
            organizer=self.staff,
            location='Main Hall',
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=2),
        )
        self.client.force_authenticate(self.staff)
        self.assertEqual(
            self.client.get(f'/api/events/{draft.pk}/').data['availability'],
            'unpublished',
        )

    def test_organizer_registration_search_keeps_private_user_boundary(self):
        event = self.create_event('Participant event')
        EventRegistration.objects.create(event=event, user=self.user)
        EventRegistration.objects.create(event=event, user=self.other)
        url = f'/api/events/{event.pk}/registrations/'

        self.client.force_authenticate(self.staff)
        response = self.client.get(url, {'search': 'dashboard-user'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        attendee = response.data['results'][0]['attendee']
        self.assertEqual(attendee['id'], self.user.pk)
        self.assertNotIn('email', attendee)
        self.assertNotIn('password', attendee)

        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_public_upcoming_event_order_uses_server_time(self):
        later = self.create_event('Later', start_at=timezone.now() + timedelta(days=5))
        earlier = self.create_event('Earlier', start_at=timezone.now() + timedelta(days=1))
        self.create_event('Past', start_at=timezone.now() - timedelta(hours=1))

        response = self.client.get('/api/events/?upcoming=true')

        self.assertEqual(
            [item['id'] for item in response.data['results']], [earlier.pk, later.pk]
        )
