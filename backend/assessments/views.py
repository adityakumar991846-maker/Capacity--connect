"""
Views for the assessments module.

Provides Trainer assessment/MCQ CRUD and Trainee anti-cheat quiz taking & auto-grading.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Role
from courses.models import Course, Subject
from enrollments.models import Enrollment
from .models import (
    Assessment,
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentStatus,
    Question,
)
from core.permissions import IsAdmin
from .permissions import IsTraineeOrAdmin, IsTrainerOrAdmin
from .serializers import (
    AdminAssessmentListSerializer,
    AssessmentAttemptDetailSerializer,
    AssessmentAttemptRosterSerializer,
    AssessmentCreateUpdateSerializer,
    AssessmentSubmitSerializer,
    AssessmentTraineeListSerializer,
    AssessmentTraineeTakeSerializer,
    AssessmentTrainerDetailSerializer,
    AssessmentTrainerListSerializer,
    QuestionTrainerSerializer,
)


def _get_user_role(user):
    if user and hasattr(user, 'profile'):
        return user.profile.role
    return None


def _check_course_owner_or_admin(user, course):
    role = _get_user_role(user)
    if role == Role.ADMIN:
        return True
    if role == Role.TRAINER and course.trainer == user:
        return True
    raise PermissionDenied('You do not have permission to manage assessments for this course.')


def _check_assessment_owner_or_admin(user, assessment):
    return _check_course_owner_or_admin(user, assessment.course)


# =============================================================================
# TRAINER ASSESSMENT VIEWS
# =============================================================================

class TrainerCourseAssessmentListCreateView(APIView):
    """
    GET  /api/assessments/trainer/courses/<course_id>/ - List assessments for course
    POST /api/assessments/trainer/courses/<course_id>/ - Create assessment for course
    """
    permission_classes = [IsAuthenticated, IsTrainerOrAdmin]

    def get_course(self, course_id):
        course = get_object_or_404(Course, pk=course_id)
        _check_course_owner_or_admin(self.request.user, course)
        return course

    def get(self, request, course_id):
        course = self.get_course(course_id)
        assessments = course.assessments.all()
        serializer = AssessmentTrainerListSerializer(assessments, many=True)
        return Response(serializer.data)

    def post(self, request, course_id):
        course = self.get_course(course_id)
        serializer = AssessmentCreateUpdateSerializer(
            data=request.data,
            context={'request': request, 'course': course},
        )
        serializer.is_valid(raise_exception=True)
        assessment = serializer.save(course=course, created_by=request.user)
        return Response(
            AssessmentTrainerDetailSerializer(assessment).data,
            status=status.HTTP_201_CREATED,
        )


class TrainerAssessmentDetailView(APIView):
    """
    GET    /api/assessments/trainer/<pk>/ - View assessment details with questions
    PUT    /api/assessments/trainer/<pk>/ - Full update assessment
    PATCH  /api/assessments/trainer/<pk>/ - Partial update assessment
    DELETE /api/assessments/trainer/<pk>/ - Delete assessment
    """
    permission_classes = [IsAuthenticated, IsTrainerOrAdmin]

    def get_assessment(self, pk):
        assessment = get_object_or_404(Assessment, pk=pk)
        _check_assessment_owner_or_admin(self.request.user, assessment)
        return assessment

    def get(self, request, pk):
        assessment = self.get_assessment(pk)
        return Response(AssessmentTrainerDetailSerializer(assessment).data)

    def put(self, request, pk):
        assessment = self.get_assessment(pk)
        serializer = AssessmentCreateUpdateSerializer(
            assessment,
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(AssessmentTrainerDetailSerializer(updated).data)

    def patch(self, request, pk):
        assessment = self.get_assessment(pk)
        serializer = AssessmentCreateUpdateSerializer(
            assessment,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(AssessmentTrainerDetailSerializer(updated).data)

    def delete(self, request, pk):
        assessment = self.get_assessment(pk)
        assessment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrainerQuestionCreateView(APIView):
    """
    POST /api/assessments/trainer/<assessment_id>/questions/ - Add question to assessment
    """
    permission_classes = [IsAuthenticated, IsTrainerOrAdmin]

    def post(self, request, assessment_id):
        assessment = get_object_or_404(Assessment, pk=assessment_id)
        _check_assessment_owner_or_admin(request.user, assessment)

        serializer = QuestionTrainerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.save(assessment=assessment)
        return Response(
            QuestionTrainerSerializer(question).data,
            status=status.HTTP_201_CREATED,
        )


class TrainerQuestionDetailView(APIView):
    """
    PATCH  /api/assessments/trainer/questions/<pk>/ - Update question
    DELETE /api/assessments/trainer/questions/<pk>/ - Delete question
    """
    permission_classes = [IsAuthenticated, IsTrainerOrAdmin]

    def get_question(self, pk):
        question = get_object_or_404(Question, pk=pk)
        _check_assessment_owner_or_admin(self.request.user, question.assessment)
        return question

    def patch(self, request, pk):
        question = self.get_question(pk)
        serializer = QuestionTrainerSerializer(question, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(QuestionTrainerSerializer(updated).data)

    def delete(self, request, pk):
        question = self.get_question(pk)
        question.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrainerAssessmentResultsView(APIView):
    """
    GET /api/assessments/trainer/<assessment_id>/results/ - View student results roster
    """
    permission_classes = [IsAuthenticated, IsTrainerOrAdmin]

    def get(self, request, assessment_id):
        assessment = get_object_or_404(Assessment, pk=assessment_id)
        _check_assessment_owner_or_admin(request.user, assessment)

        attempts = assessment.attempts.select_related('trainee').all()
        serializer = AssessmentAttemptRosterSerializer(attempts, many=True)
        return Response(serializer.data)


# =============================================================================
# TRAINEE ASSESSMENT VIEWS
# =============================================================================

class TraineeCourseAssessmentListView(APIView):
    """
    GET /api/assessments/trainee/courses/<course_id>/ - List published assessments for enrolled course
    """
    permission_classes = [IsAuthenticated, IsTraineeOrAdmin]

    def get(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id)
        role = _get_user_role(request.user)

        # Enforce active enrollment
        if role != Role.ADMIN:
            is_enrolled = Enrollment.objects.filter(
                trainee=request.user,
                course=course,
            ).exclude(status='DROPPED').exists()

            if not is_enrolled:
                raise PermissionDenied('You must be enrolled in this course to view its assessments.')

        assessments = course.assessments.filter(status=AssessmentStatus.PUBLISHED)
        serializer = AssessmentTraineeListSerializer(
            assessments,
            many=True,
            context={'request': request},
        )
        return Response(serializer.data)


class TraineeAssessmentTakeView(APIView):
    """
    GET /api/assessments/trainee/<pk>/take/ - Fetch sanitized quiz questions (NO correct answers)
    """
    permission_classes = [IsAuthenticated, IsTraineeOrAdmin]

    def get(self, request, pk):
        assessment = get_object_or_404(Assessment, pk=pk)
        role = _get_user_role(request.user)

        # Require PUBLISHED status for trainees
        if role != Role.ADMIN and assessment.status != AssessmentStatus.PUBLISHED:
            raise PermissionDenied('This assessment is not currently available.')

        # Require active enrollment
        if role != Role.ADMIN:
            is_enrolled = Enrollment.objects.filter(
                trainee=request.user,
                course=assessment.course,
            ).exclude(status='DROPPED').exists()

            if not is_enrolled:
                raise PermissionDenied('You must be enrolled in this course to take this assessment.')

        serializer = AssessmentTraineeTakeSerializer(assessment)
        return Response(serializer.data)


class TraineeAssessmentSubmitView(APIView):
    """
    POST /api/assessments/trainee/<pk>/submit/ - Submit quiz answers, auto-grade, record attempt
    """
    permission_classes = [IsAuthenticated, IsTraineeOrAdmin]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, pk=pk)
        role = _get_user_role(request.user)

        if role != Role.ADMIN and assessment.status != AssessmentStatus.PUBLISHED:
            raise PermissionDenied('This assessment is not currently open for submissions.')

        if role != Role.ADMIN:
            enrollment = Enrollment.objects.filter(
                trainee=request.user,
                course=assessment.course,
            ).exclude(status='DROPPED').first()

            if not enrollment:
                raise PermissionDenied('You must be enrolled in this course to submit this assessment.')
        else:
            enrollment = None

        submit_serializer = AssessmentSubmitSerializer(data=request.data)
        submit_serializer.is_valid(raise_exception=True)
        submitted_answers = submit_serializer.validated_data.get('answers', [])
        submitted_map = {a['question_id']: a.get('selected_option') for a in submitted_answers}

        questions = list(assessment.questions.all())
        total_marks = sum(q.marks for q in questions)
        score = 0
        answer_records = []

        for q in questions:
            selected = submitted_map.get(q.id)
            is_correct = bool(selected and selected == q.correct_answer)
            marks_obtained = q.marks if is_correct else 0
            score += marks_obtained

            answer_records.append({
                'question': q,
                'selected_option': selected,
                'is_correct': is_correct,
                'marks_obtained': marks_obtained,
            })

        percentage = round((score / total_marks * 100.0), 2) if total_marks > 0 else 0.0
        passed = percentage >= assessment.passing_percentage

        attempt = AssessmentAttempt.objects.create(
            assessment=assessment,
            trainee=request.user,
            score=score,
            total_marks=total_marks,
            percentage=percentage,
            passed=passed,
            submitted_at=timezone.now(),
        )

        for ans in answer_records:
            AssessmentAnswer.objects.create(
                attempt=attempt,
                question=ans['question'],
                selected_option=ans['selected_option'],
                is_correct=ans['is_correct'],
                marks_obtained=ans['marks_obtained'],
            )

        # Subject module completion integration
        if assessment.subject and passed and enrollment:
            from enrollments.models import SubjectProgress
            sp, _ = SubjectProgress.objects.get_or_create(
                enrollment=enrollment,
                subject=assessment.subject,
            )
            sp.mark_completed(save=True)

        return Response(
            AssessmentAttemptDetailSerializer(attempt).data,
            status=status.HTTP_201_CREATED,
        )


class TraineeAttemptDetailView(APIView):
    """
    GET /api/assessments/trainee/attempts/<pk>/ - View past attempt breakdown
    """
    permission_classes = [IsAuthenticated, IsTraineeOrAdmin]

    def get(self, request, pk):
        attempt = get_object_or_404(AssessmentAttempt, pk=pk)
        role = _get_user_role(request.user)

        if role != Role.ADMIN and attempt.trainee != request.user:
            raise PermissionDenied('You do not have permission to view this assessment result.')

        serializer = AssessmentAttemptDetailSerializer(attempt)
        return Response(serializer.data)


class TraineeMyAttemptsView(APIView):
    """
    GET /api/assessments/trainee/my-attempts/ - List all past attempts by authenticated trainee
    """
    permission_classes = [IsAuthenticated, IsTraineeOrAdmin]

    def get(self, request):
        attempts = AssessmentAttempt.objects.filter(trainee=request.user)
        serializer = AssessmentAttemptDetailSerializer(attempts, many=True)
        return Response(serializer.data)


class AdminAssessmentListView(APIView):
    """
    GET /api/assessments/admin/all/ — All platform assessments (Admin only) with optional status filter and search.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        from django.db.models import Q
        assessments = (
            Assessment.objects.select_related('course', 'subject', 'created_by')
            .prefetch_related('questions', 'attempts')
            .all()
            .order_by('-created_at')
        )

        status_filter = request.query_params.get('status')
        if status_filter:
            assessments = assessments.filter(status=status_filter.upper())

        search = request.query_params.get('search')
        if search:
            assessments = assessments.filter(
                Q(title__icontains=search)
                | Q(course__title__icontains=search)
                | Q(created_by__username__icontains=search)
            )

        serializer = AdminAssessmentListSerializer(assessments, many=True)
        return Response(serializer.data)
