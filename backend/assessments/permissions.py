"""
Custom DRF permission classes for the assessments module.
"""

from rest_framework.permissions import BasePermission
from core.models import Role


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


class IsTrainerOrAdmin(BasePermission):
    """Allows access to users with either TRAINER or ADMIN role."""
    def has_permission(self, request, view):
        return (
            hasattr(request.user, 'profile')
            and request.user.profile.role in (Role.TRAINER, Role.ADMIN)
        )


class IsTrainee(BasePermission):
    """Allows access only to users with the TRAINEE role."""
    def has_permission(self, request, view):
        return (
            hasattr(request.user, 'profile')
            and request.user.profile.role == Role.TRAINEE
        )


class IsTraineeOrAdmin(BasePermission):
    """Allows access to users with either TRAINEE or ADMIN role."""
    def has_permission(self, request, view):
        return (
            hasattr(request.user, 'profile')
            and request.user.profile.role in (Role.TRAINEE, Role.ADMIN)
        )
