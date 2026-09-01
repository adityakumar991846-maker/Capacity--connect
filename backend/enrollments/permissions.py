"""
Custom DRF permissions for enrollments module.
"""

from rest_framework.permissions import BasePermission

from core.models import Role


class IsTrainee(BasePermission):
    """Allows access only to users with the TRAINEE role."""

    def has_permission(self, request, view):
        return (
            hasattr(request.user, 'profile')
            and request.user.profile.role == Role.TRAINEE
        )


class IsTrainer(BasePermission):
    """Allows access only to users with the TRAINER role."""

    def has_permission(self, request, view):
        return (
            hasattr(request.user, 'profile')
            and request.user.profile.role == Role.TRAINER
        )


class IsAdmin(BasePermission):
    """Allows access only to users with the ADMIN role."""

    def has_permission(self, request, view):
        return (
            hasattr(request.user, 'profile')
            and request.user.profile.role == Role.ADMIN
        )
