"""
Views for course enrollments and trainee learning tracking.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Role
from courses.models import Course, Subject
from .models import Enrollment, EnrollmentStatus, SubjectProgress
from .permissions import IsAdmin, IsTrainee, IsTrainer
from .serializers import (
    EnrollmentCreateSerializer,
    EnrollmentDetailSerializer,
    EnrollmentListSerializer,
    SubjectProgressSerializer,
)


def _get_user_role(user):
    """Safely retrieve user profile role."""
    if user and hasattr(user, 'profile'):
        return user.profile.role
    return None


def _ensure_subject_progresses_synced(enrollment):
    """
    Ensure all current subjects of the enrolled course have a SubjectProgress
    entry (in case new subjects were added after initial enrollment).
    """
    course_subjects = enrollment.course.subjects.all()
    existing_subject_ids = set(
        enrollment.subject_progresses.values_list('subject_id', flat=True)
    )
    for subject in course_subjects:
        if subject.id not in existing_subject_ids:
            SubjectProgress.objects.create(
                enrollment=enrollment,
                subject=subject,
                completed=False,
            )


class EnrollmentListCreateView(APIView):
    """
    GET  /api/enrollments/ - List visible enrollments based on user role
    POST /api/enrollments/ - Enroll in a course (Trainee only)
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsTrainee()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        role = _get_user_role(user)
        course_id = self.request.query_params.get('course')

        if role == Role.ADMIN:
            qs = Enrollment.objects.all()
        elif role == Role.TRAINER:
            qs = Enrollment.objects.filter(course__trainer=user)
        else: # Trainee and default
            qs = Enrollment.objects.filter(trainee=user)

        if course_id:
            qs = qs.filter(course_id=course_id)

        return qs

    def get(self, request):
        enrollments = self.get_queryset()
        serializer = EnrollmentListSerializer(enrollments, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = EnrollmentCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        enrollment = serializer.save()
        return Response(
            EnrollmentDetailSerializer(enrollment).data,
            status=status.HTTP_201_CREATED,
        )


class EnrollmentDetailView(APIView):
    """
    GET /api/enrollments/<pk>/ - View detailed enrollment & learning progress
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        enrollment = get_object_or_404(Enrollment, pk=pk)
        user = self.request.user
        role = _get_user_role(user)

        if role == Role.ADMIN:
            pass
        elif role == Role.TRAINER:
            if enrollment.course.trainer != user:
                raise PermissionDenied('You do not have permission to view this enrollment.')
        elif role == Role.TRAINEE:
            if enrollment.trainee != user:
                raise get_object_or_404(Enrollment, pk=0)
        else:
            raise PermissionDenied('Access denied.')

        _ensure_subject_progresses_synced(enrollment)
        return enrollment

    def get(self, request, pk):
        enrollment = self.get_object(pk)
        return Response(EnrollmentDetailSerializer(enrollment).data)


class SubjectCompletionToggleView(APIView):
    """
    POST /api/enrollments/<pk>/subjects/<subject_id>/complete/
    Marks a course subject complete or incomplete for the trainee's enrollment.
    """
    permission_classes = [IsAuthenticated, IsTrainee]

    def post(self, request, pk, subject_id):
        enrollment = get_object_or_404(Enrollment, pk=pk)
        if enrollment.trainee != request.user:
            raise PermissionDenied('You can only update progress for your own enrollment.')

        if enrollment.status == EnrollmentStatus.DROPPED:
            return Response(
                {'detail': 'Cannot update progress on a dropped enrollment.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subject = get_object_or_404(Subject, pk=subject_id)
        if subject.course_id != enrollment.course_id:
            return Response(
                {'detail': 'Subject does not belong to the enrolled course.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get or create progress record
        progress, _ = SubjectProgress.objects.get_or_create(
            enrollment=enrollment,
            subject=subject,
        )

        # Determine target state (if explicit 'completed' in body, use it; else toggle)
        if 'completed' in request.data:
            target_completed = bool(request.data['completed'])
        else:
            target_completed = not progress.completed

        if target_completed:
            progress.mark_completed(save=True)
        else:
            progress.mark_incomplete(save=True)

        enrollment.refresh_from_db()
        return Response(EnrollmentDetailSerializer(enrollment).data)


class EnrollmentDropView(APIView):
    """
    POST /api/enrollments/<pk>/drop/ - Drop/cancel an active enrollment
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        enrollment = get_object_or_404(Enrollment, pk=pk)
        user = request.user
        role = _get_user_role(user)

        if role != Role.ADMIN and enrollment.trainee != user:
            raise PermissionDenied('You cannot drop another trainee\'s enrollment.')

        enrollment.status = EnrollmentStatus.DROPPED
        enrollment.save(update_fields=['status', 'last_accessed_at'])

        return Response(EnrollmentDetailSerializer(enrollment).data)


class CourseEnrollmentsListView(APIView):
    """
    GET /api/courses/<course_id>/enrollments/ - View enrollment roster for a course
    (Course Trainer and Admin only)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id)
        user = request.user
        role = _get_user_role(user)

        if role == Role.ADMIN or (role == Role.TRAINER and course.trainer == user):
            enrollments = course.enrollments.all()
            serializer = EnrollmentListSerializer(enrollments, many=True)
            return Response(serializer.data)

        raise PermissionDenied('You do not have permission to view enrollments for this course.')
