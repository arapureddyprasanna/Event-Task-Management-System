from rest_framework.permissions import BasePermission


class EventOwnerOrAdmin(BasePermission):
    message = 'Only the event organizer or an admin may manage this event.'

    def has_object_permission(self, request, view, event):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_staff or event.organizer_id == user.pk)
        )
