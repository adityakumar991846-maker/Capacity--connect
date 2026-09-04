"""
Views for the certificates and credential verification engine.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Role
from courses.models import Course
from enrollments.models import Enrollment, EnrollmentStatus
from .models import Certificate
from .permissions import IsAdmin, IsTraineeOrAdmin, IsTrainerOrAdmin
from .serializers import (
    CertificateDetailSerializer,
    CertificateListSerializer,
    CertificatePublicVerifySerializer,
    CertificateRevokeSerializer,
    CertificateTrainerRosterSerializer,
    AdminCertificateListSerializer,
    TraineeCertificateSummarySerializer,
    AcademicTranscriptSerializer,
)


def _get_user_role(user):
    if user and hasattr(user, 'profile'):
        return user.profile.role
    return None


def check_and_issue_certificate(enrollment):
    """
    Checks course completion eligibility and auto-issues a Certificate if earned.
    Returns (certificate, is_created_or_existing, error_message).
    """
    # Check if certificate already exists
    existing_cert = Certificate.objects.filter(enrollment=enrollment).first()
    if existing_cert:
        return existing_cert, False, None

    # Check enrollment status & curriculum completion
    if enrollment.status == EnrollmentStatus.DROPPED:
        return None, False, 'Enrollment was dropped.'

    total_subjects = enrollment.course.subjects.count()
    if total_subjects == 0:
        return None, False, 'Course has no curriculum modules configured.'

    completed_subjects_count = enrollment.subject_progresses.filter(
        completed=True,
        subject__course=enrollment.course,
    ).count()

    if completed_subjects_count < total_subjects:
        return None, False, f'Curriculum incomplete ({completed_subjects_count}/{total_subjects} modules finished).'

    # Ensure enrollment status is updated to COMPLETED
    if enrollment.status != EnrollmentStatus.COMPLETED:
        enrollment.update_completion_status(save=True)

    # Check published course assessments
    published_assessments = enrollment.course.assessments.filter(status='PUBLISHED')
    best_percentages = []

    for assess in published_assessments:
        passed_attempts = assess.attempts.filter(trainee=enrollment.trainee, passed=True)
        if not passed_attempts.exists():
            return None, False, f'Required assessment "{assess.title}" has not been passed.'
        best_pct = max(a.percentage for a in passed_attempts)
        best_percentages.append(best_pct)

    # Check mandatory published assignments (Step 13)
    if hasattr(enrollment.course, 'assignments'):
        mandatory_assignments = enrollment.course.assignments.filter(
            is_mandatory=True,
            is_published=True,
        )
        for assign in mandatory_assignments:
            passed_sub = assign.submissions.filter(
                trainee=enrollment.trainee,
                review__passed=True,
            ).first()
            if not passed_sub:
                return None, False, f'Mandatory assignment "{assign.title}" has not been passed.'
            if hasattr(passed_sub, 'review') and passed_sub.review:
                # Factor in assignment percentage if available
                assign_pct = round((passed_sub.review.score / assign.max_score) * 100, 2)
                best_percentages.append(assign_pct)

    # Calculate final grade
    if best_percentages:
        final_grade = round(sum(best_percentages) / len(best_percentages), 2)
    else:
        final_grade = 100.0

    # Issue unique certificate
    cert, created = Certificate.objects.get_or_create(
        enrollment=enrollment,
        defaults={
            'trainee': enrollment.trainee,
            'course': enrollment.course,
            'final_grade_percentage': final_grade,
        },
    )
    return cert, created, None


# =============================================================================
# TRAINEE CERTIFICATE VIEWS
# =============================================================================

class TraineeMyCertificatesView(APIView):
    """
    GET /api/certificates/my-certificates/ - List all certificates earned by trainee
    """
    permission_classes = [IsAuthenticated, IsTraineeOrAdmin]

    def get(self, request):
        certs = Certificate.objects.filter(trainee=request.user).select_related('course', 'course__trainer')
        serializer = CertificateListSerializer(certs, many=True)
        return Response(serializer.data)


class TraineeCertificateSummaryView(APIView):
    """
    GET /api/certificates/my-summary/ - Trainee achievement KPIs and certification stats
    """
    permission_classes = [IsAuthenticated, IsTraineeOrAdmin]

    def get(self, request):
        certs = Certificate.objects.filter(
            trainee=request.user,
            is_revoked=False
        ).select_related('course')

        total_certs = certs.count()
        total_hours = sum(c.course.duration_hours or 0 for c in certs)
        grades = [c.final_grade_percentage for c in certs if c.final_grade_percentage is not None]
        avg_grade = round(sum(grades) / len(grades), 2) if grades else 0.0
        categories = list(set(c.course.category for c in certs if c.course.category))
        distinctions = sum(1 for c in certs if c.honors_tier == 'DISTINCTION')

        data = {
            'total_certificates': total_certs,
            'cumulative_grade_average': avg_grade,
            'total_certified_hours': total_hours,
            'categories_mastered': categories,
            'distinctions_count': distinctions,
        }
        serializer = TraineeCertificateSummarySerializer(data)
        return Response(serializer.data)


class TraineeTranscriptView(APIView):
    """
    GET /api/certificates/transcript/ - Official academic transcript document
    """
    permission_classes = [IsAuthenticated, IsTraineeOrAdmin]

    def get(self, request):
        from django.utils import timezone
        user = request.user
        certs = Certificate.objects.filter(trainee=user).select_related('course', 'course__trainer').order_by('issued_at')

        records = []
        valid_certs = [c for c in certs if not c.is_revoked]
        total_hours = sum(c.course.duration_hours or 0 for c in valid_certs)
        grades = [c.final_grade_percentage for c in valid_certs if c.final_grade_percentage is not None]
        avg_grade = round(sum(grades) / len(grades), 2) if grades else 0.0

        for c in certs:
            trainer_name = 'Capacity Connect Instructor'
            if c.course.trainer:
                full = f'{c.course.trainer.first_name} {c.course.trainer.last_name}'.strip()
                trainer_name = full or c.course.trainer.username

            records.append({
                'course_id': c.course.id,
                'course_title': c.course.title,
                'category': c.course.category or 'General',
                'level': c.course.level,
                'duration_hours': c.course.duration_hours or 0,
                'trainer_name': trainer_name,
                'completion_date': c.issued_at,
                'final_grade': c.final_grade_percentage,
                'honors_tier': c.honors_tier,
                'certificate_code': c.certificate_code,
                'is_valid': not c.is_revoked,
            })

        student_name = f'{user.first_name} {user.last_name}'.strip() or user.username
        data = {
            'student_id': user.id,
            'student_name': student_name,
            'student_email': user.email,
            'generated_at': timezone.now(),
            'total_courses_completed': len(valid_certs),
            'cumulative_grade_average': avg_grade,
            'total_hours_completed': total_hours,
            'records': records,
        }
        serializer = AcademicTranscriptSerializer(data)
        return Response(serializer.data)


class TraineeCertificateDetailView(APIView):
    """
    GET /api/certificates/<pk>/ - Detailed printable certificate view
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        cert = get_object_or_404(Certificate, pk=pk)
        role = _get_user_role(request.user)

        # Allow trainee owner, course trainer, or admin
        is_owner = (cert.trainee == request.user)
        is_course_trainer = (cert.course.trainer == request.user)
        is_admin = (role == Role.ADMIN)

        if not (is_owner or is_course_trainer or is_admin):
            raise PermissionDenied('You do not have permission to view this certificate.')

        serializer = CertificateDetailSerializer(cert)
        return Response(serializer.data)


