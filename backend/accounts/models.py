import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Profile(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ADMIN = 'admin', 'Admin'

    user = models.OneToOneField(
        'auth.User', on_delete=models.CASCADE, related_name='profile'
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)
    is_email_verified = models.BooleanField(default=False)
    registration_demo_access = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('user_id',)

    def clean(self):
        super().clean()
        if self.role == self.Role.ADMIN and self.user_id:
            is_staff = type(self.user).objects.filter(pk=self.user_id, is_staff=True).exists()
            if not is_staff:
                raise ValidationError({'role': 'Admin role requires a staff account.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.user} profile'


class AdminAccessRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admin_access_requests',
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='reviewed_admin_access_requests',
        null=True,
        blank=True,
    )
    decision_reason = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at', '-pk')
        indexes = [
            models.Index(
                fields=('status', '-created_at'),
                name='acct_admreq_status_dt_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=('pending', 'approved', 'rejected')),
                name='accounts_admin_request_status_valid',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status='pending', reviewed_at__isnull=True)
                    | models.Q(
                        status__in=('approved', 'rejected'),
                        reviewed_at__isnull=False,
                    )
                ),
                name='accounts_admin_request_reviewed_at_valid',
            ),
            models.UniqueConstraint(
                fields=('requester',),
                condition=models.Q(status='pending'),
                name='accounts_one_pending_admin_request',
            ),
        ]

    def __str__(self):
        return f'{self.requester} — admin access ({self.status})'


class Notification(models.Model):
    class Category(models.TextChoices):
        EVENT_REGISTRATION = 'event_registration', 'Event registration'
        REGISTRATION_CANCELLED = 'registration_cancelled', 'Registration cancelled'
        TASK_ASSIGNED = 'task_assigned', 'Task assigned'
        TASK_UPDATED = 'task_updated', 'Task updated'
        ADMIN_ACCESS_REQUEST = 'admin_access_request', 'Admin access request'
        ADMIN_ACCESS_APPROVED = 'admin_access_approved', 'Admin access approved'
        ADMIN_ACCESS_REJECTED = 'admin_access_rejected', 'Admin access rejected'
        SYSTEM = 'system', 'System'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    category = models.CharField(max_length=32, choices=Category.choices)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    related_type = models.CharField(max_length=32, blank=True, default='')
    related_id = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-pk')
        indexes = [
            models.Index(
                fields=('recipient', 'is_read', '-created_at'),
                name='acct_notif_rec_read_dt',
            ),
            models.Index(
                fields=('recipient', '-created_at'),
                name='acct_notif_rec_dt_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(category__in=(
                    'event_registration', 'registration_cancelled', 'task_assigned',
                    'task_updated', 'admin_access_request', 'admin_access_approved',
                    'admin_access_rejected', 'system',
                )),
                name='accounts_notification_category_valid',
            ),
        ]

    def __str__(self):
        return f'{self.recipient}: {self.title}'


class Activity(models.Model):
    class Action(models.TextChoices):
        USER_REGISTERED_FOR_EVENT = 'user_registered_for_event', 'User registered for event'
        REGISTRATION_CANCELLED = 'registration_cancelled', 'Registration cancelled'
        TASK_CREATED = 'task_created', 'Task created'
        TASK_ASSIGNED = 'task_assigned', 'Task assigned'
        TASK_UPDATED = 'task_updated', 'Task updated'
        TASK_STATUS_CHANGED = 'task_status_changed', 'Task status changed'
        ADMIN_ACCESS_REQUESTED = 'admin_access_requested', 'Admin access requested'
        ADMIN_ACCESS_APPROVED = 'admin_access_approved', 'Admin access approved'
        ADMIN_ACCESS_REJECTED = 'admin_access_rejected', 'Admin access rejected'

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='activities',
        null=True,
        blank=True,
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='activity_targets',
        null=True,
        blank=True,
    )
    target_event = models.ForeignKey(
        'events.Event',
        on_delete=models.SET_NULL,
        related_name='activities',
        null=True,
        blank=True,
    )
    target_task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.SET_NULL,
        related_name='activities',
        null=True,
        blank=True,
    )
    target_registration = models.ForeignKey(
        'events.EventRegistration',
        on_delete=models.SET_NULL,
        related_name='activities',
        null=True,
        blank=True,
    )
    action_type = models.CharField(max_length=32, choices=Action.choices)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-pk')
        indexes = [
            models.Index(
                fields=('actor', '-created_at'),
                name='acct_activity_actor_dt',
            ),
            models.Index(
                fields=('target_user', '-created_at'),
                name='acct_activity_target_dt',
            ),
            models.Index(
                fields=('action_type', '-created_at'),
                name='acct_activity_action_dt',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(action_type__in=(
                    'user_registered_for_event', 'registration_cancelled', 'task_created',
                    'task_assigned', 'task_updated', 'task_status_changed',
                    'admin_access_requested', 'admin_access_approved',
                    'admin_access_rejected',
                )),
                name='accounts_activity_action_valid',
            ),
        ]

    def __str__(self):
        return self.description


