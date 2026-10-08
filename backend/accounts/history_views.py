from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .history_serializers import ActivitySerializer, NotificationSerializer
from .models import Activity, Notification
from .permissions import IsVerifiedUser


class HistoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class NotificationListView(generics.ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsVerifiedUser)
    serializer_class = NotificationSerializer
    pagination_class = HistoryPagination

    def get_queryset(self):
        notifications = Notification.objects.filter(
            recipient=self.request.user
        )
        unread = self.request.query_params.get('unread')
        if unread is not None:
            if unread.lower() not in ('true', 'false'):
                raise ValidationError({'unread': 'Use true or false.'})
            notifications = notifications.filter(is_read=unread.lower() == 'false')
        return notifications.order_by('-created_at', '-pk')


class NotificationReadView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsVerifiedUser)

    def post(self, request, pk):
        notification = get_object_or_404(
            Notification.objects.filter(recipient=request.user), pk=pk
        )
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=('is_read',))
        return Response(NotificationSerializer(notification).data)


class NotificationReadAllView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsVerifiedUser)

    def post(self, request):
        updated = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).update(is_read=True)
        return Response({'updated': updated}, status=status.HTTP_200_OK)


class ActivityListView(generics.ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsVerifiedUser)
    serializer_class = ActivitySerializer
    pagination_class = HistoryPagination

    def get_queryset(self):
        activities = Activity.objects.select_related(
            'actor', 'target_user', 'target_event', 'target_task',
            'target_registration',
        )
        if not self.request.user.is_staff:
            activities = activities.filter(
                Q(actor=self.request.user) | Q(target_user=self.request.user)
            )
        return activities.order_by('-created_at', '-pk')
