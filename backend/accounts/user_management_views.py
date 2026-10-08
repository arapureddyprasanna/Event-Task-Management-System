from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Profile
from .profile_serializers import AdminUserSerializer, UserActivationSerializer


User = get_user_model()


class AdminUserPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminUserListView(ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAdminUser,)
    serializer_class = AdminUserSerializer
    pagination_class = AdminUserPagination

    def get_queryset(self):
        users = User.objects.select_related('profile').order_by('pk')
        for parameter, field in (
            ('is_active', 'is_active'),
            ('is_staff', 'is_staff'),
            ('is_email_verified', 'profile__is_email_verified'),
        ):
            raw_value = self.request.query_params.get(parameter)
            if raw_value is None:
                continue
            value = raw_value.casefold()
            if value not in {'true', 'false'}:
                raise ValidationError({parameter: 'Use true or false.'})
            flag = value == 'true'
            if parameter == 'is_email_verified' and not flag:
                users = users.filter(
                    Q(profile__is_email_verified=False) | Q(profile__isnull=True)
                )
            else:
                users = users.filter(**{field: flag})

        search = self.request.query_params.get('search', '').strip()
        if search:
            users = users.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        return users


class AdminUserDetailView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAdminUser,)

    def get(self, request, pk):
        user = get_object_or_404(User.objects.select_related('profile'), pk=pk)
        return Response(AdminUserSerializer(user).data)


class AdminUserActivationView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAdminUser,)

    def patch(self, request, pk):
        serializer = UserActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_object_or_404(User, pk=pk)
        user.is_active = serializer.validated_data['is_active']
        user.save(update_fields=('is_active',))
        user = User.objects.select_related('profile').get(pk=user.pk)
        return Response(AdminUserSerializer(user).data, status=status.HTTP_200_OK)
