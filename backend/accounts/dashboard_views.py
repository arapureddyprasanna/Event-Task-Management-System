from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from backend.accounts.history_serializers import ActivitySerializer, NotificationSerializer
from backend.accounts.models import Activity, AdminAccessRequest, Notification
from backend.accounts.permissions import IsVerifiedUser
from backend.events.models import Event, EventRegistration
from backend.events.serializers import EventSerializer
from backend.tasks.models import Task, TaskStatus


User = get_user_model()
UPCOMING_EVENT_LIMIT = 5
RECENT_ITEM_LIMIT = 5


def upcoming_events_queryset():
    return Event.objects.filter(
        status=Event.Status.PUBLISHED,
        start_at__gte=timezone.now(),
    ).select_related('organizer').annotate(
        active_registration_count=Count(
            'registrations',
            filter=Q(registrations__status=EventRegistration.Status.REGISTERED),
        )
    ).order_by('start_at', 'pk')


def dashboard_upcoming_events():
    return EventSerializer(
        upcoming_events_queryset()[:UPCOMING_EVENT_LIMIT], many=True
    ).data


def recent_activities(queryset):
    return ActivitySerializer(
        queryset.select_related(
            'actor', 'target_user', 'target_event', 'target_task', 'target_registration'
        ).order_by('-created_at', '-pk')[:RECENT_ITEM_LIMIT],
        many=True,
    ).data


def task_statistics(queryset, now):
    return queryset.aggregate(
        total=Count('pk'),
        pending=Count('pk', filter=Q(status=TaskStatus.TODO)),
        in_progress=Count('pk', filter=Q(status=TaskStatus.IN_PROGRESS)),
        completed=Count('pk', filter=Q(status=TaskStatus.COMPLETED)),
        overdue=Count(
            'pk',
            filter=Q(due_at__lt=now)
            & ~Q(status__in=(TaskStatus.COMPLETED, TaskStatus.CANCELLED)),
        ),
    )


class UserDashboardView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsVerifiedUser)

    def get(self, request):
        user = request.user
        now = timezone.now()
        registration_stats = EventRegistration.objects.filter(user=user).aggregate(
            total=Count('pk'),
            active=Count('pk', filter=Q(status=EventRegistration.Status.REGISTERED)),
            cancelled=Count('pk', filter=Q(status=EventRegistration.Status.CANCELLED)),
            upcoming=Count(
                'pk',
                filter=Q(
                    status=EventRegistration.Status.REGISTERED,
                    event__status=Event.Status.PUBLISHED,
                    event__start_at__gte=now,
                ),
            ),
        )
        tasks = task_statistics(Task.objects.filter(assignee=user), now)
        unread_notifications = Notification.objects.filter(
            recipient=user, is_read=False
        )
        recent_notifications = Notification.objects.filter(recipient=user)
        activities = Activity.objects.filter(Q(actor=user) | Q(target_user=user))
        upcoming = upcoming_events_queryset()

        return Response({
            'registrations': {
                'total': registration_stats['total'],
                'active': registration_stats['active'],
                'upcoming': registration_stats['upcoming'],
                'cancelled': registration_stats['cancelled'],
            },
            'tasks': tasks,
            'unread_notifications': unread_notifications.count(),
            'recent_notifications': NotificationSerializer(
                recent_notifications.order_by('-created_at', '-pk')[:RECENT_ITEM_LIMIT],
                many=True,
            ).data,
            'recent_activity': recent_activities(activities),
            'upcoming_events': EventSerializer(upcoming[:UPCOMING_EVENT_LIMIT], many=True).data,
        })


class AdminDashboardView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAdminUser,)

    def get(self, request):
        now = timezone.now()
        event_stats = Event.objects.aggregate(
            total=Count('pk'),
            published=Count('pk', filter=Q(status=Event.Status.PUBLISHED)),
        )
        registration_stats = EventRegistration.objects.aggregate(
            total=Count('pk'),
            active=Count('pk', filter=Q(status=EventRegistration.Status.REGISTERED)),
        )
        admin_notification_categories = (
            Notification.Category.ADMIN_ACCESS_REQUEST,
            Notification.Category.ADMIN_ACCESS_APPROVED,
            Notification.Category.ADMIN_ACCESS_REJECTED,
        )
        unread_admin_notifications = Notification.objects.filter(
            recipient__is_staff=True,
            category__in=admin_notification_categories,
            is_read=False,
        )
        recent_admin_notifications = Notification.objects.filter(
            recipient__is_staff=True,
            category__in=admin_notification_categories,
        )

        return Response({
            'users': {'total': User.objects.count()},
            'events': event_stats,
            'registrations': registration_stats,
            'tasks': task_statistics(Task.objects.all(), now),
            'pending_admin_access_requests': AdminAccessRequest.objects.filter(
                status=AdminAccessRequest.Status.PENDING
            ).count(),
            'unread_admin_notifications': unread_admin_notifications.count(),
            'recent_notifications': NotificationSerializer(
                recent_admin_notifications.order_by('-created_at', '-pk')[:RECENT_ITEM_LIMIT],
                many=True,
            ).data,
            'recent_activity': recent_activities(Activity.objects.all()),
            'upcoming_events': dashboard_upcoming_events(),
        })
