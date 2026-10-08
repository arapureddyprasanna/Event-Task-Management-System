"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

from backend.accounts.history_views import (
    ActivityListView,
    NotificationListView,
    NotificationReadAllView,
    NotificationReadView,
)
from backend.accounts.dashboard_views import AdminDashboardView, UserDashboardView
from backend.accounts.user_management_views import (
    AdminUserActivationView,
    AdminUserDetailView,
    AdminUserListView,
)
from backend.tasks.views import EventTaskListCreateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('backend.accounts.urls')),
    path('api/notifications/', NotificationListView.as_view(), name='notification-list'),
    path('api/notifications/read-all/', NotificationReadAllView.as_view(), name='notification-read-all'),
    path('api/notifications/<int:pk>/read/', NotificationReadView.as_view(), name='notification-read'),
    path('api/activity/', ActivityListView.as_view(), name='activity-list'),
    path('api/dashboard/', UserDashboardView.as_view(), name='user-dashboard'),
    path('api/admin/dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('api/events/<int:event_id>/tasks/', EventTaskListCreateView.as_view(), name='event-tasks'),
    path('api/events/', include('backend.events.urls')),
    path('api/tasks/', include('backend.tasks.urls')),
    path('api/users/', AdminUserListView.as_view(), name='admin-user-list'),
    path('api/users/<int:pk>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    path(
        'api/users/<int:pk>/activation/',
        AdminUserActivationView.as_view(),
        name='admin-user-activation',
    ),
]
