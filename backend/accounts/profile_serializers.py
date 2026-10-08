from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Profile


User = get_user_model()


class ProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    is_staff = serializers.BooleanField(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)
    is_email_verified = serializers.BooleanField(read_only=True)
    registration_demo_access = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def to_representation(self, user):
        profile = getattr(user, 'profile', None)
        return {
            'id': user.pk,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'is_email_verified': bool(profile and profile.is_email_verified),
            'registration_demo_access': bool(profile and profile.registration_demo_access),
            'created_at': profile.created_at if profile else None,
            'updated_at': profile.updated_at if profile else None,
        }


class ProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(max_length=254, required=False)

    protected_fields = frozenset({
        'id', 'username', 'is_staff', 'is_superuser', 'is_email_verified',
        'role', 'password', 'groups', 'user_permissions', 'permissions',
    })

    def validate_email(self, value):
        normalized = value.strip().lower()
        user = self.context['request'].user
        if User.objects.filter(email__iexact=normalized).exclude(pk=user.pk).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return normalized

    def validate(self, attrs):
        forbidden = self.protected_fields.intersection(self.initial_data)
        if forbidden:
            raise serializers.ValidationError({
                field: 'This field cannot be changed.' for field in sorted(forbidden)
            })
        unexpected = set(self.initial_data) - set(self.fields)
        if unexpected:
            raise serializers.ValidationError({
                field: 'Unexpected field.' for field in sorted(unexpected)
            })
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'Passwords do not match.'
            })
        return attrs


class AdminUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_staff = serializers.BooleanField(read_only=True)
    is_email_verified = serializers.SerializerMethodField()
    date_joined = serializers.DateTimeField(read_only=True)

    def get_is_email_verified(self, user):
        profile = getattr(user, 'profile', None)
        return bool(profile and profile.is_email_verified)


class UserActivationSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()

    def validate(self, attrs):
        unexpected = set(self.initial_data) - set(self.fields)
        if unexpected:
            raise serializers.ValidationError({
                field: 'Unexpected field.' for field in sorted(unexpected)
            })
        return attrs
