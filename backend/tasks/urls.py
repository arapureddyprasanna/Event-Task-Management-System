from django.urls import path

from .views import EventTaskListCreateView, MyTaskListView, TaskDetailView


urlpatterns = [
    path('my/', MyTaskListView.as_view(), name='my-tasks'),
    path('<int:pk>/', TaskDetailView.as_view(), name='task-detail'),
]
