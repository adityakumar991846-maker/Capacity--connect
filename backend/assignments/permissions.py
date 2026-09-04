"""
Permissions for assignments, project submissions, and grading workbench.
"""

from rest_framework.permissions import BasePermission
from core.models import Role
from enrollments.models import Enrollment, EnrollmentStatus


class IsEnrolledTraineeOrCourseTrainerOrAdmin(BasePermission):
    """
    Allows access if the user is an active enrolled trainee in the course,
    the course trainer, or an admin.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN:
            return True

        course = getattr(obj, 'course', None)
        if not course and hasattr(obj, 'assignment'):
            course = obj.assignment.course

        if not course:
            return True

        if course.trainer == request.user:
            return True

        return Enrollment.objects.filter(
            course=course,
            trainee=request.user,
        ).exclude(status=EnrollmentStatus.DROPPED).exists()


class IsCourseTrainerOrAdmin(BasePermission):
    """
    Allows actions (such as grading or creating assignments) only to the course trainer or an admin.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN:
            return True

        course = getattr(obj, 'course', None)
        if not course and hasattr(obj, 'assignment'):
            course = obj.assignment.course

        return course and course.trainer == request.user


class IsSubmissionOwnerOrCourseTrainerOrAdmin(BasePermission):
    """
    Allows access to submission deliverables and reviews to the trainee owner,
    the course trainer, or an admin.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN:
            return True

        if obj.trainee == request.user:
            return True

        return obj.assignment.course.trainer == request.user
