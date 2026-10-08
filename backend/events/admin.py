from django.contrib import admin

from .models import Event, EventRegistration


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'organizer', 'status', 'start_at', 'end_at', 'capacity')
    list_filter = ('status', 'start_at')
    search_fields = ('title', 'organizer__username', 'organizer__email', 'location')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'start_at'


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('event', 'user', 'status', 'registered_at', 'updated_at')
    list_filter = ('status', 'registered_at')
    search_fields = ('event__title', 'user__username', 'user__email')
    readonly_fields = ('registered_at', 'updated_at')
    list_select_related = ('event', 'user')
