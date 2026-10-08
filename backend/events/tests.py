from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from backend.accounts.models import Profile
from .models import Event


User = get_user_model()


class EventModelTests(TestCase):
    def setUp(self):
        self.organizer = self.create_user('organizer', 'organizer@example.com')

    @staticmethod
    def create_user(username, email, *, verified=True, is_staff=False, is_active=True):
        user = User.objects.create_user(
            username=username,
            email=email,
            password='Complex#Pass987!',
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
    def event_values(**overrides):
        values = {
            'title': 'Community meetup',
            'description': 'A local community event.',
            'location': 'Central Hall',
            'start_at': datetime(2030, 5, 1, 10, tzinfo=timezone.utc),
            'end_at': datetime(2030, 5, 1, 12, tzinfo=timezone.utc),
            'capacity': 80,
        }
        values.update(overrides)
        return values

    def create_event(self, **overrides):
        return Event.objects.create(
            organizer=self.organizer,
            **self.event_values(**overrides),
        )

    def test_valid_event_defaults_to_draft_and_references_existing_user(self):
        event = self.create_event()

        self.assertEqual(event.status, Event.Status.DRAFT)
        self.assertEqual(event.organizer, self.organizer)
        self.assertEqual(self.organizer.organized_events.get(), event)
        self.assertTrue(event.created_at.tzinfo)
        self.assertTrue(event.updated_at.tzinfo)

    def test_end_must_follow_start(self):
        with self.assertRaises(ValidationError):
            self.create_event(
                end_at=datetime(2030, 5, 1, 10, tzinfo=timezone.utc)
            )

    def test_capacity_must_be_positive_or_null(self):
        with self.assertRaises(ValidationError):
            self.create_event(capacity=0)

        event = self.create_event(capacity=None)
        self.assertIsNone(event.capacity)

    def test_only_supported_statuses_and_draft_creation_are_allowed(self):
        with self.assertRaises(ValidationError):
            self.create_event(status='private')
        with self.assertRaises(ValidationError):
            self.create_event(status=Event.Status.PUBLISHED)

    def test_blank_required_text_fields_are_rejected(self):
        for field in ('title', 'description', 'location'):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.create_event(**{field: '   '})

    def test_invalid_lifecycle_transition_and_terminal_edits_are_rejected(self):
        event = self.create_event()
        event.status = Event.Status.CANCELLED
        with self.assertRaises(ValidationError):
            event.save()

        event = self.create_event()
        event.status = Event.Status.PUBLISHED
        event.save()
        event.status = Event.Status.CANCELLED
        event.save()
        event.title = 'Changed after cancellation'
        with self.assertRaises(ValidationError):
            event.save()


class EventAPITests(TestCase):
    collection_url = '/api/events/'
    password = 'Complex#Pass987!'

    def setUp(self):
        self.client = APIClient()
        self.organizer = self.create_user('organizer', 'organizer@example.com')
        self.other = self.create_user('other', 'other@example.com')
        self.unverified = self.create_user(
            'unverified', 'unverified@example.com', verified=False
        )
        self.inactive = self.create_user(
            'inactive', 'inactive@example.com', is_active=False
        )
        self.admin = self.create_user(
            'admin', 'admin@example.com', is_staff=True
        )

    def create_user(
        self, username, email, *, verified=True, is_staff=False, is_active=True
    ):
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
    def event_values(**overrides):
        values = {
            'title': 'Community meetup',
            'description': 'A local community event.',
            'location': 'Central Hall',
            'start_at': '2030-05-01T10:00:00Z',
            'end_at': '2030-05-01T12:00:00Z',
            'capacity': 80,
        }
        values.update(overrides)
        return values

    def api_event(self, organizer=None, status=Event.Status.DRAFT, **overrides):
        values = self.event_values(**overrides)
        return Event.objects.create(
            organizer=organizer or self.organizer,
            status=status,
            **values,
        ) if status == Event.Status.DRAFT else self._create_lifecycle_event(
            organizer or self.organizer, status, values
        )

    @staticmethod
    def _create_lifecycle_event(organizer, final_status, values):
        event = Event.objects.create(
            organizer=organizer,
            **{
                **values,
                'start_at': datetime(2030, 5, 1, 10, tzinfo=timezone.utc),
                'end_at': datetime(2030, 5, 1, 12, tzinfo=timezone.utc),
            },
        )
        event.status = Event.Status.PUBLISHED
        event.save()
        if final_status != Event.Status.PUBLISHED:
            event.status = final_status
            event.save()
        return event

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_create_requires_verified_active_authentication(self):
        payload = self.event_values()

        self.assertEqual(
            self.client.post(self.collection_url, payload, format='json').status_code,
            401,
        )
        self.authenticate(self.unverified)
        self.assertEqual(
            self.client.post(self.collection_url, payload, format='json').status_code,
            403,
        )
        self.authenticate(self.inactive)
        self.assertEqual(
            self.client.post(self.collection_url, payload, format='json').status_code,
            403,
        )

    def test_verified_user_creates_draft_owned_by_request_user(self):
        self.authenticate(self.organizer)

        response = self.client.post(
            self.collection_url, self.event_values(), format='json'
        )

        self.assertEqual(response.status_code, 201)
        event = Event.objects.get(pk=response.data['id'])
        self.assertEqual(event.organizer, self.organizer)
        self.assertEqual(event.status, Event.Status.DRAFT)
        self.assertEqual(response.data['organizer']['id'], self.organizer.pk)

    def test_client_cannot_assign_organizer_or_system_fields(self):
        self.authenticate(self.organizer)
        protected_values = (
            {'organizer': self.other.pk},
            {'organizer_id': self.other.pk},
            {'created_at': '2030-01-01T00:00:00Z'},
            {'updated_at': '2030-01-01T00:00:00Z'},
            {'permissions': ['admin']},
        )
        for protected in protected_values:
            with self.subTest(protected=protected):
                response = self.client.post(
                    self.collection_url,
                    {**self.event_values(), **protected},
                    format='json',
                )
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Event.objects.count(), 0)

    def test_creation_rejects_client_controlled_status_invalid_dates_and_capacity(self):
        self.authenticate(self.organizer)
        cases = (
            ({'status': Event.Status.PUBLISHED}, 'status'),
            ({'status': 'arbitrary'}, 'status'),
            ({'end_at': '2030-05-01T09:00:00Z'}, 'end_at'),
            ({'capacity': 0}, 'capacity'),
            ({'title': '   '}, 'title'),
            ({'location': '   '}, 'location'),
            ({'description': '   '}, 'description'),
        )
        for override, field in cases:
            with self.subTest(field=field, override=override):
                response = self.client.post(
                    self.collection_url,
                    {**self.event_values(), **override},
                    format='json',
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)

    def test_public_list_is_paginated_ordered_and_excludes_drafts(self):
        for index in range(21):
            event = self.api_event(title=f'Published {index:02d}')
            event.status = Event.Status.PUBLISHED
            event.save()
        self.api_event(title='Private draft')

        response = self.client.get(self.collection_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 21)
        self.assertEqual(len(response.data['results']), 20)
        self.assertIsNotNone(response.data['next'])
        self.assertEqual(
            [item['title'] for item in response.data['results']],
            sorted(item['title'] for item in response.data['results']),
        )
        self.assertNotIn('Private draft', [item['title'] for item in response.data['results']])

    def test_search_status_date_and_organizer_filters_are_server_side(self):
        matching = self.api_event(title='Python community conference')
        matching.status = Event.Status.PUBLISHED
        matching.save()
        other = self.api_event(organizer=self.other, title='Gardening fair')
        other.status = Event.Status.PUBLISHED
        other.save()

        search = self.client.get(self.collection_url, {'search': 'PYTHON'})
        status_filter = self.client.get(
            self.collection_url, {'status': Event.Status.PUBLISHED}
        )
        date_filter = self.client.get(
            self.collection_url, {'start_after': '2030-05-01T11:00:00Z'}
        )
        organizer_filter = self.client.get(
            self.collection_url, {'organizer': str(self.other.pk)}
        )
        invalid_status = self.client.get(self.collection_url, {'status': 'unknown'})
        invalid_date = self.client.get(self.collection_url, {'start_after': 'tomorrow'})

        self.assertEqual([row['id'] for row in search.data['results']], [matching.pk])
        self.assertEqual(status_filter.data['count'], 2)
        self.assertEqual(date_filter.data['count'], 0)
        self.assertEqual([row['id'] for row in organizer_filter.data['results']], [other.pk])
        self.assertEqual(invalid_status.status_code, 400)
        self.assertEqual(invalid_date.status_code, 400)

    def test_draft_visibility_is_owner_admin_only_and_public_lifecycle_is_historical(self):
        draft = self.api_event()
        published = self.api_event(title='Published')
        published.status = Event.Status.PUBLISHED
        published.save()
        cancelled = self.api_event(title='Cancelled', status=Event.Status.CANCELLED)
        completed = self.api_event(title='Completed', status=Event.Status.COMPLETED)

        self.assertEqual(self.client.get(f'{self.collection_url}{draft.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'{self.collection_url}{published.pk}/').status_code, 200)
        self.assertEqual(self.client.get(f'{self.collection_url}{cancelled.pk}/').status_code, 200)
        self.assertEqual(self.client.get(f'{self.collection_url}{completed.pk}/').status_code, 200)
        public_list = self.client.get(self.collection_url)
        self.assertEqual(public_list.data['count'], 3)

        self.authenticate(self.other)
        self.assertEqual(self.client.get(f'{self.collection_url}{draft.pk}/').status_code, 404)
        self.authenticate(self.organizer)
        self.assertEqual(self.client.get(f'{self.collection_url}{draft.pk}/').status_code, 200)
        self.authenticate(self.admin)
        self.assertEqual(self.client.get(f'{self.collection_url}{draft.pk}/').status_code, 200)

    def test_detail_representation_has_safe_organizer_without_account_secrets(self):
        event = self.api_event()
        event.status = Event.Status.PUBLISHED
        event.save()

        response = self.client.get(f'{self.collection_url}{event.pk}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['organizer']['id'], self.organizer.pk)
        self.assertNotIn('email', response.data['organizer'])
        self.assertFalse(
            {'password', 'user_permissions', 'groups', 'otp', 'token'}
            & set(response.data)
        )

    def test_owner_can_update_event_and_other_user_cannot(self):
        event = self.api_event()
        event.status = Event.Status.PUBLISHED
        event.save()
        self.authenticate(self.organizer)
        response = self.client.patch(
            f'{self.collection_url}{event.pk}/',
            {'title': 'Updated meetup'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'Updated meetup')

        self.authenticate(self.other)
        forbidden = self.client.patch(
            f'{self.collection_url}{event.pk}/',
            {'title': 'Unauthorized edit'},
            format='json',
        )
        self.assertEqual(forbidden.status_code, 403)
        event.refresh_from_db()
        self.assertEqual(event.title, 'Updated meetup')

    def test_admin_can_manage_another_organizers_event(self):
        event = self.api_event()
        self.authenticate(self.admin)

        response = self.client.patch(
            f'{self.collection_url}{event.pk}/',
            {'title': 'Admin update'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.title, 'Admin update')
        self.assertEqual(event.organizer, self.organizer)

    def test_owner_cannot_transfer_ownership_or_inject_status_on_create(self):
        event = self.api_event()
        self.authenticate(self.organizer)

        transfer = self.client.patch(
            f'{self.collection_url}{event.pk}/',
            {'organizer': self.other.pk},
            format='json',
        )
        self.assertEqual(transfer.status_code, 400)
        event.refresh_from_db()
        self.assertEqual(event.organizer, self.organizer)

    def test_update_revalidates_dates_and_status_transition(self):
        event = self.api_event()
        self.authenticate(self.organizer)

        invalid_dates = self.client.patch(
            f'{self.collection_url}{event.pk}/',
            {'end_at': '2030-05-01T09:00:00Z'},
            format='json',
        )
        cannot_cancel_draft = self.client.patch(
            f'{self.collection_url}{event.pk}/',
            {'status': Event.Status.CANCELLED},
            format='json',
        )
        self.assertEqual(invalid_dates.status_code, 400)
        self.assertEqual(cannot_cancel_draft.status_code, 400)

        publish = self.client.patch(
            f'{self.collection_url}{event.pk}/',
            {'status': Event.Status.PUBLISHED},
            format='json',
        )
        self.assertEqual(publish.status_code, 200)
        owner_cannot_complete = self.client.patch(
            f'{self.collection_url}{event.pk}/',
            {'status': Event.Status.COMPLETED},
            format='json',
        )
        self.assertEqual(owner_cannot_complete.status_code, 400)

    def test_admin_can_complete_and_cancel_and_terminal_events_cannot_be_edited(self):
        published = self.api_event(title='Published')
        published.status = Event.Status.PUBLISHED
        published.save()
        self.authenticate(self.admin)

        completed = self.client.patch(
            f'{self.collection_url}{published.pk}/',
            {'status': Event.Status.COMPLETED},
            format='json',
        )
        self.assertEqual(completed.status_code, 200)
        terminal_edit = self.client.patch(
            f'{self.collection_url}{published.pk}/',
            {'title': 'Not allowed'},
            format='json',
        )
        self.assertEqual(terminal_edit.status_code, 400)

        another = self.api_event(title='To cancel')
        another.status = Event.Status.PUBLISHED
        another.save()
        cancelled = self.client.patch(
            f'{self.collection_url}{another.pk}/',
            {'status': Event.Status.CANCELLED},
            format='json',
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.data['status'], Event.Status.CANCELLED)

    def test_deletion_is_disabled_in_favor_of_cancellation(self):
        event = self.api_event()
        self.authenticate(self.organizer)

        response = self.client.delete(f'{self.collection_url}{event.pk}/')

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Event.objects.filter(pk=event.pk).exists())

    def test_unverified_and_inactive_users_cannot_manage_even_their_own_events(self):
        event = self.api_event()
        for user in (self.unverified, self.inactive):
            self.authenticate(user)
            with self.subTest(user=user.username):
                response = self.client.patch(
                    f'{self.collection_url}{event.pk}/',
                    {'title': 'Not allowed'},
                    format='json',
                )
                self.assertEqual(response.status_code, 403)
