"""
Permission classes for Course Reviews (Step 14).
"""

from rest_framework.permissions import BasePermission
from core.models import Role
from enrollments.models import Enrollment, EnrollmentStatus


class IsEnrolledTrainee(BasePermission):
    """
    Ensures user is an enrolled trainee in the target course.
    Trainers who authored the course cannot review their own course.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        role = getattr(getattr(request.user, 'profile', None), 'role', None)
        if role != Role.TRAINEE:
            return False

        course_id = view.kwargs.get('course_id') or request.data.get('course')
        if not course_id:
            return True

        return Enrollment.objects.filter(
            trainee=request.user,
            course_id=course_id,
            status__in=[EnrollmentStatus.ENROLLED, EnrollmentStatus.COMPLETED]
        ).exists()


class IsReviewOwnerOrAdmin(BasePermission):
    """
    Allows mutation/deletion only by the review owner or platform admin.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        role = getattr(getattr(request.user, 'profile', None), 'role', None)
        if role == Role.ADMIN:
            return True

        return obj.trainee == request.user


class IsAdmin(BasePermission):
    """
    Allows access only to users with the ADMIN role.
    """
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, 'profile')
            and request.user.profile.role == Role.ADMIN
        )


class IsTrainer(BasePermission):
    """
    Allows access only to users with the TRAINER role.
    """
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, 'profile')
            and request.user.profile.role == Role.TRAINER
        )
