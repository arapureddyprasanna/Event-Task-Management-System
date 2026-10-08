from rest_framework.permissions import BasePermission


class TaskVisibleToUser(BasePermission):
    message = 'You may only access tasks for your event or assigned to you.'

    def has_object_permission(self, request, view, task):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_staff
                or task.event.organizer_id == user.pk
                or task.assignee_id == user.pk
            )
        )