class EmailOTP(models.Model):
    class Purpose(models.TextChoices):
        VERIFY_EMAIL = 'verify_email', 'Verify email'
        RESET_PASSWORD = 'reset_password', 'Reset password'

    CODE_LENGTH = 6
    EXPIRY_MINUTES = 10
    MAX_VERIFY_ATTEMPTS = 5
    MAX_RESENDS = 3

    email = models.EmailField(max_length=254, db_index=True)
    purpose = models.CharField(
        max_length=20,
        choices=Purpose.choices,
        default=Purpose.VERIFY_EMAIL,
    )
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        related_name='email_otps',
        null=True,
        blank=True,
    )
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField(db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_attempts = models.PositiveSmallIntegerField(default=0)
    resend_attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('email', '-created_at'), name='accounts_otp_email_created_idx'),
            models.Index(
                fields=('email', 'purpose', '-created_at'),
                name='acct_otp_email_purpose_dt_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(purpose__in=('verify_email', 'reset_password')),
                name='accounts_otp_purpose_valid',
            ),
            models.CheckConstraint(
                condition=Q(verification_attempts__lte=5),
                name='accounts_otp_verify_attempts_lte_max',
            ),
            models.CheckConstraint(
                condition=Q(resend_attempts__lte=3),
                name='accounts_otp_resend_attempts_lte_max',
            ),
        ]

    @staticmethod
    def _new_code():
        return f'{secrets.randbelow(10 ** EmailOTP.CODE_LENGTH):0{EmailOTP.CODE_LENGTH}d}'

    @classmethod
    def issue(cls, email, user=None, purpose=Purpose.VERIFY_EMAIL):
        """Create a challenge; return it with the one-time plaintext code for delivery."""
        email = email.strip().lower()
        validate_email(email)
        code = cls._new_code()
        otp = cls.objects.create(
            email=email,
            purpose=purpose,
            user=user,
            code_hash=make_password(code),
            expires_at=timezone.now() + timedelta(minutes=cls.EXPIRY_MINUTES),
        )
        return otp, code

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()
            validate_email(self.email)
        if self.user_id and self.email and self.user.email:
            if self.user.email.strip().lower() != self.email:
                raise ValidationError({'email': 'Email must match the associated user.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def verify(self, code):
        """Check a code, recording every attempt and consuming it on success."""
        if self.verified_at or self.expires_at <= timezone.now():
            return False
        if self.verification_attempts >= self.MAX_VERIFY_ATTEMPTS:
            return False
        self.verification_attempts += 1
        if check_password(str(code), self.code_hash):
            self.verified_at = timezone.now()
            self.save(update_fields=('verification_attempts', 'verified_at', 'updated_at'))
            return True
        self.save(update_fields=('verification_attempts', 'updated_at'))
        return False

    def resend(self):
        """Rotate the code and expiry, returning only the new code for delivery."""
        if self.verified_at:
            raise ValidationError('A verified challenge cannot be resent.')
        if self.resend_attempts >= self.MAX_RESENDS:
            raise ValidationError('Maximum resend attempts reached.')
        code = self._new_code()
        self.code_hash = make_password(code)
        self.expires_at = timezone.now() + timedelta(minutes=self.EXPIRY_MINUTES)
        self.resend_attempts += 1
        self.verification_attempts = 0
        self.save(update_fields=(
            'code_hash', 'expires_at', 'resend_attempts',
            'verification_attempts', 'updated_at',
        ))
        return code

    def __str__(self):
        return f'Email verification for {self.email}'
