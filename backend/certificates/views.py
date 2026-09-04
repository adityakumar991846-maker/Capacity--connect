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
        certs = Certificate.objects.filter(trainee=request.user)
        serializer = CertificateListSerializer(certs, many=True)
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
