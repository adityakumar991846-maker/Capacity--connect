"""
Automated unit and integration test suite for the assignments module (Step 13).
"""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Role, UserProfile
from courses.models import Course, CourseLevel, CourseStatus, Subject
from enrollments.models import Enrollment, EnrollmentStatus, SubjectProgress
from certificates.views import check_and_issue_certificate
from .models import (
    Assignment,
    AssignmentSubmission,
    SubmissionReview,
    SubmissionType,
    SubmissionStatus,
)


class AssignmentsTestCase(TestCase):
    """
    Comprehensive tests for practical assignments, project deliverables,
    trainer grading workbench, and certificate eligibility enforcement.
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Create Admin
        self.admin_user = User.objects.create_user(
            username='admin_step13',
            email='admin13@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.admin_user, role=Role.ADMIN)

        # 2. Create Trainer
        self.trainer_user = User.objects.create_user(
            username='trainer_step13',
            email='trainer13@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainer_user, role=Role.TRAINER)

        # 3. Create Enrolled Trainee A
        self.trainee_a = User.objects.create_user(
            username='trainee_a_step13',
            email='trainea13@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainee_a, role=Role.TRAINEE)

        # 4. Create Non-Enrolled Trainee B
        self.trainee_b = User.objects.create_user(
            username='trainee_b_step13',
            email='traineb13@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainee_b, role=Role.TRAINEE)

        # 5. Create Course & Subject
        self.course = Course.objects.create(
            title='Step 13 Full Stack Architecture',
            category='Engineering',
            level=CourseLevel.ADVANCED,
            status=CourseStatus.PUBLISHED,
            duration_hours=40,
            trainer=self.trainer_user,
        )
        self.subject1 = Subject.objects.create(
            course=self.course,
            title='Module 1: Microservices Architecture',
            description='System design and service meshes.',
            order=1,
        )

        # Enroll Trainee A in course
        self.enrollment_a = Enrollment.objects.create(
            trainee=self.trainee_a,
            course=self.course,
            status=EnrollmentStatus.ENROLLED,
        )
        self.sp1 = SubjectProgress.objects.create(
            enrollment=self.enrollment_a,
            subject=self.subject1,
            completed=True,
        )

        # Create Sample Assignment
        self.assignment = Assignment.objects.create(
            course=self.course,
            subject=self.subject1,
            title='Capstone: Microservice API Design',
            description='Build and deploy a scalable microservice API with Docker and OpenAPI.',
            submission_type=SubmissionType.LINK,
            max_score=100,
            passing_score=70,
            is_mandatory=True,
            is_published=True,
        )

    # -------------------------------------------------------------------------
    # 1. Access & Visibility
    # -------------------------------------------------------------------------

    def test_enrolled_trainee_can_list_assignments(self):
        self.client.force_authenticate(user=self.trainee_a)
        res = self.client.get(f'/api/assignments/courses/{self.course.id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['title'], self.assignment.title)

    def test_non_enrolled_trainee_cannot_view_assignments(self):
        self.client.force_authenticate(user=self.trainee_b)
        res = self.client.get(f'/api/assignments/courses/{self.course.id}/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # 2. Assignment Authoring (Trainer / Admin)
    # -------------------------------------------------------------------------

    def test_trainer_can_create_assignment(self):
        self.client.force_authenticate(user=self.trainer_user)
        payload = {
            'title': 'Project: Docker Compose Orchestration',
            'description': 'Configure multi-container setup with PostgreSQL and Redis.',
            'subject_id': self.subject1.id,
            'submission_type': 'LINK',
            'max_score': 100,
            'passing_score': 60,
            'is_mandatory': False,
            'is_published': True,
        }
        res = self.client.post(f'/api/assignments/courses/{self.course.id}/', payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['title'], payload['title'])
        self.assertEqual(res.data['max_score'], 100)

    def test_trainee_cannot_create_assignment(self):
        self.client.force_authenticate(user=self.trainee_a)
        payload = {
            'title': 'Illegal Trainee Assignment',
            'description': 'Should be rejected.',
        }
        res = self.client.post(f'/api/assignments/courses/{self.course.id}/', payload)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # 3. Trainee Submission Handling
    # -------------------------------------------------------------------------

    def test_trainee_can_submit_link_assignment(self):
        self.client.force_authenticate(user=self.trainee_a)
        payload = {
            'submission_link': 'https://github.com/trainee/microservice-capstone',
            'submission_text': 'Here is the GitHub repo link and deployment README.',
            'status': 'SUBMITTED',
        }
        res = self.client.post(f'/api/assignments/{self.assignment.id}/submit/', payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['status'], 'SUBMITTED')
        self.assertEqual(res.data['submission_link'], payload['submission_link'])

    def test_link_assignment_validates_url_required(self):
        self.client.force_authenticate(user=self.trainee_a)
        payload = {
            'submission_link': '',  # Missing link for LINK type
            'submission_text': 'I forgot the link',
            'status': 'SUBMITTED',
        }
        res = self.client.post(f'/api/assignments/{self.assignment.id}/submit/', payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('submission_link', res.data)

    def test_trainee_cannot_submit_to_unregistered_course(self):
        self.client.force_authenticate(user=self.trainee_b)
        payload = {
            'submission_link': 'https://github.com/trainee-b/demo',
        }
        res = self.client.post(f'/api/assignments/{self.assignment.id}/submit/', payload)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_duplicate_submission_updates_existing(self):
        self.client.force_authenticate(user=self.trainee_a)
        # First submission
        self.client.post(f'/api/assignments/{self.assignment.id}/submit/', {
            'submission_link': 'https://github.com/trainee/v1',
            'status': 'SUBMITTED',
        })
        # Second submission updates deliverable
        res = self.client.post(f'/api/assignments/{self.assignment.id}/submit/', {
            'submission_link': 'https://github.com/trainee/v2',
            'status': 'SUBMITTED',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['submission_link'], 'https://github.com/trainee/v2')
        self.assertEqual(AssignmentSubmission.objects.filter(assignment=self.assignment).count(), 1)

    # -------------------------------------------------------------------------
    # 4. Trainer Grading & Rubric Evaluation
    # -------------------------------------------------------------------------

    def test_trainer_can_grade_submission_passed(self):
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            trainee=self.trainee_a,
            enrollment=self.enrollment_a,
            submission_link='https://github.com/trainee/passed-project',
            status=SubmissionStatus.SUBMITTED,
        )

        self.client.force_authenticate(user=self.trainer_user)
        payload = {
            'score': 85,  # passing_score is 70
            'feedback': 'Excellent system architecture, clean modular design, and robust tests.',
            'request_resubmission': False,
        }
        res = self.client.post(f'/api/assignments/submissions/{submission.id}/grade/', payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'GRADED')
        self.assertTrue(res.data['review']['passed'])
        self.assertEqual(res.data['review']['score'], 85)

    def test_trainer_can_request_resubmission(self):
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            trainee=self.trainee_a,
            enrollment=self.enrollment_a,
            submission_link='https://github.com/trainee/flawed-project',
            status=SubmissionStatus.SUBMITTED,
        )

        self.client.force_authenticate(user=self.trainer_user)
        payload = {
            'score': 45,  # Below passing_score 70
            'feedback': 'Docker container fails to start due to missing environment variables. Please fix and resubmit.',
            'request_resubmission': True,
        }
        res = self.client.post(f'/api/assignments/submissions/{submission.id}/grade/', payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'RESUBMISSION_REQUESTED')
        self.assertFalse(res.data['review']['passed'])

    def test_trainee_can_resubmit_after_changes_requested(self):
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            trainee=self.trainee_a,
            enrollment=self.enrollment_a,
            submission_link='https://github.com/trainee/buggy',
            status=SubmissionStatus.RESUBMISSION_REQUESTED,
        )

        self.client.force_authenticate(user=self.trainee_a)
        res = self.client.post(f'/api/assignments/{self.assignment.id}/submit/', {
            'submission_link': 'https://github.com/trainee/fixed',
            'status': 'SUBMITTED',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        submission.refresh_from_db()
        self.assertEqual(submission.status, 'SUBMITTED')
        self.assertEqual(submission.submission_link, 'https://github.com/trainee/fixed')

    def test_non_trainer_cannot_grade_submission(self):
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            trainee=self.trainee_a,
            enrollment=self.enrollment_a,
            submission_link='https://github.com/trainee/project',
            status=SubmissionStatus.SUBMITTED,
        )

        # Another trainee tries to grade -> 403
        self.client.force_authenticate(user=self.trainee_b)
        res = self.client.post(f'/api/assignments/submissions/{submission.id}/grade/', {
            'score': 100,
            'feedback': 'Fake grade',
        })
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_score_cannot_exceed_max_score(self):
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            trainee=self.trainee_a,
            enrollment=self.enrollment_a,
            submission_link='https://github.com/trainee/project',
            status=SubmissionStatus.SUBMITTED,
        )

        self.client.force_authenticate(user=self.trainer_user)
        res = self.client.post(f'/api/assignments/submissions/{submission.id}/grade/', {
            'score': 150,  # Max is 100
            'feedback': 'Too many marks.',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('score', res.data)

    # -------------------------------------------------------------------------
    # 5. Trainer Inquiries Queue & Certificate Eligibility
    # -------------------------------------------------------------------------

    def test_trainer_pending_reviews_queue(self):
        # Submission 1: SUBMITTED (pending review)
        AssignmentSubmission.objects.create(
            assignment=self.assignment,
            trainee=self.trainee_a,
            enrollment=self.enrollment_a,
            submission_link='https://github.com/trainee/pending',
            status=SubmissionStatus.SUBMITTED,
        )

        self.client.force_authenticate(user=self.trainer_user)
        res = self.client.get('/api/assignments/trainer/pending-reviews/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['trainee_username'], self.trainee_a.username)

    def test_certificate_eligibility_enforces_mandatory_assignment(self):
        # 1. 100% module progress fulfilled, but mandatory assignment NOT passed yet
        cert, created, err = check_and_issue_certificate(self.enrollment_a)
        self.assertIsNone(cert)
        self.assertFalse(created)
        self.assertIn('Mandatory assignment', err)

        # 2. Now submit and pass the assignment
        sub = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            trainee=self.trainee_a,
            enrollment=self.enrollment_a,
            submission_link='https://github.com/trainee/certified-capstone',
            status=SubmissionStatus.GRADED,
        )
        SubmissionReview.objects.create(
            submission=sub,
            reviewer=self.trainer_user,
            score=90,
            passed=True,
            feedback='Passed with distinction!',
        )

        # 3. Now check_and_issue_certificate should succeed
        cert, created, err = check_and_issue_certificate(self.enrollment_a)
        self.assertIsNotNone(cert)
        self.assertTrue(created)
        self.assertIsNone(err)
        self.assertEqual(cert.final_grade_percentage, 90.0)
