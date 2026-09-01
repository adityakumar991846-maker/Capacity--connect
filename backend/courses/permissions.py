"""
Custom DRF permission classes for the courses module.

Imports ``Role`` from the core app to check user roles.
All permissions require the user to be authenticated first
(handled by the global DRF ``IsAuthenticated`` default).
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
