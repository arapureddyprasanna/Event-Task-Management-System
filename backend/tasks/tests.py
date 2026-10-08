from datetime import datetime, timedelta, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from backend.accounts.models import Profile
from backend.events.models import Event, EventRegistration
from .models import Task, TaskPriority, TaskStatus


User = get_user_model()


class TaskAPITests(TestCase):
    password = 'Complex#Pass987!'

    def setUp(self):
        self.client = APIClient()
        self.organizer = self.create_user('organizer')
        self.attendee = self.create_user('attendee')
        self.other = self.create_user('other')
        self.staff = self.create_user('staff', staff=True)
        self.unverified = self.create_user('unverified', verified=False)
        self.inactive = self.create_user('inactive', active=False)
        self.event = self.create_event(self.organizer)
        self.register(self.event, self.attendee)

    def create_user(self, username, *, verified=True, active=True, staff=False):
        user = User.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password=self.password,
            is_active=active,
            is_staff=staff,
        )
        Profile.objects.create(
            user=user,
            is_email_verified=verified,
            role=Profile.Role.ADMIN if staff else Profile.Role.USER,
        )
        return user

    def create_event(self, organizer, *, state=Event.Status.PUBLISHED, end_at=None):
        event = Event.objects.create(
            title='Community meetup', description='A local event.',
            organizer=organizer, location='Central Hall',
            start_at=datetime(2030, 5, 1, 10, tzinfo=dt_timezone.utc),
            end_at=end_at or datetime(2030, 5, 1, 12, tzinfo=dt_timezone.utc),
        )
        if state != Event.Status.DRAFT:
            event.status = Event.Status.PUBLISHED
            event.save()
        if state not in (Event.Status.DRAFT, Event.Status.PUBLISHED):
            event.status = state
            event.save()
        return event

    @staticmethod
    def register(event, user):
        return EventRegistration.objects.create(event=event, user=user)

    def create_task(self, *, event=None, assignee=None, **overrides):
        return Task.objects.create(
            event=event or self.event,
            title=overrides.pop('title', 'Prepare venue'),
            description=overrides.pop('description', 'Arrange tables and chairs.'),
            assignee=assignee,
            **overrides,
        )

    def auth(self, user):
        self.client.force_authenticate(user)

    def event_tasks_url(self, event=None):
        return f'/api/events/{(event or self.event).pk}/tasks/'

    def test_model_fields_choices_relationships_and_timezone_validation(self):
        due = datetime(2030, 4, 30, 10, tzinfo=dt_timezone.utc)
        task = self.create_task(assignee=self.attendee, due_at=due)
        self.assertEqual(task.event, self.event)
        self.assertEqual(task.assignee, self.attendee)
        self.assertEqual(task.status, TaskStatus.TODO)
        self.assertEqual(task.priority, TaskPriority.MEDIUM)
        self.assertIsNotNone(task.created_at.tzinfo)
        self.assertIsNotNone(task.updated_at.tzinfo)
        with self.assertRaises(ValidationError):
            self.create_task(status='made_up')
        with self.assertRaises(ValidationError):
            self.create_task(priority='critical')
        with self.assertRaises(ValidationError):
            self.create_task(due_at=datetime(2030, 4, 30, 10))

    def test_database_constraints_and_model_status_lifecycle(self):
        task = self.create_task()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Task.objects.filter(pk=task.pk).update(status='invalid')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Task.objects.filter(pk=task.pk).update(priority='critical')
        task.status = TaskStatus.IN_PROGRESS
        task.save()
        task.status = TaskStatus.COMPLETED
        task.save()
        task.status = TaskStatus.TODO
        with self.assertRaises(ValidationError):
            task.save()
        task.refresh_from_db()
        task.status = 'invalid'
        with self.assertRaises(ValidationError):
            task.save()

    def test_creation_permissions_event_source_and_terminal_event_rules(self):
        payload = {'title': 'Book equipment', 'description': 'Reserve microphones.'}
        self.assertEqual(self.client.post(self.event_tasks_url(), payload, format='json').status_code, 401)
        self.auth(self.organizer)
        created = self.client.post(self.event_tasks_url(), payload, format='json')
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data['event'], self.event.pk)
        self.assertEqual(created.data['status'], TaskStatus.TODO)
        self.assertEqual(created.data['priority'], TaskPriority.MEDIUM)

        draft = self.create_event(self.organizer, state=Event.Status.DRAFT)
        self.assertEqual(self.client.post(self.event_tasks_url(draft), payload, format='json').status_code, 201)
        cancelled = self.create_event(self.organizer, state=Event.Status.CANCELLED)
        self.assertEqual(self.client.post(self.event_tasks_url(cancelled), payload, format='json').status_code, 400)
        completed = self.create_event(self.organizer, state=Event.Status.COMPLETED)
        self.assertEqual(self.client.post(self.event_tasks_url(completed), payload, format='json').status_code, 400)

        another_event = self.create_event(self.other)
        self.auth(self.staff)
        self.assertEqual(self.client.post(self.event_tasks_url(another_event), payload, format='json').status_code, 201)
        self.auth(self.other)
        self.assertEqual(self.client.post(self.event_tasks_url(), payload, format='json').status_code, 403)
        for user in (self.unverified, self.inactive):
            self.auth(user)
            self.assertEqual(self.client.post(self.event_tasks_url(), payload, format='json').status_code, 403)

    def test_creation_rejects_forged_fields_and_invalid_status(self):
        self.auth(self.organizer)
        payload = {'title': 'Book equipment', 'description': 'Reserve microphones.'}
        for injected in (
            {'event': self.event.pk + 1},
            {'event_id': self.event.pk + 1},
            {'organizer_id': self.other.pk},
            {'created_at': '2030-01-01T00:00:00Z'},
            {'status': TaskStatus.COMPLETED},
        ):
            response = self.client.post(self.event_tasks_url(), {**payload, **injected}, format='json')
            self.assertEqual(response.status_code, 400, injected)
        self.assertEqual(Task.objects.count(), 0)

    def test_assignment_requires_active_registered_attendee(self):
        self.auth(self.organizer)
        payload = {
            'title': 'Guide attendees', 'description': 'Help direct guests.',
            'assignee_id': self.attendee.pk,
        }
        accepted = self.client.post(self.event_tasks_url(), payload, format='json')
        self.assertEqual(accepted.status_code, 201)
        self.assertEqual(accepted.data['assignee']['id'], self.attendee.pk)

        for assignee_id in (self.other.pk, 987654321, self.inactive.pk):
            if assignee_id == self.inactive.pk:
                self.register(self.event, self.inactive)
            response = self.client.post(
                self.event_tasks_url(), {**payload, 'assignee_id': assignee_id}, format='json'
            )
            self.assertEqual(response.status_code, 400)

    def test_event_task_list_filters_pagination_order_and_query_efficiency(self):
        for index in range(23):
            task = self.create_task(
                title=f'Prepare area {index:02d}',
                description='Venue preparation',
                priority=TaskPriority.HIGH if index % 2 else TaskPriority.LOW,
                due_at=datetime(2030, 4, 30, 10, tzinfo=dt_timezone.utc) + timedelta(hours=index),
            )
            if index % 3 == 0:
                task.status = TaskStatus.IN_PROGRESS
                task.save()
        self.auth(self.organizer)
        with self.assertNumQueries(3):
            response = self.client.get(self.event_tasks_url(), {'page_size': 20})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 23)
        self.assertEqual(len(response.data['results']), 20)
        self.assertIsNotNone(response.data['next'])
        self.assertEqual(
            [row['title'] for row in response.data['results']],
            sorted(row['title'] for row in response.data['results']),
        )
        self.assertEqual(self.client.get(self.event_tasks_url(), {'search': 'area 22'}).data['count'], 1)
        self.assertEqual(self.client.get(self.event_tasks_url(), {'status': 'in_progress'}).data['count'], 8)
        self.assertEqual(self.client.get(self.event_tasks_url(), {'priority': 'high'}).data['count'], 11)
        self.create_task(title='Assigned task', assignee=self.attendee)
        self.assertEqual(self.client.get(self.event_tasks_url(), {'assignee': str(self.attendee.pk)}).data['count'], 1)
        self.assertEqual(
            self.client.get(self.event_tasks_url(), {'due_after': '2030-04-30T20:00:00Z'}).data['count'],
            13,
        )
        self.assertEqual(self.client.get(self.event_tasks_url(), {'status': 'invalid'}).status_code, 400)

    def test_task_visibility_and_safe_task_detail(self):
        task = self.create_task(assignee=self.attendee)
        detail_url = f'/api/tasks/{task.pk}/'
        self.auth(self.other)
        self.assertEqual(self.client.get(detail_url).status_code, 403)
        self.auth(self.organizer)
        organizer_response = self.client.get(detail_url)
        self.assertEqual(organizer_response.status_code, 200)
        self.assertEqual(organizer_response.data['event_title'], self.event.title)
        self.assertNotIn('password', organizer_response.data)
        self.assertNotIn('otp', organizer_response.data)
        self.auth(self.attendee)
        self.assertEqual(self.client.get(detail_url).status_code, 200)
        self.auth(self.staff)
        self.assertEqual(self.client.get(detail_url).status_code, 200)

    def test_organizer_staff_and_assignee_updates_with_field_restrictions(self):
        task = self.create_task(assignee=self.attendee)
        detail_url = f'/api/tasks/{task.pk}/'
        self.auth(self.other)
        self.assertEqual(self.client.patch(detail_url, {'title': 'Changed'}, format='json').status_code, 403)

        self.auth(self.attendee)
        started = self.client.patch(detail_url, {'status': TaskStatus.IN_PROGRESS}, format='json')
        self.assertEqual(started.status_code, 200)
        self.assertEqual(
            self.client.patch(detail_url, {'title': 'Hijack'}, format='json').status_code, 400
        )
        completed = self.client.patch(detail_url, {'status': TaskStatus.COMPLETED}, format='json')
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(
            self.client.patch(detail_url, {'status': TaskStatus.TODO}, format='json').status_code, 400
        )

        self.auth(self.organizer)
        self.assertEqual(self.client.patch(detail_url, {'title': 'Final title'}, format='json').status_code, 200)
        self.assertEqual(
            self.client.patch(detail_url, {'event': self.event.pk + 1}, format='json').status_code, 400
        )
        self.auth(self.staff)
        self.assertEqual(self.client.patch(detail_url, {'priority': TaskPriority.URGENT}, format='json').status_code, 200)

    def test_assignee_can_only_see_own_tasks_on_event_task_endpoint(self):
        mine = self.create_task(assignee=self.attendee)
        self.create_task(title='Organizer private task')
        self.auth(self.attendee)
        response = self.client.get(self.event_tasks_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], mine.pk)

    def test_my_tasks_are_private_filtered_paginated_and_due_ordered(self):
        first = self.create_task(assignee=self.attendee, title='First', due_at=timezone.now() + timedelta(days=2))
        second = self.create_task(assignee=self.attendee, title='Second', due_at=timezone.now() + timedelta(days=1))
        self.register(self.event, self.other)
        self.create_task(assignee=self.other, title='Other user task')
        self.auth(self.attendee)
        response = self.client.get('/api/tasks/my/', {'page_size': 1})
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(response.data['results'][0]['id'], second.pk)
        self.assertIsNotNone(response.data['next'])
        self.assertEqual(self.client.get('/api/tasks/my/', {'status': 'todo'}).data['count'], 2)
        self.assertEqual(self.client.get('/api/tasks/my/', {'priority': 'medium'}).data['count'], 2)
        self.assertEqual(self.client.get('/api/tasks/my/', {'priority': 'bad'}).status_code, 400)
        self.assertNotEqual(first.pk, second.pk)

    def test_due_dates_require_timezone_and_overdue_is_derived(self):
        self.auth(self.organizer)
        payload = {'title': 'Follow up', 'description': 'Send event follow-up.'}
        naive = self.client.post(
            self.event_tasks_url(), {**payload, 'due_at': '2030-04-30T10:00:00'}, format='json'
        )
        malformed = self.client.post(
            self.event_tasks_url(), {**payload, 'due_at': 'not a date'}, format='json'
        )
        self.assertEqual(naive.status_code, 400)
        self.assertEqual(malformed.status_code, 400)

        overdue = self.create_task(due_at=timezone.now() - timedelta(days=1))
        done = self.create_task(due_at=timezone.now() - timedelta(days=1))
        done.status = TaskStatus.IN_PROGRESS
        done.save()
        done.status = TaskStatus.COMPLETED
        done.save()
        self.assertTrue(overdue.is_overdue)
        self.assertFalse(done.is_overdue)

