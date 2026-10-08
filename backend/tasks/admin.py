from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'event', 'status', 'priority', 'assignee', 'due_at')
    list_filter = ('status', 'priority', 'event')
    search_fields = ('title', 'description', 'event__title', 'assignee__username')
    list_select_related = ('event', 'assignee')
    readonly_fields = ('created_at', 'updated_at')
