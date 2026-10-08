from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .profile_serializers import ChangePasswordSerializer, ProfileSerializer, ProfileUpdateSerializer
from .permissions import IsVerifiedUser
from .services.email import EmailDeliveryError
from .services.profiles import update_user_profile


class ProfileView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsVerifiedUser)

    def get(self, request):
        return Response(ProfileSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        try:
            user = update_user_profile(request.user, dict(serializer.validated_data))
        except EmailDeliveryError:
            return Response(
                {'detail': 'Verification email could not be sent. Please try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        user = type(user).objects.select_related('profile').get(pk=user.pk)
        return Response(ProfileSerializer(user).data)


class ChangePasswordView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsVerifiedUser)

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        if not request.user.check_password(values['current_password']):
            return Response(
                {'current_password': ['Current password is incorrect.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            password_validation.validate_password(
                values['new_password'], user=request.user
            )
        except DjangoValidationError as exc:
            return Response(
                {'new_password': list(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.set_password(values['new_password'])
        request.user.save(update_fields=('password',))
        return Response(
            {'detail': 'Password changed successfully.'},
            status=status.HTTP_200_OK,
        )
