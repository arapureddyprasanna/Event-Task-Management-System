from django.db import IntegrityError, transaction
from rest_framework.exceptions import APIException, NotFound
from django.utils import timezone

from backend.accounts.models import Activity, Notification
from backend.accounts.services.activities import create_activity
from backend.accounts.services.notifications import create_notification
from .models import Event, EventRegistration


class DuplicateRegistration(APIException):
    status_code = 409
    default_detail = 'You are already registered for this event.'
    default_code = 'already_registered'


class EventNotOpen(APIException):
    status_code = 400
    default_detail = 'This event is not open for registration.'
    default_code = 'event_not_open'


class EventFull(APIException):
    status_code = 409
    default_detail = 'This event has reached capacity.'
    default_code = 'event_full'


def register_user(event_id, user):
    with transaction.atomic():
        try:
            event = Event.objects.select_for_update().get(pk=event_id)
        except Event.DoesNotExist:
            raise NotFound('Event not found.')

        if event.status != Event.Status.PUBLISHED:
            raise EventNotOpen()
        if event.start_at <= timezone.now():
            raise EventNotOpen('Registration is closed for this event.')

        registration = EventRegistration.objects.filter(
            event=event, user=user
        ).first()
        if registration and registration.status == EventRegistration.Status.REGISTERED:
            raise DuplicateRegistration()

        active_count = EventRegistration.objects.filter(
            event=event, status=EventRegistration.Status.REGISTERED
        ).count()
        if event.capacity is not None and active_count >= event.capacity:
            raise EventFull()

        if registration:
            registration.status = EventRegistration.Status.REGISTERED
            registration.save(update_fields=('status', 'updated_at'))
        else:
            try:
                with transaction.atomic():
                    registration = EventRegistration.objects.create(event=event, user=user)
            except IntegrityError:
                # The registration uniqueness constraint is the final guard against races.
                raise DuplicateRegistration() from None
        create_notification(
            user,
            Notification.Category.EVENT_REGISTRATION,
            'Event registration confirmed',
            f'You are registered for {event.title}.',
            related_type='event_registration',
            related_id=registration.pk,
        )
        create_activity(
            user,
            Activity.Action.USER_REGISTERED_FOR_EVENT,
            f'{user.get_username()} registered for {event.title}.',
            target_user=user,
            target_event=event,
            target_registration=registration,
        )
        return registration


def cancel_user_registration(event_id, user):
    with transaction.atomic():
        try:
            event = Event.objects.select_for_update().get(pk=event_id)
        except Event.DoesNotExist:
            raise NotFound('Event not found.')
        try:
            registration = EventRegistration.objects.select_for_update().get(
                event_id=event_id, user=user
            )
        except EventRegistration.DoesNotExist:
            raise NotFound('Registration not found.')
        if registration.status != EventRegistration.Status.CANCELLED:
            registration.status = EventRegistration.Status.CANCELLED
            registration.save(update_fields=('status', 'updated_at'))
            create_notification(
                user,
                Notification.Category.REGISTRATION_CANCELLED,
                'Event registration cancelled',
                f'Your registration for {event.title} was cancelled.',
                related_type='event_registration',
                related_id=registration.pk,
            )
            create_activity(
                user,
                Activity.Action.REGISTRATION_CANCELLED,
                f'{user.get_username()} cancelled registration for {event.title}.',
                target_user=user,
                target_event=event,
                target_registration=registration,
            )
        return registration
