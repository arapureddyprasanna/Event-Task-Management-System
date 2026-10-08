from django.urls import path

from .views import (
    CancelEventRegistrationView,
    EventRegistrationView,
    EventRegistrationsView,
    EventViewSet,
    MyRegistrationsView,
)


urlpatterns = [
    path('my-registrations/', MyRegistrationsView.as_view(), name='my-event-registrations'),
    path('<int:event_id>/register/', EventRegistrationView.as_view(), name='event-register'),
    path('<int:event_id>/register/cancel/', CancelEventRegistrationView.as_view(), name='event-registration-cancel'),
    path('<int:event_id>/registrations/', EventRegistrationsView.as_view(), name='event-registrations'),
    path(
        '',
        EventViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='event-list',
    ),
    path(
        '<int:pk>/',
        EventViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update'}),
        name='event-detail',
    ),
]
