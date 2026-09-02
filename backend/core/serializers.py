"""
Serializers for the core authentication module.

Provides Register, Login, and User serializers. Passwords are never
included in any response serializer.
"""

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Role, UserProfile


class RegisterSerializer(serializers.Serializer):
    """
    Handles user registration.

    Validates:
    - username and email uniqueness
    - password strength (Django validators)
    - password confirmation match
    - role must be TRAINEE or TRAINER (blocks ADMIN)
    """
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=[(Role.TRAINEE, 'Trainee'), (Role.TRAINER, 'Trainer')])

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('A user with this username already exists.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
        )
        UserProfile.objects.create(
            user=user,
            role=validated_data['role'],
        )
        return user


class LoginSerializer(serializers.Serializer):
    """Accepts username and password for authentication."""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.Serializer):
    """
    Returns current user info. Never returns password.
    """
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    role = serializers.SerializerMethodField()
    supabase_uid = serializers.SerializerMethodField()

    def get_role(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.role
        return None

    def get_supabase_uid(self, obj):
        if hasattr(obj, 'profile') and obj.profile.supabase_uid:
            return str(obj.profile.supabase_uid)
        return None

