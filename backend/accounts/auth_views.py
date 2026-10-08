from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .auth_serializers import (
    ForgotPasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    ResetPasswordSerializer,
    VerifiedTokenRefreshSerializer,
)
from .models import EmailOTP
from .permissions import IsVerifiedUser
from .services.admin_access import admin_request_auth_error
from .services.email import EmailDeliveryError, send_otp_email


User = get_user_model()


class LoginView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data['identifier']
        candidate = User.objects.select_related('profile').filter(
            email__iexact=identifier
        ).first()
        if candidate is None:
            candidate = User.objects.select_related('profile').filter(
                username__iexact=identifier
            ).first()

        authenticated_user = authenticate(
            request,
            username=candidate.username if candidate else identifier,
            password=serializer.validated_data['password'],
        )
        if authenticated_user is None:
            return Response(
                {'detail': 'Invalid username/email or password.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        admin_error = admin_request_auth_error(candidate)
        if admin_error:
            return Response(admin_error, status=status.HTTP_403_FORBIDDEN)

        try:
            profile = candidate.profile
            verified = profile.is_email_verified
            registration_demo_access = profile.registration_demo_access
        except ObjectDoesNotExist:
            verified = False
            registration_demo_access = False
        if not verified and not registration_demo_access:
            return Response(
                {
                    'code': 'email_not_verified',
                    'detail': 'Email verification is required before login.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(authenticated_user)
        return Response(
            {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': authenticated_user.pk,
                    'username': authenticated_user.username,
                    'email': authenticated_user.email,
                    'first_name': authenticated_user.first_name,
                    'last_name': authenticated_user.last_name,
                },
                'is_staff': authenticated_user.is_staff,
                'is_email_verified': verified,
            },
            status=status.HTTP_200_OK,
        )


class VerifiedTokenRefreshView(TokenRefreshView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    serializer_class = VerifiedTokenRefreshSerializer


class LogoutView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refresh = RefreshToken(serializer.validated_data['refresh'])
        except TokenError as exc:
            raise InvalidToken(str(exc)) from exc

        user_id = refresh.get(api_settings.USER_ID_CLAIM)
        if str(user_id) != str(request.user.pk):
            return Response(
                {'detail': 'Invalid refresh token.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        refresh.blacklist()
        return Response({'detail': 'Logout successful.'}, status=status.HTTP_200_OK)


class IsVerifiedUserTestView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsVerifiedUser)

    def get(self, request):
        return Response({'user_id': request.user.pk}, status=status.HTTP_200_OK)


class ForgotPasswordView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    generic_response = {
        'detail': 'If an account with that email exists, password reset instructions have been sent.'
    }

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        user = User.objects.filter(email__iexact=email).first()
        if user is not None:
            try:
                with transaction.atomic():
                    otp, code = EmailOTP.issue(
                        user.email,
                        user=user,
                        purpose=EmailOTP.Purpose.RESET_PASSWORD,
                    )
                    send_otp_email(otp.email, code)
            except EmailDeliveryError:
                pass
        return Response(self.generic_response, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = User.objects.select_related('profile').filter(
            email__iexact=data['email']
        ).first()
        if user is None:
            return self.invalid_code_response()

        try:
            validate_password(data['new_password'], user=user)
        except DjangoValidationError as exc:
            return Response(
                {'new_password': list(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            otp = (
                EmailOTP.objects.select_for_update()
                .filter(
                    email__iexact=user.email,
                    user=user,
                    purpose=EmailOTP.Purpose.RESET_PASSWORD,
                    verified_at__isnull=True,
                )
                .order_by('-created_at')
                .first()
            )
            if otp is None:
                return self.invalid_code_response()
            if otp.expires_at <= timezone.now():
                return self.invalid_code_response()
            if otp.verification_attempts >= EmailOTP.MAX_VERIFY_ATTEMPTS:
                return Response(
                    {'detail': 'Verification attempt limit reached.'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            if not otp.verify(data['otp']):
                if otp.verification_attempts >= EmailOTP.MAX_VERIFY_ATTEMPTS:
                    return Response(
                        {'detail': 'Verification attempt limit reached.'},
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
                return self.invalid_code_response()

            user.set_password(data['new_password'])
            user.save(update_fields=('password',))

        return Response(
            {'detail': 'Password reset successful.'},
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def invalid_code_response():
        return Response(
            {'detail': 'Invalid or expired reset code.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
