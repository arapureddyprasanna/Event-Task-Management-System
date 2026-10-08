from django.core.exceptions import ObjectDoesNotExist
from rest_framework.permissions import BasePermission


class IsVerifiedUser(BasePermission):
    message = 'Email verification is required.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        try:
            profile = user.profile
            return profile.is_email_verified or profile.registration_demo_access
        except ObjectDoesNotExist:
            return False


class IsSuperuser(BasePermission):
    message = 'Only a superuser may manage admin access requests.'

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_superuser
        )
