"""
Views for practical assignments, project submissions, and instructor grading.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Role
from courses.models import Course, Subject
from courses.permissions import IsTrainerOrAdmin
from enrollments.models import Enrollment, EnrollmentStatus
from .models import (
    Assignment,
    AssignmentSubmission,
    SubmissionReview,
    SubmissionType,
    SubmissionStatus,
)
from .serializers import (
    AssignmentListSerializer,
    AssignmentDetailSerializer,
    AssignmentCreateUpdateSerializer,
    AssignmentSubmissionSerializer,
    AssignmentSubmissionCreateSerializer,
    SubmissionGradeSerializer,
    TrainerPendingReviewItemSerializer,
)


def _user_has_course_access(user, course):
    """
    Checks if user is admin, course trainer, or active enrolled trainee.
    """
    if not user or not user.is_authenticated:
        return False
    if hasattr(user, 'profile') and user.profile.role == Role.ADMIN:
        return True
    if course.trainer == user:
        return True
    return Enrollment.objects.filter(
        course=course,
        trainee=user,
    ).exclude(status=EnrollmentStatus.DROPPED).exists()


class CourseAssignmentListCreateView(APIView):
    """
    GET /api/assignments/courses/<course_id>/ — List assignments for course.
    POST /api/assignments/courses/<course_id>/ — Create new assignment (Trainer/Admin).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id)
        if not _user_has_course_access(request.user, course):
            return Response(
                {'detail': 'You must be enrolled in this course to view assignments.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        is_staff = hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN
        is_trainer = course.trainer == request.user

        assignments = Assignment.objects.filter(course=course).select_related('subject', 'course')
        if not (is_staff or is_trainer):
            assignments = assignments.filter(is_published=True)

        serializer = AssignmentListSerializer(assignments, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id)
        is_staff = hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN
        is_trainer = course.trainer == request.user

        if not (is_staff or is_trainer):
            return Response(
                {'detail': 'Only the course trainer or an admin can create assignments.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AssignmentCreateUpdateSerializer(
            data=request.data,
            context={'course': course, 'request': request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        subject = None
        subject_id = validated_data.get('subject_id')
        if subject_id:
            subject = get_object_or_404(Subject, pk=subject_id, course=course)

        assignment = Assignment.objects.create(
            course=course,
            subject=subject,
            title=validated_data['title'],
            description=validated_data['description'],
            submission_type=validated_data.get('submission_type', SubmissionType.LINK),
            max_score=validated_data.get('max_score', 100),
            passing_score=validated_data.get('passing_score', 60),
            due_date=validated_data.get('due_date'),
            is_mandatory=validated_data.get('is_mandatory', True),
            is_published=validated_data.get('is_published', True),
        )

        detail_serializer = AssignmentDetailSerializer(assignment, context={'request': request})
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)


class AssignmentDetailView(APIView):
    """
    GET /api/assignments/<pk>/ — Retrieve assignment details.
    PATCH /api/assignments/<pk>/ — Update assignment (Trainer/Admin).
    DELETE /api/assignments/<pk>/ — Delete assignment (Trainer/Admin).
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(
            Assignment.objects.select_related('course', 'course__trainer', 'subject'),
            pk=pk,
        )

    def get(self, request, pk):
        assignment = self.get_object(pk)
        if not _user_has_course_access(request.user, assignment.course):
            return Response(
                {'detail': 'You must be enrolled in this course to view this assignment.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = AssignmentDetailSerializer(assignment, context={'request': request})
        return Response(serializer.data)

    def patch(self, request, pk):
        assignment = self.get_object(pk)
        is_staff = hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN
        is_trainer = assignment.course.trainer == request.user

        if not (is_staff or is_trainer):
            return Response(
                {'detail': 'Only the course trainer or an admin can edit this assignment.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AssignmentCreateUpdateSerializer(
            assignment,
            data=request.data,
            partial=True,
            context={'course': assignment.course, 'request': request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(AssignmentDetailSerializer(assignment, context={'request': request}).data)

    def delete(self, request, pk):
        assignment = self.get_object(pk)
        is_staff = hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN
        is_trainer = assignment.course.trainer == request.user

        if not (is_staff or is_trainer):
            return Response(
                {'detail': 'Only the course trainer or an admin can delete this assignment.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssignmentMySubmissionView(APIView):
    """
    GET /api/assignments/<pk>/my-submission/ — Get logged-in trainee's submission for an assignment.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk)
        submission = AssignmentSubmission.objects.filter(
            assignment=assignment,
            trainee=request.user,
        ).select_related('assignment', 'trainee', 'review', 'review__reviewer').first()

        if not submission:
            return Response(
                {'detail': 'No submission found for this assignment.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AssignmentSubmissionSerializer(submission)
        return Response(serializer.data)


class AssignmentSubmitView(APIView):
    """
    POST /api/assignments/<pk>/submit/ — Submit or update project deliverable (Enrolled Trainee).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        assignment = get_object_or_404(Assignment.objects.select_related('course'), pk=pk)

        if not assignment.is_published:
            return Response(
                {'detail': 'This assignment is not currently published.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        enrollment = Enrollment.objects.filter(
            course=assignment.course,
            trainee=request.user,
        ).exclude(status=EnrollmentStatus.DROPPED).first()

        if not enrollment:
            return Response(
                {'detail': 'You must have an active enrollment in this course to submit assignments.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AssignmentSubmissionCreateSerializer(
            data=request.data,
            context={'assignment': assignment, 'request': request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        status_choice = validated_data.get('status', SubmissionStatus.SUBMITTED)

        submission, created = AssignmentSubmission.objects.get_or_create(
            assignment=assignment,
            trainee=request.user,
            defaults={
                'enrollment': enrollment,
                'submission_link': validated_data.get('submission_link', ''),
                'submission_text': validated_data.get('submission_text', ''),
                'submission_file': request.FILES.get('submission_file'),
                'status': status_choice,
            },
        )

        if not created:
            submission.submission_link = validated_data.get('submission_link', submission.submission_link)
            submission.submission_text = validated_data.get('submission_text', submission.submission_text)
            if 'submission_file' in request.FILES:
                submission.submission_file = request.FILES['submission_file']
            submission.status = status_choice
            submission.save()

        out_serializer = AssignmentSubmissionSerializer(submission)
        res_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(out_serializer.data, status=res_status)


class AssignmentSubmissionListView(APIView):
    """
    GET /api/assignments/<pk>/submissions/ — List all trainee submissions for an assignment (Trainer/Admin).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        assignment = get_object_or_404(
            Assignment.objects.select_related('course', 'course__trainer'), pk=pk
        )
        is_staff = hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN
        is_trainer = assignment.course.trainer == request.user

        if not (is_staff or is_trainer):
            return Response(
                {'detail': 'Only the course trainer or an admin can view student submissions.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        submissions = assignment.submissions.select_related(
            'trainee', 'review', 'review__reviewer'
        ).order_by('-submitted_at')

        serializer = AssignmentSubmissionSerializer(submissions, many=True)
        return Response(serializer.data)


class SubmissionGradeView(APIView):
    """
    POST /api/assignments/submissions/<pk>/grade/ — Grade a trainee's submission (Trainer/Admin).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        submission = get_object_or_404(
            AssignmentSubmission.objects.select_related('assignment', 'assignment__course', 'trainee'),
            pk=pk,
        )
        course = submission.assignment.course
        is_staff = hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN
        is_trainer = course.trainer == request.user

        if not (is_staff or is_trainer):
            return Response(
                {'detail': 'Only the course trainer or an admin can grade this submission.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = SubmissionGradeSerializer(
            data=request.data,
            context={'assignment': submission.assignment, 'request': request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        score = serializer.validated_data['score']
        feedback = serializer.validated_data['feedback']
        request_resubmission = serializer.validated_data['request_resubmission']

        passed = (score >= submission.assignment.passing_score) and not request_resubmission

        if request_resubmission:
            submission.status = SubmissionStatus.RESUBMISSION_REQUESTED
        else:
            submission.status = SubmissionStatus.GRADED
        submission.save(update_fields=['status'])

        review, _ = SubmissionReview.objects.update_or_create(
            submission=submission,
            defaults={
                'reviewer': request.user,
                'score': score,
                'passed': passed,
                'feedback': feedback,
            },
        )

        return Response(AssignmentSubmissionSerializer(submission).data, status=status.HTTP_200_OK)


class TrainerPendingReviewsView(APIView):
    """
    GET /api/assignments/trainer/pending-reviews/ — Live queue of submissions awaiting grading.
    """
    permission_classes = [IsAuthenticated, IsTrainerOrAdmin]

    def get(self, request):
        is_admin = hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN

        if is_admin:
            submissions = AssignmentSubmission.objects.all()
        else:
            submissions = AssignmentSubmission.objects.filter(
                assignment__course__trainer=request.user
            )

        # Filter by status: SUBMITTED or UNDER_REVIEW (pending review)
        status_filter = request.query_params.get('status')
        if status_filter:
            submissions = submissions.filter(status=status_filter.upper())
        else:
            submissions = submissions.filter(
                status__in=[SubmissionStatus.SUBMITTED, SubmissionStatus.UNDER_REVIEW]
            )

        submissions = submissions.select_related(
            'assignment', 'assignment__course', 'assignment__subject', 'trainee'
        ).order_by('submitted_at')

        serializer = TrainerPendingReviewItemSerializer(submissions, many=True)
        return Response(serializer.data)
