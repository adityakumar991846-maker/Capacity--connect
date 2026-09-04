"""
Custom DRF permission classes for the core module.
"""

from rest_framework.permissions import BasePermission
from .models import Role


class IsAdmin(BasePermission):
    """Allows access only to users with the ADMIN role."""
    def has_permission(self, request, view):
        return (
            hasattr(request.user, 'profile')
            and request.user.profile.role == Role.ADMIN
        )
