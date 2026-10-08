from django.contrib import admin

from .models import EmailOTP, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'created_at', 'updated_at')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = (
        'email', 'user', 'expires_at', 'verified_at',
        'verification_attempts', 'resend_attempts', 'created_at',
    )
    list_filter = ('verified_at', 'created_at')
    search_fields = ('email', 'user__username')
    readonly_fields = (
        'code_hash', 'expires_at', 'verified_at', 'verification_attempts',
        'resend_attempts', 'created_at', 'updated_at',
    )
    fields = (
        'email', 'user', 'code_hash', 'expires_at', 'verified_at',
        'verification_attempts', 'resend_attempts', 'created_at', 'updated_at',
    )
