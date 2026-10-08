from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


class EventStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    PUBLISHED = 'published', 'Published'
    CANCELLED = 'cancelled', 'Cancelled'
    COMPLETED = 'completed', 'Completed'


class Event(models.Model):
    Status = EventStatus

    ALLOWED_TRANSITIONS = {
        Status.DRAFT: {Status.PUBLISHED},
        Status.PUBLISHED: {Status.CANCELLED, Status.COMPLETED},
        Status.CANCELLED: set(),
        Status.COMPLETED: set(),
    }

    title = models.CharField(max_length=200)
    description = models.TextField()
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='organized_events',
    )
    location = models.CharField(max_length=255)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=(MinValueValidator(1),),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('start_at', 'pk')
        indexes = [
            models.Index(fields=('status', 'start_at'), name='events_status_start_idx'),
            models.Index(fields=('organizer', 'status'), name='events_org_status_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_at__gt=F('start_at')),
                name='events_end_after_start',
            ),
            models.CheckConstraint(
                condition=Q(capacity__isnull=True) | Q(capacity__gte=1),
                name='events_capacity_positive_or_null',
            ),
            models.CheckConstraint(
                condition=Q(status__in=EventStatus.values),
                name='events_status_valid',
            ),
        ]

    def clean(self):
        super().clean()
        for field in ('title', 'description', 'location'):
            value = getattr(self, field)
            if value is not None and not value.strip():
                raise ValidationError({field: 'This field cannot be blank.'})
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValidationError({'end_at': 'End time must be after start time.'})
        if self.capacity is not None and self.capacity < 1:
            raise ValidationError({'capacity': 'Capacity must be at least 1.'})
        if self.status not in self.Status.values:
            raise ValidationError({'status': 'Choose a supported event status.'})
        if self._state.adding and self.status != self.Status.DRAFT:
            raise ValidationError({'status': 'New events must start as drafts.'})
        if self.pk:
            existing = type(self).objects.filter(pk=self.pk).values(
                'status', 'title', 'description', 'location', 'start_at', 'end_at',
                'capacity',
            ).first()
            if existing:
                if self.status != existing['status'] and self.status not in self.ALLOWED_TRANSITIONS[
                    existing['status']
                ]:
                    raise ValidationError({
                        'status': f"Cannot transition from {existing['status']} to {self.status}."
                    })
                if existing['status'] in (self.Status.CANCELLED, self.Status.COMPLETED):
                    changed_fields = (
                        'title', 'description', 'location', 'start_at', 'end_at', 'capacity'
                    )
                    if any(getattr(self, field) != existing[field] for field in changed_fields):
                        raise ValidationError(
                            'Cancelled or completed events cannot be edited.'
                        )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class EventRegistration(models.Model):
    class Status(models.TextChoices):
        REGISTERED = 'registered', 'Registered'
        CANCELLED = 'cancelled', 'Cancelled'

    event = models.ForeignKey(
        Event, on_delete=models.PROTECT, related_name='registrations'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='event_registrations',
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.REGISTERED
    )
    registered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-registered_at', '-pk')
        constraints = [
            models.UniqueConstraint(fields=('event', 'user'), name='event_registration_unique_user'),
            models.CheckConstraint(
                condition=Q(status__in=('registered', 'cancelled')),
                name='event_registration_status_valid',
            ),
        ]
        indexes = [models.Index(fields=('user', 'status', '-registered_at'), name='event_reg_user_status_idx')]

    def __str__(self):
        return f'{self.user_id} — {self.event_id} ({self.status})'
