from django.urls import path

from .auth_views import (
    ForgotPasswordView,
    IsVerifiedUserTestView,
    LoginView,
    LogoutView,
    ResetPasswordView,
    VerifiedTokenRefreshView,
)
from .profile_views import ChangePasswordView, ProfileView
from .views import (
    AdminAccessRequestListView,
    ApproveAdminAccessRequestView,
    RegisterView,
    AdminCreateView,
    RejectAdminAccessRequestView,
    ResendOTPView,
    VerifyEmailView,
)


app_name = 'accounts'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', VerifiedTokenRefreshView.as_view(), name='token-refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('protected/', IsVerifiedUserTestView.as_view(), name='protected-test'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('register/', RegisterView.as_view(), name='register'),
    path('admin/create/', AdminCreateView.as_view(), name='admin-create'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('admin-requests/', AdminAccessRequestListView.as_view(), name='admin-access-request-list'),
    path(
        'admin-requests/<int:pk>/approve/',
        ApproveAdminAccessRequestView.as_view(),
        name='admin-access-request-approve',
    ),
    path(
        'admin-requests/<int:pk>/reject/',
        RejectAdminAccessRequestView.as_view(),
        name='admin-access-request-reject',
    ),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
]
