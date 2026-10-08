from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from backend.accounts.permissions import IsVerifiedUser
from .models import Event
from .permissions import EventOwnerOrAdmin
from .models import EventRegistration
from .serializers import (
    EventSerializer,
    EventRegistrationSerializer,
    OrganizerRegistrationSerializer,
)
from .services import cancel_user_registration, register_user


class EventPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class EventViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = EventSerializer
    pagination_class = EventPagination
    authentication_classes = (JWTAuthentication,)
    http_method_names = ('get', 'post', 'patch', 'head', 'options')

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return (AllowAny(),)
        permissions = [IsAuthenticated(), IsVerifiedUser()]
        if self.action in ('update', 'partial_update'):
            permissions.append(EventOwnerOrAdmin())
        return permissions

    def get_queryset(self):
        events = Event.objects.select_related('organizer').annotate(
            active_registration_count=Count(
                'registrations',
                filter=Q(registrations__status=EventRegistration.Status.REGISTERED),
            )
        ).order_by('start_at', 'pk')
        user = self.request.user
        if user.is_authenticated and user.is_staff:
            pass
        elif user.is_authenticated and IsVerifiedUser().has_permission(self.request, self):
            events = events.filter(
                Q(status__in=(
                    Event.Status.PUBLISHED,
                    Event.Status.CANCELLED,
                    Event.Status.COMPLETED,
                ))
                | Q(organizer=user)
            )
        else:
            events = events.filter(
                status__in=(
                    Event.Status.PUBLISHED,
                    Event.Status.CANCELLED,
                    Event.Status.COMPLETED,
                )
            )

        search = self.request.query_params.get('search', '').strip()
        if search:
            events = events.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(location__icontains=search)
            )

        event_status = self.request.query_params.get('status')
        if event_status:
            if event_status not in Event.Status.values:
                raise ValidationError({'status': 'Choose a supported event status.'})
            events = events.filter(status=event_status)

        upcoming = self.request.query_params.get('upcoming')
        if upcoming is not None:
            if upcoming.casefold() not in {'true', 'false'}:
                raise ValidationError({'upcoming': 'Use true or false.'})
            if upcoming.casefold() == 'true':
                events = events.filter(
                    status=Event.Status.PUBLISHED,
                    start_at__gte=timezone.now(),
                )

        for parameter, lookup in (
            ('start_after', 'start_at__gte'),
            ('start_before', 'start_at__lte'),
        ):
            value = self.request.query_params.get(parameter)
            if value:
                try:
                    parsed = EventSerializer().fields['start_at'].to_internal_value(value)
                except (TypeError, ValueError, ValidationError):
                    raise ValidationError({parameter: 'Enter a valid ISO-8601 datetime.'})
                events = events.filter(**{lookup: parsed})

        organizer = self.request.query_params.get('organizer')
        if organizer:
            if not organizer.isdecimal():
                raise ValidationError({'organizer': 'Enter a valid organizer ID.'})
            events = events.filter(organizer_id=int(organizer))
        return events

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)


class RegistrationPermissionsMixin:
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsVerifiedUser)


class EventRegistrationView(RegistrationPermissionsMixin, APIView):
    def post(self, request, event_id):
        registration = register_user(event_id, request.user)
        return Response(
            EventRegistrationSerializer(registration).data,
            status=status.HTTP_201_CREATED,
        )


class CancelEventRegistrationView(RegistrationPermissionsMixin, APIView):
    def post(self, request, event_id):
        registration = cancel_user_registration(event_id, request.user)
        return Response(EventRegistrationSerializer(registration).data)


class MyRegistrationsView(RegistrationPermissionsMixin, ListAPIView):
    serializer_class = EventRegistrationSerializer
    pagination_class = EventPagination

    def get_queryset(self):
        queryset = EventRegistration.objects.filter(user=self.request.user).select_related('event').annotate(
            event_active_registration_count=Count(
                'event__registrations',
                filter=Q(
                    event__registrations__status=EventRegistration.Status.REGISTERED
                ),
            )
        )
        registration_status = self.request.query_params.get('status')
        if registration_status:
            if registration_status not in EventRegistration.Status.values:
                raise ValidationError({'status': 'Choose a supported registration status.'})
            queryset = queryset.filter(status=registration_status)
        return queryset.order_by('-registered_at', '-pk')


class EventRegistrationsView(RegistrationPermissionsMixin, ListAPIView):
    serializer_class = OrganizerRegistrationSerializer
    pagination_class = EventPagination

    def get_queryset(self):
        try:
            event = Event.objects.get(pk=self.kwargs['event_id'])
        except Event.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Event not found.')
        if not (self.request.user.is_staff or event.organizer_id == self.request.user.pk):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only the event organizer or staff may view registrations.')
        queryset = EventRegistration.objects.filter(event=event).select_related('user', 'event')
        registration_status = self.request.query_params.get('status')
        if registration_status:
            if registration_status not in EventRegistration.Status.values:
                raise ValidationError({'status': 'Choose a supported registration status.'})
            queryset = queryset.filter(status=registration_status)
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(user__username__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
            )
        return queryset.order_by('-registered_at', '-pk')

