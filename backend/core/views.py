"""
Views for the core authentication module.

Provides Register, Login, Logout, and CurrentUser API views.
Aligned with Supabase Bearer token architecture without creating competing API sessions.
"""

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


class RegisterView(APIView):
    """
    POST /api/auth/register/

    Creates a new user with a UserProfile. Public endpoint.
    Only TRAINEE and TRAINER roles are allowed.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """
    POST /api/auth/login/

    Validates user credentials against Django backend.
    Does not issue or require Django session cookies.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password'],
        )
        if user is None:
            return Response(
                {'detail': 'Invalid credentials.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    """
    POST /api/auth/logout/

    Logs out the user in alignment with Bearer token authentication.
    Requires valid authentication.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({'detail': 'Successfully logged out.'})


class CurrentUserView(APIView):
    """
    GET /api/auth/me/

    Returns the current authenticated user's info and role.
    Requires Bearer token authentication.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

