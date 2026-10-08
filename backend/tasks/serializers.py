from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from backend.events.models import Event, EventRegistration
from .models import Task, TaskPriority, TaskStatus


User = get_user_model()


class AwareDateTimeField(serializers.DateTimeField):
    default_error_messages = {
        'timezone': 'Include a timezone in the datetime, such as Z or +05:30.'
    }

    def to_internal_value(self, value):
        if value is not None:
            parsed = value if hasattr(value, 'tzinfo') else parse_datetime(str(value))
            if parsed is not None and timezone.is_naive(parsed):
                self.fail('timezone')
        return super().to_internal_value(value)


class TaskSerializer(serializers.ModelSerializer):
    event = serializers.IntegerField(source='event_id', read_only=True)
    event_title = serializers.CharField(source='event.title', read_only=True)
    assignee = serializers.SerializerMethodField()
    assignee_id = serializers.PrimaryKeyRelatedField(
        source='assignee', queryset=User.objects.all(),
        required=False, allow_null=True, write_only=True,
    )
    due_at = AwareDateTimeField(required=False, allow_null=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Task
        fields = (
            'id', 'event', 'event_title', 'title', 'description', 'status',
            'priority', 'assignee', 'assignee_id', 'due_at', 'created_at',
            'updated_at', 'is_overdue',
        )
        read_only_fields = ('id', 'event', 'event_title', 'assignee', 'created_at', 'updated_at', 'is_overdue')
        extra_kwargs = {
            'title': {'max_length': 200},
            'status': {'required': False},
            'priority': {'required': False},
        }

    def get_assignee(self, task):
        user = task.assignee
        if user is None:
            return None
        return {
            'id': user.pk,
            'username': user.get_username(),
            'first_name': user.first_name,
            'last_name': user.last_name,
        }

    def validate(self, attrs):
        request = self.context['request']
        protected = {
            'id', 'event', 'event_id', 'event_title', 'organizer', 'owner',
            'created_at', 'updated_at', 'is_overdue', 'assignee',
        }.intersection(self.initial_data)
        if protected:
            raise serializers.ValidationError({
                key: 'This field is controlled by the server.' for key in sorted(protected)
            })
        allowed = {'title', 'description', 'status', 'priority', 'assignee_id', 'due_at'}
        unexpected = set(self.initial_data) - allowed
        if unexpected:
            raise serializers.ValidationError({
                key: 'Unexpected or protected field.' for key in sorted(unexpected)
            })

        event = self.instance.event if self.instance else self.context['event']
        if self.instance is None and event.status in (Event.Status.CANCELLED, Event.Status.COMPLETED):
            raise serializers.ValidationError({'event': 'Tasks cannot be created for a terminal event.'})

        status_value = attrs.get('status', self.instance.status if self.instance else TaskStatus.TODO)
        if self.instance is None and status_value != TaskStatus.TODO:
            raise serializers.ValidationError({'status': 'New tasks must start as todo.'})
        is_manager = request.user.is_staff or event.organizer_id == request.user.pk
        if self.instance and status_value != self.instance.status:
            allowed_next = Task.ALLOWED_TRANSITIONS[self.instance.status]
            if status_value not in allowed_next:
                raise serializers.ValidationError({
                    'status': f'Cannot transition from {self.instance.status} to {status_value}.'
                })
            if self.instance.assignee_id == request.user.pk and not is_manager and (
                status_value not in (TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED)
            ):
                raise serializers.ValidationError({
                    'status': 'Assignees may only start or complete their task.'
                })

        if self.instance and self.instance.assignee_id == request.user.pk and not is_manager:
            if set(self.initial_data) - {'status'}:
                raise serializers.ValidationError(
                    'Assignees may update only their task status.'
                )

        assignee = attrs.get('assignee', serializers.empty)
        if assignee is not serializers.empty and assignee is not None:
            if not assignee.is_active:
                raise serializers.ValidationError({'assignee_id': 'The assignee account must be active.'})
            registered = EventRegistration.objects.filter(
                event=event,
                user=assignee,
                status=EventRegistration.Status.REGISTERED,
            ).exists()
            if not registered:
                raise serializers.ValidationError({
                    'assignee_id': 'The assignee must have an active registration for this event.'
                })

        for key in ('title', 'description'):
            value = attrs.get(key)
            if value is not None and not value.strip():
                raise serializers.ValidationError({key: 'This field cannot be blank.'})
        return attrs

    def create(self, validated_data):
        event = validated_data.pop('event', self.context['event'])
        try:
            return Task.objects.create(event=event, **validated_data)
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                error.message_dict if hasattr(error, 'message_dict') else error.messages
            )

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        try:
            instance.save()
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict if hasattr(error, 'message_dict') else error.messages)
        return instance
