"""
Custom DRF permissions for the discussions app.
"""

from rest_framework.permissions import BasePermission
from core.models import Role
from enrollments.models import Enrollment, EnrollmentStatus


class IsEnrolledOrTrainerOrAdmin(BasePermission):
    """
    Grants access if the user is an active enrolled trainee in the course,
    the course trainer, or a platform admin.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # If obj is a DiscussionThread
        course = getattr(obj, 'course', None)
        if not course and hasattr(obj, 'thread'):
            course = obj.thread.course

        if not course:
            return True

        if hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN:
            return True

        if course.trainer == request.user:
            return True

        return Enrollment.objects.filter(
            course=course,
            trainee=request.user,
        ).exclude(status=EnrollmentStatus.DROPPED).exists()


class IsAuthorOrAdmin(BasePermission):
    """
    Allows modification/deletion only by the author of the thread/reply or an admin.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN:
            return True

        return obj.author == request.user


class IsCourseTrainerOrAdmin(BasePermission):
    """
    Allows actions (e.g. pinning, endorsing) only to the course trainer or an admin.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN:
            return True

        course = getattr(obj, 'course', None)
        if not course and hasattr(obj, 'thread'):
            course = obj.thread.course

        return course and course.trainer == request.user
