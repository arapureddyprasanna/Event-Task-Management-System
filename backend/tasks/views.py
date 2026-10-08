from django.db import transaction
from django.db.models import F, Q
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from backend.accounts.permissions import IsVerifiedUser
from backend.accounts.models import Activity, Notification
from backend.accounts.services.activities import create_activity
from backend.accounts.services.notifications import create_notification
from backend.events.models import Event
from backend.events.permissions import EventOwnerOrAdmin
from .models import Task, TaskPriority, TaskStatus
from .permissions import TaskVisibleToUser
from .serializers import AwareDateTimeField, TaskSerializer


def safe_task_queryset():
    return Task.objects.select_related('event', 'assignee').only(
        'id', 'event_id', 'event__title', 'event__organizer_id', 'title', 'description', 'status',
        'priority', 'assignee_id', 'assignee__username', 'assignee__first_name',
        'assignee__last_name', 'due_at', 'created_at', 'updated_at',
    )


class TaskPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class TaskQueryMixin:
    def apply_filters(self, queryset):
        params = self.request.query_params
        search = params.get('search', '').strip()
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search))
        for param, field, choices in (
            ('status', 'status', TaskStatus.values),
            ('priority', 'priority', TaskPriority.values),
        ):
            value = params.get(param)
            if value:
                if value not in choices:
                    raise ValidationError({param: f'Choose a supported task {param}.'})
                queryset = queryset.filter(**{field: value})
        assignee_id = params.get('assignee')
        if assignee_id:
            if not assignee_id.isdecimal():
                raise ValidationError({'assignee': 'Enter a valid user ID.'})
            queryset = queryset.filter(assignee_id=int(assignee_id))
        for param, lookup in (
            ('due_after', 'due_at__gte'),
            ('due_before', 'due_at__lte'),
        ):
            raw_value = params.get(param)
            if raw_value:
                try:
                    value = AwareDateTimeField().run_validation(raw_value)
                except ValidationError:
                    raise ValidationError({param: 'Enter a valid timezone-aware ISO-8601 datetime.'})
                queryset = queryset.filter(**{lookup: value})
        return queryset


class EventTaskListCreateView(TaskQueryMixin, generics.ListCreateAPIView):
    serializer_class = TaskSerializer
    pagination_class = TaskPagination
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsVerifiedUser)

    def get_event(self):
        if not hasattr(self, '_task_event'):
            try:
                self._task_event = Event.objects.get(pk=self.kwargs['event_id'])
            except Event.DoesNotExist:
                raise NotFound('Event not found.')
        return self._task_event

    def get_queryset(self):
        event = self.get_event()
        user = self.request.user
        tasks = safe_task_queryset().filter(event=event)
        if user.is_staff or event.organizer_id == user.pk:
            pass
        elif tasks.filter(assignee_id=user.pk).exists():
            tasks = tasks.filter(assignee_id=user.pk)
        else:
            raise PermissionDenied('You cannot view tasks for this event.')
        return self.apply_filters(tasks).order_by(F('due_at').asc(nulls_last=True), 'pk')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['event'] = self.get_event()
        return context

    def create(self, request, *args, **kwargs):
        event = self.get_event()
        if not EventOwnerOrAdmin().has_object_permission(request, self, event):
            raise PermissionDenied('Only the event organizer or staff may create tasks.')
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        with transaction.atomic():
            task = serializer.save(event=self.get_event())
            create_activity(
                self.request.user,
                Activity.Action.TASK_CREATED,
                f'{self.request.user.get_username()} created task {task.title}.',
                target_user=task.assignee,
                target_event=task.event,
                target_task=task,
            )
            if task.assignee_id:
                create_activity(
                    self.request.user,
                    Activity.Action.TASK_ASSIGNED,
                    f'{task.title} was assigned to {task.assignee.get_username()}.',
                    target_user=task.assignee,
                    target_event=task.event,
                    target_task=task,
                )
                if task.assignee_id != self.request.user.pk:
                    create_notification(
                        task.assignee,
                        Notification.Category.TASK_ASSIGNED,
                        'A task was assigned to you',
                        f'{task.title} was assigned to you for {task.event.title}.',
                        related_type='task',
                        related_id=task.pk,
                    )


class TaskDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = TaskSerializer
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsVerifiedUser, TaskVisibleToUser)
    queryset = safe_task_queryset()
    http_method_names = ('get', 'patch', 'head', 'options')

    def perform_update(self, serializer):
        task = serializer.instance
        previous_assignee = task.assignee
        previous = {
            'title': task.title,
            'description': task.description,
            'status': task.status,
            'priority': task.priority,
            'assignee_id': task.assignee_id,
            'due_at': task.due_at,
        }
        with transaction.atomic():
            task = serializer.save()
            changed = {
                field: (value, getattr(task, field))
                for field, value in previous.items()
                if value != getattr(task, field)
            }
            if not changed:
                return

            if 'status' in changed:
                old_status, new_status = changed['status']
                create_activity(
                    self.request.user,
                    Activity.Action.TASK_STATUS_CHANGED,
                    f'{task.title} changed from {old_status} to {new_status}.',
                    target_user=task.assignee,
                    target_event=task.event,
                    target_task=task,
                )

            if 'assignee_id' in changed and task.assignee_id:
                create_activity(
                    self.request.user,
                    Activity.Action.TASK_ASSIGNED,
                    f'{task.title} was assigned to {task.assignee.get_username()}.',
                    target_user=task.assignee,
                    target_event=task.event,
                    target_task=task,
                )
                if task.assignee_id != self.request.user.pk:
                    create_notification(
                        task.assignee,
                        Notification.Category.TASK_ASSIGNED,
                        'A task was assigned to you',
                        f'{task.title} was assigned to you for {task.event.title}.',
                        related_type='task',
                        related_id=task.pk,
                    )

            task_fields = set(changed) - {'status', 'assignee_id'}
            if task_fields:
                create_activity(
                    self.request.user,
                    Activity.Action.TASK_UPDATED,
                    f'{task.title} details were updated.',
                    target_user=task.assignee,
                    target_event=task.event,
                    target_task=task,
                )

            if 'status' in changed or task_fields or 'assignee_id' in changed:
                assigned_user_id = task.assignee_id if 'assignee_id' in changed else None
                recipients = {
                    recipient.pk: recipient
                    for recipient in (
                        task.assignee,
                        previous_assignee if 'assignee_id' in changed else None,
                        task.event.organizer,
                    )
                    if recipient is not None
                    and recipient.pk != self.request.user.pk
                    and recipient.pk != assigned_user_id
                }
                if 'status' in changed:
                    message = f'{task.title} status changed to {task.get_status_display()}.'
                else:
                    message = f'{task.title} was updated.'
                for recipient in recipients.values():
                    create_notification(
                        recipient,
                        Notification.Category.TASK_UPDATED,
                        'Task updated',
                        message,
                        related_type='task',
                        related_id=task.pk,
                    )

class MyTaskListView(TaskQueryMixin, generics.ListAPIView):
    serializer_class = TaskSerializer
    pagination_class = TaskPagination
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsVerifiedUser)

    def get_queryset(self):
        queryset = safe_task_queryset().filter(assignee=self.request.user)
        queryset = self.apply_filters(queryset)
        return queryset.order_by(F('due_at').asc(nulls_last=True), 'pk')
