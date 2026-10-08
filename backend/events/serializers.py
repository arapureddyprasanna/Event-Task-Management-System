from rest_framework import serializers
from django.utils import timezone

from .models import Event, EventRegistration


def active_registration_count(event):
    if hasattr(event, 'active_registration_count'):
        return event.active_registration_count
    return event.registrations.filter(
        status=EventRegistration.Status.REGISTERED
    ).count()


def event_availability(event, registration_count=None):
    if event.status == Event.Status.DRAFT:
        return 'unpublished'
    if event.status == Event.Status.CANCELLED:
        return 'cancelled'
    if event.status == Event.Status.COMPLETED or event.start_at <= timezone.now():
        return 'registration_closed'
    if registration_count is None:
        registration_count = active_registration_count(event)
    if event.capacity is not None and registration_count >= event.capacity:
        return 'full'
    return 'available'


class EventSerializer(serializers.ModelSerializer):
    organizer = serializers.SerializerMethodField()
    registration_count = serializers.SerializerMethodField()
    remaining_seats = serializers.SerializerMethodField()
    availability = serializers.SerializerMethodField()
    status = serializers.ChoiceField(choices=Event.Status.choices, required=False)

    class Meta:
        model = Event
        fields = (
            'id',
            'title',
            'description',
            'organizer',
            'location',
            'start_at',
            'end_at',
            'status',
            'capacity',
            'registration_count',
            'remaining_seats',
            'availability',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'organizer', 'created_at', 'updated_at')
        extra_kwargs = {
            'title': {'max_length': 200},
            'location': {'max_length': 255},
            'capacity': {'allow_null': True, 'required': False, 'min_value': 1},
        }

    def get_organizer(self, event):
        user = event.organizer
        return {
            'id': user.pk,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
        }

    @staticmethod
    def get_registration_count(event):
        return active_registration_count(event)

    def get_remaining_seats(self, event):
        if event.capacity is None:
            return None
        return max(0, event.capacity - self.get_registration_count(event))

    def get_availability(self, event):
        return event_availability(event)

    def validate(self, attrs):
        protected = {
            'id', 'organizer', 'organizer_id', 'owner', 'created_at', 'updated_at',
            'permissions',
        }.intersection(self.initial_data)
        if protected:
            raise serializers.ValidationError({
                field: 'This field is controlled by the server.'
                for field in sorted(protected)
            })
        unknown = set(self.initial_data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({
                field: 'Unexpected or protected field.' for field in sorted(unknown)
            })
        if self.instance is None and 'status' in self.initial_data:
            raise serializers.ValidationError({
                'status': 'New events are created as drafts.'
            })

        start_at = attrs.get(
            'start_at', getattr(self.instance, 'start_at', None)
        )
        end_at = attrs.get('end_at', getattr(self.instance, 'end_at', None))
        if start_at is not None and end_at is not None and end_at <= start_at:
            raise serializers.ValidationError({
                'end_at': 'End time must be after start time.'
            })

        if self.instance is not None:
            self._validate_status_transition(attrs)
            if self.instance.status in (Event.Status.CANCELLED, Event.Status.COMPLETED):
                if attrs:
                    raise serializers.ValidationError(
                        'Cancelled or completed events cannot be edited.'
                    )
        return attrs

    def _validate_status_transition(self, attrs):
        next_status = attrs.get('status', self.instance.status)
        current_status = self.instance.status
        if next_status == current_status:
            return

        if next_status not in Event.ALLOWED_TRANSITIONS[current_status]:
            raise serializers.ValidationError({
                'status': f'Cannot transition from {current_status} to {next_status}.'
            })
        request = self.context.get('request')
        if next_status == Event.Status.COMPLETED and not request.user.is_staff:
            raise serializers.ValidationError({
                'status': 'Only an admin may mark an event as completed.'
            })


class EventRegistrationSerializer(serializers.ModelSerializer):
    event = serializers.SerializerMethodField()

    class Meta:
        model = EventRegistration
        fields = ('id', 'event', 'user_id', 'status', 'registered_at', 'updated_at')
        read_only_fields = fields

    def get_event(self, registration):
        event = registration.event
        if hasattr(registration, 'event_active_registration_count'):
            registration_count = registration.event_active_registration_count
        else:
            registration_count = active_registration_count(event)
        return {
            'id': event.pk,
            'title': event.title,
            'location': event.location,
            'start_at': event.start_at,
            'end_at': event.end_at,
            'status': event.status,
            'capacity': event.capacity,
            'registration_count': registration_count,
            'remaining_seats': (
                None if event.capacity is None
                else max(0, event.capacity - registration_count)
            ),
            'availability': event_availability(event, registration_count),
        }


class OrganizerRegistrationSerializer(serializers.ModelSerializer):
    attendee = serializers.SerializerMethodField()

    class Meta:
        model = EventRegistration
        fields = ('id', 'event_id', 'attendee', 'status', 'registered_at', 'updated_at')
        read_only_fields = fields

    def get_attendee(self, registration):
        user = registration.user
        return {
            'id': user.pk,
            'username': user.get_username(),
            'first_name': user.first_name,
            'last_name': user.last_name,
        }
