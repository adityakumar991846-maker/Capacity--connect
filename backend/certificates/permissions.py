"""
Permission classes for the certificates module.
"""

from rest_framework.permissions import BasePermission
from core.models import Role


class IsAdmin(BasePermission):
    """Allows access only to Admin users."""
    def has_permission(self, request, view):
        return (
            hasattr(request.user, 'profile')
            and request.user.profile.role == Role.ADMIN
        )


class IsTrainerOrAdmin(BasePermission):
    """Allows access to Trainers or Admins."""
    def has_permission(self, request, view):
        return (
            hasattr(request.user, 'profile')
            and request.user.profile.role in (Role.TRAINER, Role.ADMIN)
        )


class IsTraineeOrAdmin(BasePermission):
    """Allows access to Trainees or Admins."""
    def has_permission(self, request, view):
        return (
            hasattr(request.user, 'profile')
            and request.user.profile.role in (Role.TRAINEE, Role.ADMIN)
        )
