import smtplib

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .admin_access_serializers import (
    AdminAccessDecisionSerializer,
    AdminAccessRequestSerializer,
)
from .models import Activity, AdminAccessRequest, EmailOTP, Notification, Profile
from .permissions import IsSuperuser
from .serializers import AdminCreationSerializer, EmailOTPSerializer, RegistrationSerializer, VerifyEmailSerializer
from .services.activities import create_activity
from .services.notifications import create_notification
from .services.email import EmailDeliveryError, send_otp_email


User = get_user_model()


def _is_unverified_demo_sender_error(error):
    if not settings.DEBUG:
        return False
    cause = error.__cause__
    while cause is not None:
        if isinstance(cause, smtplib.SMTPDataError):
            response = cause.smtp_error.decode(errors='replace') if isinstance(
                cause.smtp_error, bytes
            ) else str(cause.smtp_error)
            return cause.smtp_code == 550 and 'domain is not verified' in response.lower()
        cause = cause.__cause__
    return False


class RegisterView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        requested_admin_access = values['role'] == 'admin'
        email_delivery_deferred = False

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=values['username'],
                    email=values['email'],
                    password=values['password'],
                    first_name=values.get('first_name', ''),
                    last_name=values.get('last_name', ''),
                )
                Profile.objects.create(
                    user=user,
                    registration_demo_access=False,
                )
                if requested_admin_access:
                    admin_request = AdminAccessRequest.objects.create(requester=user)
                    create_activity(
                        user,
                        Activity.Action.ADMIN_ACCESS_REQUESTED,
                        f'{user.get_username()} requested admin access.',
                        target_user=user,
                    )
                    for superuser in User.objects.filter(
                        is_superuser=True, is_active=True
                    ):
                        create_notification(
                            superuser,
                            Notification.Category.ADMIN_ACCESS_REQUEST,
                            'Admin access request',
                            f'{user.get_username()} is requesting admin access.',
                            related_type='admin_access_request',
                            related_id=admin_request.pk,
                        )
                otp, code = EmailOTP.issue(
                    values['email'], user=user, purpose=EmailOTP.Purpose.VERIFY_EMAIL
                )
                try:
                    send_otp_email(otp.email, code)
                except EmailDeliveryError as exc:
                    if not _is_unverified_demo_sender_error(exc):
                        raise
                    email_delivery_deferred = True
        except EmailDeliveryError:
            return Response(
                {'detail': 'Registration email could not be sent. Please try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except DjangoValidationError as exc:
            return Response(
                {'detail': 'Registration data is invalid.', 'errors': exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = {
            'detail': (
                'Admin access request submitted. Verify your email and wait for '
                'superuser approval before signing in.'
                if requested_admin_access else
                'Registration successful. The verification email could not be delivered; '
                'sign in to continue with the demo.'
                if email_delivery_deferred else
                'Registration successful. Check your email for a verification code.'
            ),
            'email_delivery_deferred': email_delivery_deferred,
        }
        if requested_admin_access:
            response_data['admin_request_status'] = AdminAccessRequest.Status.PENDING
        return Response(response_data, status=status.HTTP_201_CREATED)


class AdminCreateView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsSuperuser)

    def post(self, request):
        serializer = AdminCreationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=values['username'], email=values['email'], password=values['password'],
                    first_name=values.get('first_name', ''), last_name=values.get('last_name', ''),
                    is_staff=True,
                )
                Profile.objects.create(user=user, role=Profile.Role.ADMIN)
                otp, code = EmailOTP.issue(
                    values['email'], user=user, purpose=EmailOTP.Purpose.VERIFY_EMAIL
                )
                send_otp_email(otp.email, code)
        except EmailDeliveryError:
            return Response(
                {'detail': 'The admin account could not be created because a verification email could not be sent. Please try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({
            'id': user.pk, 'username': user.username, 'email': user.email,
            'first_name': user.first_name, 'last_name': user.last_name,
            'is_staff': user.is_staff, 'is_email_verified': False,
            'detail': 'Admin account created. The new admin must verify their email before signing in.',
        }, status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        code = serializer.validated_data['otp']

        with transaction.atomic():
            user = User.objects.filter(email__iexact=email).select_related('profile').first()
            profile = getattr(user, 'profile', None) if user else None
            if profile and profile.is_email_verified:
                return Response(
                    {'detail': 'Email is already verified.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            otp = (
                EmailOTP.objects.select_for_update()
                .filter(email=email, purpose=EmailOTP.Purpose.VERIFY_EMAIL, verified_at__isnull=True)
                .order_by('-created_at')
                .first()
            )
            if otp is None:
                return Response(
                    {'detail': 'Invalid or unavailable verification code.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if otp.expires_at <= timezone.now():
                return Response(
                    {'detail': 'Verification code has expired.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if otp.verification_attempts >= EmailOTP.MAX_VERIFY_ATTEMPTS:
                return Response(
                    {'detail': 'Verification attempt limit reached. Request a new code.'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            if otp.user_id is None:
                return Response(
                    {'detail': 'Verification code is not associated with an account.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if user is None or user.pk != otp.user_id or profile is None:
                return Response(
                    {'detail': 'Account profile is unavailable for verification.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not otp.verify(code):
                if otp.verification_attempts >= EmailOTP.MAX_VERIFY_ATTEMPTS:
                    return Response(
                        {'detail': 'Verification attempt limit reached. Request a new code.'},
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
                return Response(
                    {'detail': 'Invalid verification code.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            profile = Profile.objects.select_for_update().get(user_id=otp.user_id)
            profile.is_email_verified = True
            profile.registration_demo_access = False
            profile.save(update_fields=(
                'is_email_verified', 'registration_demo_access', 'updated_at'
            ))

        return Response({'detail': 'Email verified successfully.'}, status=status.HTTP_200_OK)


class ResendOTPView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = EmailOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        try:
            with transaction.atomic():
                user = User.objects.filter(email__iexact=email).select_related('profile').first()
                profile = getattr(user, 'profile', None) if user else None
                if profile and profile.is_email_verified:
                    return Response(
                        {'detail': 'Email is already verified.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                otp = (
                    EmailOTP.objects.select_for_update()
                    .filter(email=email, purpose=EmailOTP.Purpose.VERIFY_EMAIL, verified_at__isnull=True)
                    .order_by('-created_at')
                    .first()
                )
                if otp is None:
                    return Response(
                        {'detail': 'No verification request is available for this email.'},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                code = otp.resend()
                send_otp_email(otp.email, code)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0]},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except EmailDeliveryError:
            return Response(
                {'detail': 'Verification email could not be sent. Please try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {'detail': 'A new verification code has been sent.'},
            status=status.HTTP_200_OK,
        )


class AdminAccessRequestPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminAccessRequestListView(generics.ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsSuperuser)
    serializer_class = AdminAccessRequestSerializer
    pagination_class = AdminAccessRequestPagination

    def get_queryset(self):
        request_status = self.request.query_params.get(
            'status', AdminAccessRequest.Status.PENDING
        )
        requests = AdminAccessRequest.objects.select_related(
            'requester', 'reviewer'
        )
        if request_status == 'all':
            pass
        elif request_status in AdminAccessRequest.Status.values:
            requests = requests.filter(status=request_status)
        else:
            raise ValidationError({
                'status': 'Choose pending, approved, rejected, or all.'
            })
        return requests


class AdminAccessRequestDecisionView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsSuperuser)
    decision_status = None

    def post(self, request, pk):
        serializer = AdminAccessDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            admin_request = get_object_or_404(
                AdminAccessRequest.objects.select_for_update(), pk=pk
            )
            if admin_request.requester_id == request.user.pk:
                raise PermissionDenied('You cannot review your own admin access request.')
            if admin_request.status != AdminAccessRequest.Status.PENDING:
                return Response(
                    {'detail': 'This admin access request has already been reviewed.'},
                    status=status.HTTP_409_CONFLICT,
                )

            if self.decision_status == AdminAccessRequest.Status.APPROVED:
                requester = get_user_model().objects.select_for_update().get(
                    pk=admin_request.requester_id
                )
                profile = Profile.objects.select_for_update().get(user=requester)
                requester.is_staff = True
                requester.save(update_fields=('is_staff',))
                profile.role = Profile.Role.ADMIN
                profile.save(update_fields=('role', 'updated_at'))

            admin_request.status = self.decision_status
            admin_request.reviewer = request.user
            admin_request.reviewed_at = timezone.now()
            admin_request.decision_reason = serializer.validated_data.get('reason', '')
            admin_request.save(update_fields=(
                'status', 'reviewer', 'reviewed_at', 'decision_reason'
            ))
            requester = admin_request.requester
            if self.decision_status == AdminAccessRequest.Status.APPROVED:
                category = Notification.Category.ADMIN_ACCESS_APPROVED
                action = Activity.Action.ADMIN_ACCESS_APPROVED
                title = 'Admin access approved'
                message = 'Your admin access request was approved.'
                description = f'{requester.get_username()} was approved for admin access.'
            else:
                category = Notification.Category.ADMIN_ACCESS_REJECTED
                action = Activity.Action.ADMIN_ACCESS_REJECTED
                title = 'Admin access request rejected'
                message = 'Your admin access request was rejected.'
                description = f'{requester.get_username()} was rejected for admin access.'
            create_notification(
                requester,
                category,
                title,
                message,
                related_type='admin_access_request',
                related_id=admin_request.pk,
            )
            create_activity(
                request.user,
                action,
                description,
                target_user=requester,
            )

        return Response(
            AdminAccessRequestSerializer(admin_request).data,
            status=status.HTTP_200_OK,
        )


class ApproveAdminAccessRequestView(AdminAccessRequestDecisionView):
    decision_status = AdminAccessRequest.Status.APPROVED


class RejectAdminAccessRequestView(AdminAccessRequestDecisionView):
    decision_status = AdminAccessRequest.Status.REJECTED
