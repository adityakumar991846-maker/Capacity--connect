"""
Unit tests for Certificates and Credential Verification Engine.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Role, UserProfile
from courses.models import Course, CourseLevel, Subject, CourseStatus
from enrollments.models import Enrollment, EnrollmentStatus, SubjectProgress
from assessments.models import Assessment, AssessmentAttempt, AssessmentStatus
from certificates.models import Certificate, CertificateStatus
from certificates.views import check_and_issue_certificate

User = get_user_model()


class CertificateEngineTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Users & Profiles
        self.admin = User.objects.create_user(
            username='admin_user',
            email='admin@example.com',
            password='Password123!'
        )
        UserProfile.objects.create(user=self.admin, role=Role.ADMIN)

        self.trainer_1 = User.objects.create_user(
            username='trainer_one',
            email='trainer1@example.com',
            password='Password123!'
        )
        UserProfile.objects.create(user=self.trainer_1, role=Role.TRAINER)

        self.trainer_2 = User.objects.create_user(
            username='trainer_two',
            email='trainer2@example.com',
            password='Password123!'
        )
        UserProfile.objects.create(user=self.trainer_2, role=Role.TRAINER)

        self.trainee_1 = User.objects.create_user(
            username='trainee_one',
            email='trainee1@example.com',
            password='Password123!'
        )
        UserProfile.objects.create(user=self.trainee_1, role=Role.TRAINEE)

        self.trainee_2 = User.objects.create_user(
            username='trainee_two',
            email='trainee2@example.com',
            password='Password123!'
        )
        UserProfile.objects.create(user=self.trainee_2, role=Role.TRAINEE)

        # Course by Trainer 1
        self.course_1 = Course.objects.create(
            title='Fullstack Web Development',
            description='Complete web stack course',
            category='Web Development',
            level=CourseLevel.BEGINNER,
            duration_hours=20,
            trainer=self.trainer_1,
            status=CourseStatus.PUBLISHED
        )
        self.subject_1_1 = Subject.objects.create(
            course=self.course_1,
            title='HTML & CSS Fundamentals',
            description='Basic HTML & CSS',
            order=1
        )
        self.subject_1_2 = Subject.objects.create(
            course=self.course_1,
            title='JavaScript Deep Dive',
            description='Modern JS syntax and features',
            order=2
        )

        # Course by Trainer 2
        self.course_2 = Course.objects.create(
            title='Data Science Bootcamp',
            description='Python for Data Science',
            category='Data Science',
            level=CourseLevel.INTERMEDIATE,
            duration_hours=30,
            trainer=self.trainer_2,
            status=CourseStatus.PUBLISHED
        )
        self.subject_2_1 = Subject.objects.create(
            course=self.course_2,
            title='NumPy and Pandas',
            description='Data manipulation',
            order=1
        )

        # Enrollments
        self.enrollment_1 = Enrollment.objects.create(
            trainee=self.trainee_1,
            course=self.course_1,
            status=EnrollmentStatus.ENROLLED
        )
        self.enrollment_2 = Enrollment.objects.create(
            trainee=self.trainee_2,
            course=self.course_2,
            status=EnrollmentStatus.ENROLLED
        )

    def _complete_subjects_for_course_1(self, trainee):
        enrollment = Enrollment.objects.get(trainee=trainee, course=self.course_1)
        sp1, _ = SubjectProgress.objects.get_or_create(enrollment=enrollment, subject=self.subject_1_1)
        sp1.completed = True
        sp1.save()
        sp2, _ = SubjectProgress.objects.get_or_create(enrollment=enrollment, subject=self.subject_1_2)
        sp2.completed = True
        sp2.save()
        enrollment.update_completion_status(save=True)
        return enrollment

    # --- 1. Eligibility & Issuance Logic ---

    def test_eligible_trainee_can_claim_certificate_when_course_and_assessments_completed(self):
        """Trainee who completed 100% subjects and passed all published assessments can claim certificate."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)

        # Add published assessment and passing attempt
        assessment = Assessment.objects.create(
            course=self.course_1,
            created_by=self.trainer_1,
            title='Final Assessment',
            passing_percentage=60,
            status=AssessmentStatus.PUBLISHED
        )
        AssessmentAttempt.objects.create(
            assessment=assessment,
            trainee=self.trainee_1,
            score=85,
            total_marks=100,
            percentage=85.0,
            passed=True
        )

        self.client.force_authenticate(user=self.trainee_1)
        url = reverse('trainee-claim-certificate', kwargs={'enrollment_id': enrollment.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['is_revoked'], False)
        self.assertTrue(response.data['certificate_code'].startswith('CC-'))
        self.assertEqual(response.data['final_grade_percentage'], 85.0)
        self.assertEqual(Certificate.objects.filter(trainee=self.trainee_1, course=self.course_1).count(), 1)

    def test_ineligible_trainee_with_incomplete_subjects_cannot_claim(self):
        """Incomplete subjects prevent certificate claim."""
        self.client.force_authenticate(user=self.trainee_1)
        url = reverse('trainee-claim-certificate', kwargs={'enrollment_id': self.enrollment_1.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('incomplete', response.data['detail'].lower())
        self.assertFalse(Certificate.objects.filter(trainee=self.trainee_1, course=self.course_1).exists())

    def test_ineligible_trainee_with_failed_assessment_cannot_claim(self):
        """Failed assessment prevents certificate claim even with 100% subject progress."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        assessment = Assessment.objects.create(
            course=self.course_1,
            created_by=self.trainer_1,
            title='Final Assessment',
            passing_percentage=60,
            status=AssessmentStatus.PUBLISHED
        )
        # Attempt failed
        AssessmentAttempt.objects.create(
            assessment=assessment,
            trainee=self.trainee_1,
            score=40,
            total_marks=100,
            percentage=40.0,
            passed=False
        )

        self.client.force_authenticate(user=self.trainee_1)
        url = reverse('trainee-claim-certificate', kwargs={'enrollment_id': enrollment.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not been passed', response.data['detail'])

    def test_course_without_assessments_issues_certificate_at_100_percent_progress(self):
        """Courses without any published assessments issue a certificate upon 100% subject completion."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)

        self.client.force_authenticate(user=self.trainee_1)
        url = reverse('trainee-claim-certificate', kwargs={'enrollment_id': enrollment.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['final_grade_percentage'], 100.0)

    def test_draft_assessments_do_not_block_certificate_eligibility(self):
        """Draft assessments are ignored when evaluating passing requirements."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        Assessment.objects.create(
            course=self.course_1,
            created_by=self.trainer_1,
            title='Draft Assessment In Progress',
            passing_percentage=60,
            status=AssessmentStatus.DRAFT
        )

        self.client.force_authenticate(user=self.trainee_1)
        url = reverse('trainee-claim-certificate', kwargs={'enrollment_id': enrollment.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # --- 2. Deduplication & Idempotency ---

    def test_claiming_certificate_twice_returns_existing_certificate(self):
        """Calling claim again for already issued certificate returns 200 OK with existing data."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        self.client.force_authenticate(user=self.trainee_1)
        url = reverse('trainee-claim-certificate', kwargs={'enrollment_id': enrollment.id})
        resp1 = self.client.post(url)
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        code1 = resp1.data['certificate_code']

        resp2 = self.client.post(url)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['certificate_code'], code1)
        self.assertEqual(Certificate.objects.filter(trainee=self.trainee_1, course=self.course_1).count(), 1)

    # --- 3. Code Generation & Immutability ---

    def test_certificate_code_format_and_sha256_hash_integrity(self):
        """Certificate has valid CC-YYYY-XXXX-XXXX code and a 64-character SHA-256 hash."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        cert, _, _ = check_and_issue_certificate(enrollment)
        self.assertIsNotNone(cert)
        self.assertTrue(cert.certificate_code.startswith('CC-'))
        self.assertEqual(len(cert.certificate_code.split('-')), 4)
        self.assertEqual(len(cert.verification_hash), 64)

    # --- 4. Trainee Access & Isolation ---

    def test_trainee_can_list_only_own_certificates(self):
        """Trainee gets list containing only their own certificates."""
        enrollment1 = self._complete_subjects_for_course_1(self.trainee_1)
        check_and_issue_certificate(enrollment1)

        # Also complete for trainee 2 on course 2
        sp2_1, _ = SubjectProgress.objects.get_or_create(enrollment=self.enrollment_2, subject=self.subject_2_1)
        sp2_1.completed = True
        sp2_1.save()
        self.enrollment_2.update_completion_status(save=True)
        check_and_issue_certificate(self.enrollment_2)

        self.client.force_authenticate(user=self.trainee_1)
        url = reverse('trainee-my-certificates')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['course_title'], self.course_1.title)

    def test_trainee_cannot_view_another_trainees_certificate_detail(self):
        """Trainee receiving 403 when trying to directly access another trainee's certificate."""
        enrollment2 = self.enrollment_2
        sp2_1, _ = SubjectProgress.objects.get_or_create(enrollment=enrollment2, subject=self.subject_2_1)
        sp2_1.completed = True
        sp2_1.save()
        enrollment2.update_completion_status(save=True)
        cert2, _, _ = check_and_issue_certificate(enrollment2)

        self.client.force_authenticate(user=self.trainee_1)
        url = reverse('trainee-certificate-detail', kwargs={'pk': cert2.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- 5. Public Verification ---

    def test_public_verification_by_certificate_code_returns_sanitized_data(self):
        """Public endpoint verifies active certificate without exposing trainee email or internal IDs."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        cert, _, _ = check_and_issue_certificate(enrollment)

        self.client.force_authenticate(user=None)  # Anonymous
        url = reverse('public-certificate-verify', kwargs={'identifier': cert.certificate_code})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'VALID')
        self.assertEqual(response.data['trainee_name'], self.trainee_1.username)
        self.assertEqual(response.data['course_title'], self.course_1.title)
        self.assertEqual(response.data['trainer_name'], self.trainer_1.username)
        # Verify sanitization
        self.assertNotIn('email', response.data)
        self.assertNotIn('trainee_email', response.data)
        self.assertNotIn('password', response.data)
        self.assertNotIn('enrollment_id', response.data)

    def test_public_verification_by_sha256_hash_success(self):
        """Public verification works seamlessly with SHA-256 hash."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        cert, _, _ = check_and_issue_certificate(enrollment)

        self.client.force_authenticate(user=None)
        url = reverse('public-certificate-verify', kwargs={'identifier': cert.verification_hash})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['certificate_code'], cert.certificate_code)

    def test_public_verification_with_invalid_code_returns_404(self):
        """Non-existent certificate code returns 404 with error detail."""
        self.client.force_authenticate(user=None)
        url = reverse('public-certificate-verify', kwargs={'identifier': 'CC-9999-FAKE-CODE'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('detail', response.data)

    def test_public_verification_of_revoked_certificate_shows_revoked_status(self):
        """Revoked certificate is flagged as revoked with revocation timestamp and reason."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        cert, _, _ = check_and_issue_certificate(enrollment)
        cert.revoke(revoked_by_user=self.admin, reason='Honor code violation')

        self.client.force_authenticate(user=None)
        url = reverse('public-certificate-verify', kwargs={'identifier': cert.certificate_code})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'REVOKED')
        self.assertEqual(response.data['revocation_reason'], 'Honor code violation')

    # --- 6. Admin Revocation & Reinstatement ---

    def test_admin_can_revoke_certificate_with_reason(self):
        """Admin can revoke an active certificate."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        cert, _, _ = check_and_issue_certificate(enrollment)

        self.client.force_authenticate(user=self.admin)
        url = reverse('admin-revoke-certificate', kwargs={'pk': cert.id})
        response = self.client.post(url, {'reason': 'Plagiarism detected on submission'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cert.refresh_from_db()
        self.assertEqual(cert.status, CertificateStatus.REVOKED)
        self.assertEqual(cert.revoked_by, self.admin)
        self.assertEqual(cert.revocation_reason, 'Plagiarism detected on submission')

    def test_admin_revoke_fails_without_reason(self):
        """Revocation requires a non-empty reason string."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        cert, _, _ = check_and_issue_certificate(enrollment)

        self.client.force_authenticate(user=self.admin)
        url = reverse('admin-revoke-certificate', kwargs={'pk': cert.id})
        response = self.client.post(url, {'reason': ''})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_reinstate_revoked_certificate(self):
        """Admin can reinstate a previously revoked certificate."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        cert, _, _ = check_and_issue_certificate(enrollment)
        cert.revoke(revoked_by_user=self.admin, reason='Investigating dispute')

        self.client.force_authenticate(user=self.admin)
        url = reverse('admin-reinstate-certificate', kwargs={'pk': cert.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cert.refresh_from_db()
        self.assertEqual(cert.status, CertificateStatus.ACTIVE)
        self.assertIsNone(cert.revoked_at)
        self.assertIsNone(cert.revoked_by)
        self.assertEqual(cert.revocation_reason, '')

    def test_trainer_cannot_revoke_certificate(self):
        """Trainer gets 403 Forbidden when attempting to revoke."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        cert, _, _ = check_and_issue_certificate(enrollment)

        self.client.force_authenticate(user=self.trainer_1)
        url = reverse('admin-revoke-certificate', kwargs={'pk': cert.id})
        response = self.client.post(url, {'reason': 'Attempted trainer revocation'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_trainee_cannot_revoke_certificate(self):
        """Trainee gets 403 Forbidden when attempting to revoke."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        cert, _, _ = check_and_issue_certificate(enrollment)

        self.client.force_authenticate(user=self.trainee_1)
        url = reverse('admin-revoke-certificate', kwargs={'pk': cert.id})
        response = self.client.post(url, {'reason': 'Attempted trainee revocation'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- 7. Trainer Roster & Ownership ---

    def test_trainer_can_view_certificate_roster_for_own_course(self):
        """Trainer can view issued certificates for their course."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        check_and_issue_certificate(enrollment)

        self.client.force_authenticate(user=self.trainer_1)
        url = reverse('trainer-course-certificates', kwargs={'course_id': self.course_1.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['trainee_username'], self.trainee_1.username)

    def test_trainer_cannot_view_certificate_roster_for_another_trainers_course(self):
        """Trainer receives 403 Forbidden when requesting another trainer's course certificate roster."""
        self.client.force_authenticate(user=self.trainer_1)
        url = reverse('trainer-course-certificates', kwargs={'course_id': self.course_2.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- 8. Admin Platform-wide Certificate Oversight (Step 11) ---

    def test_admin_can_list_all_certificates(self):
        """Admin can list all platform certificates across all courses/trainees."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        check_and_issue_certificate(enrollment)

        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/certificates/admin/all/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_admin_can_search_certificates(self):
        """Admin can search certificates by code or trainee username."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        cert, _, _ = check_and_issue_certificate(enrollment)

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/certificates/admin/all/?search={cert.certificate_code}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['certificate_code'], cert.certificate_code)

    def test_non_admin_cannot_list_all_certificates(self):
        """Trainee or Trainer receives 403 on admin all certificates endpoint."""
        self.client.force_authenticate(user=self.trainee_1)
        response = self.client.get('/api/certificates/admin/all/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- 9. Step 15 Trainee Credential Portfolio, Transcripts & Achievements ---

    def test_step15_my_certificates_empty_state(self):
        """Trainee with no certificates gets an empty list."""
        self.client.force_authenticate(user=self.trainee_2)
        response = self.client.get(reverse('trainee-my-certificates'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_step15_my_certificates_payload_includes_honors_and_duration(self):
        """Trainee certificate list item includes duration_hours, honors_tier, and trainer_name."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        cert, _, _ = check_and_issue_certificate(enrollment)

        self.client.force_authenticate(user=self.trainee_1)
        response = self.client.get(reverse('trainee-my-certificates'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        item = response.data[0]
        self.assertEqual(item['certificate_code'], cert.certificate_code)
        self.assertIn('duration_hours', item)
        self.assertIn('honors_tier', item)
        self.assertEqual(item['honors_tier'], 'DISTINCTION')  # default final_grade is 100%

    def test_step15_honors_tier_classification(self):
        """Verify honors tier property: DISTINCTION (>=90%), MERIT (>=80%), PASS (<80%)."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        cert, _, _ = check_and_issue_certificate(enrollment)

        cert.final_grade_percentage = 95.0
        cert.save()
        self.assertEqual(cert.honors_tier, 'DISTINCTION')

        cert.final_grade_percentage = 85.0
        cert.save()
        self.assertEqual(cert.honors_tier, 'MERIT')

        cert.final_grade_percentage = 75.0
        cert.save()
        self.assertEqual(cert.honors_tier, 'PASS')

    def test_step15_trainee_summary_metrics(self):
        """Verify /api/certificates/my-summary/ aggregate achievement metrics."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        cert, _, _ = check_and_issue_certificate(enrollment)

        self.client.force_authenticate(user=self.trainee_1)
        response = self.client.get(reverse('trainee-certificate-summary'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data['total_certificates'], 1)
        self.assertEqual(data['cumulative_grade_average'], 100.0)
        self.assertEqual(data['distinctions_count'], 1)
        self.assertIn(self.course_1.category, data['categories_mastered'])

    def test_step15_transcript_structure_and_records(self):
        """Verify /api/certificates/transcript/ returns official academic transcript."""
        enrollment = self._complete_subjects_for_course_1(self.trainee_1)
        cert, _, _ = check_and_issue_certificate(enrollment)

        self.client.force_authenticate(user=self.trainee_1)
        response = self.client.get(reverse('trainee-transcript'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data['student_id'], self.trainee_1.id)
        self.assertEqual(data['total_courses_completed'], 1)
        self.assertEqual(len(data['records']), 1)

        rec = data['records'][0]
        self.assertEqual(rec['course_id'], self.course_1.id)
        self.assertEqual(rec['certificate_code'], cert.certificate_code)
        self.assertTrue(rec['is_valid'])

    def test_step15_unauthenticated_cannot_access_portfolio_or_transcript(self):
        """Anonymous user receives 401 on my-certificates, my-summary, and transcript."""
        self.assertEqual(self.client.get(reverse('trainee-my-certificates')).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get(reverse('trainee-certificate-summary')).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get(reverse('trainee-transcript')).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_step15_trainer_cannot_access_trainee_summary(self):
        """Trainers receive 403 when trying to access trainee summary endpoint."""
        self.client.force_authenticate(user=self.trainer_1)
        response = self.client.get(reverse('trainee-certificate-summary'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


