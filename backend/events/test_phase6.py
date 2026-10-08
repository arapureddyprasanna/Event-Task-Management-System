from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from backend.accounts.models import Profile
from .models import Event, EventRegistration


User = get_user_model()


class EventRegistrationTests(TestCase):
    password = 'Complex#Pass987!'

    def setUp(self):
        self.client = APIClient()
        self.organizer = self.create_user('organizer')
        self.user = self.create_user('attendee')
        self.other = self.create_user('other')
        self.unverified = self.create_user('unverified', verified=False)
        self.inactive = self.create_user('inactive', active=False)
        self.staff = self.create_user('staff', staff=True)

    def create_user(self, name, verified=True, active=True, staff=False):
        user = User.objects.create_user(
            username=name, email=f'{name}@example.com', password=self.password,
            is_active=active, is_staff=staff,
        )
        Profile.objects.create(
            user=user, is_email_verified=verified,
            role=Profile.Role.ADMIN if staff else Profile.Role.USER,
        )
        return user

    def create_event(self, *, status=Event.Status.PUBLISHED, capacity=3):
        event = Event.objects.create(
            title='Community meetup', description='A local event.',
            organizer=self.organizer, location='Central Hall',
            start_at=datetime(2030, 5, 1, 10, tzinfo=timezone.utc),
            end_at=datetime(2030, 5, 1, 12, tzinfo=timezone.utc),
            capacity=capacity,
        )
        if status != Event.Status.DRAFT:
            event.status = Event.Status.PUBLISHED
            event.save()
        if status not in (Event.Status.DRAFT, Event.Status.PUBLISHED):
            event.status = status
            event.save()
        return event

    def auth(self, user):
        self.client.force_authenticate(user)

    def register(self, event, body=None):
        return self.client.post(
            f'/api/events/{event.pk}/register/', body or {}, format='json'
        )

    def test_model_fields_constraints_choices_and_timestamps(self):
        event = self.create_event()
        registration = EventRegistration.objects.create(event=event, user=self.user)
        self.assertEqual(registration.status, EventRegistration.Status.REGISTERED)
        self.assertIsNotNone(registration.registered_at.tzinfo)
        self.assertIsNotNone(registration.updated_at.tzinfo)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EventRegistration.objects.create(event=event, user=self.user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EventRegistration.objects.create(event=event, user=self.other, status='invalid')

    def test_register_authentication_verification_and_active_account(self):
        event = self.create_event()
        self.assertEqual(self.register(event).status_code, 401)
        self.assertFalse(EventRegistration.objects.filter(event=event).exists())
        for user in (self.unverified, self.inactive):
            self.auth(user)
            self.assertEqual(self.register(event).status_code, 403)
        self.auth(self.staff)
        self.assertEqual(self.register(event).status_code, 201)

    def test_only_published_events_accept_registrations(self):
        self.auth(self.user)
        for state in (Event.Status.DRAFT, Event.Status.CANCELLED, Event.Status.COMPLETED):
            event = self.create_event(status=state)
            self.assertEqual(self.register(event).status_code, 400)
        event = self.create_event()
        self.assertEqual(self.register(event).status_code, 201)

    def test_client_cannot_impersonate_or_forge_registration_fields(self):
        event = self.create_event()
        self.auth(self.user)
        response = self.register(event, {
            'user_id': self.other.pk, 'status': 'cancelled',
            'event_id': event.pk + 20, 'registered_at': '2020-01-01T00:00:00Z',
        })
        self.assertEqual(response.status_code, 201)
        registration = EventRegistration.objects.get(event=event)
        self.assertEqual(registration.user, self.user)
        self.assertEqual(registration.status, EventRegistration.Status.REGISTERED)
        self.assertEqual(response.data['user_id'], self.user.pk)
        self.assertNotIn('password', response.data)

        admin_event = self.create_event()
        self.auth(self.staff)
        admin_response = self.register(admin_event, {'user_id': self.other.pk})
        self.assertEqual(admin_response.status_code, 201)
        self.assertEqual(
            EventRegistration.objects.get(event=admin_event).user,
            self.staff,
        )
        self.assertEqual(admin_response.data['user_id'], self.staff.pk)

    def test_duplicate_is_conflict_and_unique_constraint_is_database_enforced(self):
        event = self.create_event()
        self.auth(self.user)
        self.assertEqual(self.register(event).status_code, 201)
        duplicate = self.register(event)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(EventRegistration.objects.filter(event=event, user=self.user).count(), 1)

    def test_unlimited_capacity_and_full_capacity(self):
        self.auth(self.user)
        unlimited = self.create_event(capacity=None)
        self.assertEqual(self.register(unlimited).status_code, 201)
        limited = self.create_event(capacity=1)
        self.assertEqual(self.register(limited).status_code, 201)
        self.auth(self.other)
        self.assertEqual(self.register(limited).status_code, 409)

    def test_cancel_frees_capacity_and_reregistration_reuses_record(self):
        event = self.create_event(capacity=1)
        self.auth(self.user)
        created = self.register(event)
        registration_id = created.data['id']
        cancelled = self.client.post(f'/api/events/{event.pk}/register/cancel/')
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.data['status'], EventRegistration.Status.CANCELLED)
        self.auth(self.other)
        self.assertEqual(self.register(event).status_code, 201)
        self.auth(self.user)
        self.assertEqual(self.register(event).status_code, 409)
        self.auth(self.other)
        self.client.post(f'/api/events/{event.pk}/register/cancel/')
        self.auth(self.user)
        reactivated = self.register(event)
        self.assertEqual(reactivated.status_code, 201)
        self.assertEqual(reactivated.data['id'], registration_id)
        self.assertEqual(EventRegistration.objects.filter(event=event, user=self.user).count(), 1)

    def test_user_cannot_cancel_another_users_registration_or_missing_registration(self):
        event = self.create_event()
        EventRegistration.objects.create(event=event, user=self.user)
        self.auth(self.other)
        self.assertEqual(
            self.client.post(f'/api/events/{event.pk}/register/cancel/').status_code, 404
        )
        self.auth(self.user)
        self.assertEqual(
            self.client.post(f'/api/events/{event.pk}/register/cancel/').data['status'],
            EventRegistration.Status.CANCELLED,
        )

    def test_my_registrations_is_private_filtered_paginated_and_ordered(self):
        first = self.create_event()
        second = self.create_event()
        EventRegistration.objects.create(event=first, user=self.user)
        EventRegistration.objects.create(event=second, user=self.user, status='cancelled')
        EventRegistration.objects.create(event=self.create_event(), user=self.other)
        self.auth(self.user)
        response = self.client.get('/api/events/my-registrations/', {'page_size': 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['results']), 1)
        self.assertIsNotNone(response.data['next'])
        self.assertEqual(response.data['results'][0]['event']['id'], second.pk)
        filtered = self.client.get('/api/events/my-registrations/', {'status': 'cancelled'})
        self.assertEqual(filtered.data['count'], 1)
        self.assertEqual(self.client.get('/api/events/my-registrations/', {'status': 'bad'}).status_code, 400)

    def test_organizer_and_staff_can_view_safe_attendee_records(self):
        event = self.create_event()
        EventRegistration.objects.create(event=event, user=self.user)
        self.auth(self.organizer)
        response = self.client.get(f'/api/events/{event.pk}/registrations/')
        self.assertEqual(response.status_code, 200)
        attendee = response.data['results'][0]['attendee']
        self.assertEqual(attendee['id'], self.user.pk)
        self.assertNotIn('email', attendee)
        self.assertNotIn('password', attendee)
        self.auth(self.other)
        self.assertEqual(self.client.get(f'/api/events/{event.pk}/registrations/').status_code, 403)
        self.auth(self.staff)
        self.assertEqual(self.client.get(f'/api/events/{event.pk}/registrations/').status_code, 200)

