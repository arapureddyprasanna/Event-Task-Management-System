from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import get_md5_hash_password

from .services.admin_access import admin_request_auth_error


User = get_user_model()


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254, trim_whitespace=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True, trim_whitespace=False)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254, trim_whitespace=True)

    def validate_email(self, value):
        return value.strip().lower()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254, trim_whitespace=True)
    otp = serializers.RegexField(regex=r'^\d{6}$', max_length=6, min_length=6)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        if attrs['new_password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {'password_confirm': 'Passwords do not match.'}
            )
        return attrs


class VerifiedTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        try:
            refresh = RefreshToken(attrs['refresh'])
        except TokenError as exc:
            raise InvalidToken(str(exc)) from exc

        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM)
        if user_id is None:
            raise InvalidToken('Token contained no user identification.')
        try:
            user = User.objects.select_related('profile').get(
                **{api_settings.USER_ID_FIELD: user_id}
            )
        except User.DoesNotExist as exc:
            raise AuthenticationFailed('No active account found.') from exc

        if not api_settings.USER_AUTHENTICATION_RULE(user):
            raise AuthenticationFailed('No active account found.')
        admin_error = admin_request_auth_error(user)
        if admin_error:
            raise PermissionDenied(admin_error)
        try:
            profile = user.profile
            verified = profile.is_email_verified
            registration_demo_access = profile.registration_demo_access
        except ObjectDoesNotExist:
            verified = False
            registration_demo_access = False
        if not verified and not registration_demo_access:
            raise PermissionDenied(
                {'code': 'email_not_verified', 'detail': 'Email verification is required.'}
            )
        if api_settings.CHECK_REVOKE_TOKEN and refresh.get(
            api_settings.REVOKE_TOKEN_CLAIM
        ) != get_md5_hash_password(user.password):
            raise AuthenticationFailed('Token has been revoked.', code='password_changed')

        return super().validate(attrs)
