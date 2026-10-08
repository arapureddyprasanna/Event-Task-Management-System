from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from backend.events.models import Event, EventRegistration


class TaskStatus(models.TextChoices):
    TODO = 'todo', 'To do'
    IN_PROGRESS = 'in_progress', 'In progress'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


class TaskPriority(models.TextChoices):
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'


class Task(models.Model):
    Status = TaskStatus
    Priority = TaskPriority

    ALLOWED_TRANSITIONS = {
        Status.TODO: {Status.IN_PROGRESS, Status.CANCELLED},
        Status.IN_PROGRESS: {Status.TODO, Status.COMPLETED, Status.CANCELLED},
        Status.COMPLETED: set(),
        Status.CANCELLED: set(),
    }

    event = models.ForeignKey(
        Event, on_delete=models.PROTECT, related_name='tasks'
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.TODO
    )
    priority = models.CharField(
        max_length=8, choices=Priority.choices, default=Priority.MEDIUM
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='assigned_event_tasks',
        null=True,
        blank=True,
    )
    due_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('due_at', 'pk')
        indexes = [
            models.Index(fields=('event', 'status'), name='tasks_event_status_idx'),
            models.Index(fields=('assignee', 'status'), name='tasks_assignee_status_idx'),
            models.Index(fields=('due_at',), name='tasks_due_at_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=('todo', 'in_progress', 'completed', 'cancelled')),
                name='tasks_status_valid',
            ),
            models.CheckConstraint(
                condition=Q(priority__in=('low', 'medium', 'high', 'urgent')),
                name='tasks_priority_valid',
            ),
        ]

    def clean(self):
        super().clean()
        if self.title is not None and not self.title.strip():
            raise ValidationError({'title': 'This field cannot be blank.'})
        if self.description is not None and not self.description.strip():
            raise ValidationError({'description': 'This field cannot be blank.'})
        if self.due_at is not None and timezone.is_naive(self.due_at):
            raise ValidationError({'due_at': 'A timezone-aware datetime is required.'})

        if self._state.adding:
            if self.status != self.Status.TODO:
                raise ValidationError({'status': 'New tasks must start as todo.'})
            if self.event_id and self.event.status in (Event.Status.CANCELLED, Event.Status.COMPLETED):
                raise ValidationError({'event': 'Tasks cannot be created for a terminal event.'})
        else:
            existing = type(self).objects.filter(pk=self.pk).values(
                'status', 'event_id', 'assignee_id'
            ).first()
            if existing:
                if self.status != existing['status'] and self.status not in self.ALLOWED_TRANSITIONS[
                    existing['status']
                ]:
                    raise ValidationError({
                        'status': f"Cannot transition from {existing['status']} to {self.status}."
                    })
                if self.event_id != existing['event_id']:
                    raise ValidationError({'event': 'A task cannot be moved to another event.'})

        assignment_changed = self._state.adding or (
            not self._state.adding
            and existing
            and self.assignee_id != existing['assignee_id']
        )
        if self.assignee_id and assignment_changed:
            if not self.assignee.is_active:
                raise ValidationError({'assignee': 'The assignee account must be active.'})
            if not EventRegistration.objects.filter(
                event_id=self.event_id,
                user_id=self.assignee_id,
                status=EventRegistration.Status.REGISTERED,
            ).exists():
                raise ValidationError({
                    'assignee': 'The assignee must have an active registration for this event.'
                })

    @property
    def is_overdue(self):
        return bool(
            self.due_at
            and self.due_at < timezone.now()
            and self.status not in (self.Status.COMPLETED, self.Status.CANCELLED)
        )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title