class TraineeClaimCertificateView(APIView):
    """
    POST /api/certificates/claim/<enrollment_id>/ - Check eligibility and claim certificate
    """
    permission_classes = [IsAuthenticated, IsTraineeOrAdmin]

    def post(self, request, enrollment_id):
        enrollment = get_object_or_404(Enrollment, pk=enrollment_id)
        role = _get_user_role(request.user)

        if role != Role.ADMIN and enrollment.trainee != request.user:
            raise PermissionDenied('You can only claim certificates for your own enrollments.')

        cert, created, err = check_and_issue_certificate(enrollment)
        if not cert:
            return Response({'detail': err}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CertificateDetailSerializer(cert)
        resp_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(serializer.data, status=resp_status)


# =============================================================================
# PUBLIC VERIFICATION VIEW
# =============================================================================

class PublicCertificateVerifyView(APIView):
    """
    GET /api/certificates/verify/<identifier>/ - Public credential verification (AllowAny)
    """
    permission_classes = [AllowAny]

    def get(self, request, identifier):
        identifier = identifier.strip()
        cert = Certificate.objects.filter(
            Q(certificate_code__iexact=identifier) | Q(verification_hash__iexact=identifier)
        ).select_related('trainee', 'course', 'course__trainer').first()

        if not cert:
            return Response(
                {'detail': 'Certificate not found. The provided verification code is invalid.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CertificatePublicVerifySerializer(cert)
        return Response(serializer.data)


# =============================================================================
# TRAINER & ADMIN GOVERNANCE VIEWS
# =============================================================================

class TrainerCourseCertificatesView(APIView):
    """
    GET /api/certificates/trainer/courses/<course_id>/ - Course certificate issuance log
    """
    permission_classes = [IsAuthenticated, IsTrainerOrAdmin]

    def get(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id)
        role = _get_user_role(request.user)

        if role != Role.ADMIN and course.trainer != request.user:
            raise PermissionDenied('You do not have permission to view certificates for this course.')

        certs = course.certificates.select_related('trainee').all()
        serializer = CertificateTrainerRosterSerializer(certs, many=True)
        return Response(serializer.data)


class AdminRevokeCertificateView(APIView):
    """
    POST /api/certificates/<pk>/revoke/ - Admin revocation with reason
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        cert = get_object_or_404(Certificate, pk=pk)
        serializer = CertificateRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reason = serializer.validated_data['reason']
        cert.revoke(admin_user=request.user, reason=reason)
        return Response(CertificateDetailSerializer(cert).data)


class AdminReinstateCertificateView(APIView):
    """
    POST /api/certificates/<pk>/reinstate/ - Admin reinstatement
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        cert = get_object_or_404(Certificate, pk=pk)
        cert.reinstate()
        return Response(CertificateDetailSerializer(cert).data)


class AdminCertificateListView(APIView):
    """
    GET /api/certificates/admin/all/ — All platform certificates (Admin only) with optional search.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        certs = Certificate.objects.select_related('trainee', 'course').all().order_by('-issued_at')

        search = request.query_params.get('search')
        if search:
            certs = certs.filter(
                Q(certificate_code__icontains=search)
                | Q(trainee__username__icontains=search)
                | Q(trainee__email__icontains=search)
                | Q(course__title__icontains=search)
            )

        serializer = AdminCertificateListSerializer(certs, many=True)
        return Response(serializer.data)
