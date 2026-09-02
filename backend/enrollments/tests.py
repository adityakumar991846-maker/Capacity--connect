"""
Comprehensive test suite for the enrollments app.

25 test cases covering:
- Enrollment creation & validation
- Learning progress & subject completion rules
- Automatic status transitions (ENROLLED <-> COMPLETED)
- Role-based visibility and authorization
- Dropping enrollments
- Cascade deletion & dynamic subject synchronization
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Role, UserProfile
from courses.models import Course, CourseLevel, CourseStatus, Subject
from .models import Enrollment, EnrollmentStatus, SubjectProgress


class EnrollmentTestBase(TestCase):
    """Base test setup with Trainees, Trainers, Admin, and Courses."""

    def setUp(self):
        self.client = APIClient()

        # Trainee 1
        self.trainee1 = User.objects.create_user(
            username='trainee1',
            email='trainee1@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainee1, role=Role.TRAINEE)

        # Trainee 2
        self.trainee2 = User.objects.create_user(
            username='trainee2',
            email='trainee2@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainee2, role=Role.TRAINEE)

        # Trainer 1
        self.trainer1 = User.objects.create_user(
            username='trainer1',
            email='trainer1@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainer1, role=Role.TRAINER)

        # Trainer 2
        self.trainer2 = User.objects.create_user(
            username='trainer2',
            email='trainer2@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainer2, role=Role.TRAINER)

        # Admin
        self.admin_user = User.objects.create_superuser(
            username='adminuser',
            email='admin@example.com',
            password='Password123!',
        )

        # Published Course with 2 Subjects
        self.pub_course = Course.objects.create(
            title='Published Python Course',
            description='Active course',
            category='Tech',
            level=CourseLevel.BEGINNER,
            duration_hours=20,
            status=CourseStatus.PUBLISHED,
            trainer=self.trainer1,
        )
        self.subj1 = Subject.objects.create(course=self.pub_course, title='Module 1', order=1)
        self.subj2 = Subject.objects.create(course=self.pub_course, title='Module 2', order=2)

        # Draft Course
        self.draft_course = Course.objects.create(
            title='Draft Course',
            description='Draft',
            category='Tech',
            level=CourseLevel.BEGINNER,
            duration_hours=10,
            status=CourseStatus.DRAFT,
            trainer=self.trainer1,
        )

        # Archived Course
        self.archived_course = Course.objects.create(
            title='Archived Course',
            description='Archived',
            category='Tech',
            level=CourseLevel.INTERMEDIATE,
            duration_hours=15,
            status=CourseStatus.ARCHIVED,
            trainer=self.trainer2,
        )


class EnrollmentCreationTests(EnrollmentTestBase):
    """Tests for POST /api/enrollments/"""

    def test_01_trainee_enrolls_in_published_course_succeeds(self):
        """Trainee successfully enrolls in a published course; progress initialized."""
        self.client.force_authenticate(user=self.trainee1)
        url = reverse('enrollment-list-create')
        data = {'course_id': self.pub_course.id}
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], EnrollmentStatus.ENROLLED)
        self.assertEqual(response.data['progress_percentage'], 0.0)
        self.assertEqual(len(response.data['subject_progresses']), 2)

        # Verify DB
        enrollment = Enrollment.objects.get(trainee=self.trainee1, course=self.pub_course)
        self.assertEqual(enrollment.subject_progresses.count(), 2)

    def test_02_trainee_cannot_enroll_in_draft_course(self):
        """Enrolling in a DRAFT course returns 400."""
        self.client.force_authenticate(user=self.trainee1)
        url = reverse('enrollment-list-create')
        data = {'course_id': self.draft_course.id}
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Enrollment.objects.filter(trainee=self.trainee1, course=self.draft_course).exists())

    def test_03_trainee_cannot_enroll_in_archived_course(self):
        """Enrolling in an ARCHIVED course returns 400."""
        self.client.force_authenticate(user=self.trainee1)
        url = reverse('enrollment-list-create')
        data = {'course_id': self.archived_course.id}
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_04_duplicate_enrollment_rejected(self):
        """Enrolling in the same course twice returns 400."""
        Enrollment.objects.create(trainee=self.trainee1, course=self.pub_course)
        self.client.force_authenticate(user=self.trainee1)
        url = reverse('enrollment-list-create')
        data = {'course_id': self.pub_course.id}
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_05_trainer_cannot_enroll_in_course(self):
        """Users with TRAINER role receive 403 on enrollment endpoint."""
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('enrollment-list-create')
        data = {'course_id': self.pub_course.id}
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_06_unauthenticated_user_cannot_enroll(self):
        """Unauthenticated requests receive 403 Forbidden."""
        url = reverse('enrollment-list-create')
        data = {'course_id': self.pub_course.id}
        response = self.client.post(url, data, format='json')

        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])



class LearningProgressTests(EnrollmentTestBase):
    """Tests for Subject completion tracking and status recalculation."""

    def setUp(self):
        super().setUp()
        self.enrollment = Enrollment.objects.create(
            trainee=self.trainee1,
            course=self.pub_course,
            status=EnrollmentStatus.ENROLLED,
        )
        self.sp1 = SubjectProgress.objects.create(
            enrollment=self.enrollment,
            subject=self.subj1,
            completed=False,
        )
        self.sp2 = SubjectProgress.objects.create(
            enrollment=self.enrollment,
            subject=self.subj2,
            completed=False,
        )

    def test_07_trainee_marks_subject_completed(self):
        """Trainee marks a subject completed; timestamp recorded."""
        self.client.force_authenticate(user=self.trainee1)
        url = reverse(
            'enrollment-subject-complete',
            kwargs={'pk': self.enrollment.pk, 'subject_id': self.subj1.pk},
        )
        response = self.client.post(url, {'completed': True}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['progress_percentage'], 50.0)
        self.assertEqual(response.data['status'], EnrollmentStatus.ENROLLED)

        self.sp1.refresh_from_db()
        self.assertTrue(self.sp1.completed)
        self.assertIsNotNone(self.sp1.completed_at)

    def test_08_trainee_marks_subject_incomplete(self):
        """Trainee marks a previously completed subject as incomplete."""
        self.sp1.mark_completed()
        self.client.force_authenticate(user=self.trainee1)
        url = reverse(
            'enrollment-subject-complete',
            kwargs={'pk': self.enrollment.pk, 'subject_id': self.subj1.pk},
        )
        response = self.client.post(url, {'completed': False}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['progress_percentage'], 0.0)

        self.sp1.refresh_from_db()
        self.assertFalse(self.sp1.completed)
        self.assertIsNone(self.sp1.completed_at)

    def test_09_progress_percentage_calculated_accurately(self):
        """Progress percentage accurately reflects completed/total*100."""
        self.assertEqual(self.enrollment.progress_percentage, 0.0)
        self.sp1.mark_completed()
        self.assertEqual(self.enrollment.progress_percentage, 50.0)
        self.sp2.mark_completed()
        self.assertEqual(self.enrollment.progress_percentage, 100.0)

    def test_10_all_subjects_completed_auto_sets_status_completed(self):
        """Completing all subjects auto-transitions enrollment status to COMPLETED."""
        self.client.force_authenticate(user=self.trainee1)
        url1 = reverse(
            'enrollment-subject-complete',
            kwargs={'pk': self.enrollment.pk, 'subject_id': self.subj1.pk},
        )
        url2 = reverse(
            'enrollment-subject-complete',
            kwargs={'pk': self.enrollment.pk, 'subject_id': self.subj2.pk},
        )

        self.client.post(url1, {'completed': True}, format='json')
        response = self.client.post(url2, {'completed': True}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], EnrollmentStatus.COMPLETED)
        self.assertEqual(response.data['progress_percentage'], 100.0)
        self.assertIsNotNone(response.data['completed_at'])

        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, EnrollmentStatus.COMPLETED)
        self.assertIsNotNone(self.enrollment.completed_at)

    def test_11_marking_subject_incomplete_reverts_status_to_enrolled(self):
        """Uncompleting a subject on a COMPLETED course reverts status to ENROLLED."""
        self.sp1.mark_completed()
        self.sp2.mark_completed()
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, EnrollmentStatus.COMPLETED)

        self.client.force_authenticate(user=self.trainee1)
        url1 = reverse(
            'enrollment-subject-complete',
            kwargs={'pk': self.enrollment.pk, 'subject_id': self.subj1.pk},
        )
        response = self.client.post(url1, {'completed': False}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], EnrollmentStatus.ENROLLED)
        self.assertIsNone(response.data['completed_at'])

        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, EnrollmentStatus.ENROLLED)
        self.assertIsNone(self.enrollment.completed_at)

    def test_12_cannot_complete_subject_of_different_course(self):
        """Attempting to complete a subject not in the enrolled course returns 400."""
        other_course = Course.objects.create(
            title='Other Course',
            description='Other',
            category='Tech',
            level=CourseLevel.BEGINNER,
            duration_hours=5,
            status=CourseStatus.PUBLISHED,
            trainer=self.trainer1,
        )
        foreign_subj = Subject.objects.create(course=other_course, title='Other Mod', order=1)

        self.client.force_authenticate(user=self.trainee1)
        url = reverse(
            'enrollment-subject-complete',
            kwargs={'pk': self.enrollment.pk, 'subject_id': foreign_subj.pk},
        )
        response = self.client.post(url, {'completed': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_13_cannot_update_progress_on_dropped_enrollment(self):
        """Cannot mark subjects complete if enrollment is DROPPED."""
        self.enrollment.status = EnrollmentStatus.DROPPED
        self.enrollment.save()

        self.client.force_authenticate(user=self.trainee1)
        url = reverse(
            'enrollment-subject-complete',
            kwargs={'pk': self.enrollment.pk, 'subject_id': self.subj1.pk},
        )
        response = self.client.post(url, {'completed': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class EnrollmentVisibilityTests(EnrollmentTestBase):
    """Tests for role-based enrollment lists and detail access."""

    def setUp(self):
        super().setUp()
        # Trainee 1 enrollment in pub_course (trainer1)
        self.e1 = Enrollment.objects.create(trainee=self.trainee1, course=self.pub_course)
        # Trainee 2 enrollment in pub_course (trainer1)
        self.e2 = Enrollment.objects.create(trainee=self.trainee2, course=self.pub_course)

        # Course by trainer2
        self.course_trainer2 = Course.objects.create(
            title='Trainer 2 Course',
            description='Description',
            category='Design',
            level=CourseLevel.BEGINNER,
            duration_hours=10,
            status=CourseStatus.PUBLISHED,
            trainer=self.trainer2,
        )
        # Trainee 1 enrollment in course_trainer2
        self.e3 = Enrollment.objects.create(trainee=self.trainee1, course=self.course_trainer2)

    def test_14_trainee_sees_only_own_enrollments(self):
        """Trainee list returns only their own enrollments."""
        self.client.force_authenticate(user=self.trainee1)
        url = reverse('enrollment-list-create')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [e['id'] for e in response.data]
        self.assertIn(self.e1.id, ids)
        self.assertIn(self.e3.id, ids)
        self.assertNotIn(self.e2.id, ids)

    def test_15_trainee_cannot_view_other_trainee_enrollment_detail(self):
        """Trainee accessing another trainee's enrollment returns 404."""
        self.client.force_authenticate(user=self.trainee1)
        url = reverse('enrollment-detail', kwargs={'pk': self.e2.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_16_trainer_sees_enrollments_for_own_courses(self):
        """Trainer 1 list returns enrollments for trainer1's courses only."""
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('enrollment-list-create')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [e['id'] for e in response.data]
        self.assertIn(self.e1.id, ids)
        self.assertIn(self.e2.id, ids)
        self.assertNotIn(self.e3.id, ids)  # e3 is on trainer2's course

    def test_17_trainer_cannot_view_enrollment_for_other_trainer_course(self):
        """Trainer 1 cannot view enrollment detail for a course owned by Trainer 2."""
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('enrollment-detail', kwargs={'pk': self.e3.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_18_admin_sees_all_enrollments(self):
        """Admin list returns all enrollments across all trainees and courses."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('enrollment-list-create')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [e['id'] for e in response.data]
        self.assertIn(self.e1.id, ids)
        self.assertIn(self.e2.id, ids)
        self.assertIn(self.e3.id, ids)

    def test_19_unauthenticated_cannot_access_enrollments_list(self):
        """Unauthenticated requests receive 403 Forbidden."""
        url = reverse('enrollment-list-create')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])



class EnrollmentDropTests(EnrollmentTestBase):
    """Tests for POST /api/enrollments/<pk>/drop/"""

    def setUp(self):
        super().setUp()
        self.enrollment = Enrollment.objects.create(
            trainee=self.trainee1,
            course=self.pub_course,
            status=EnrollmentStatus.ENROLLED,
        )

    def test_20_trainee_drops_own_enrollment_succeeds(self):
        """Trainee drops course; record preserved with status=DROPPED."""
        self.client.force_authenticate(user=self.trainee1)
        url = reverse('enrollment-drop', kwargs={'pk': self.enrollment.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], EnrollmentStatus.DROPPED)

        # Verify DB still contains the record
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, EnrollmentStatus.DROPPED)

    def test_21_trainee_cannot_drop_another_trainee_enrollment(self):
        """Trainee 2 cannot drop Trainee 1's enrollment (403)."""
        self.client.force_authenticate(user=self.trainee2)
        url = reverse('enrollment-drop', kwargs={'pk': self.enrollment.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_22_admin_can_drop_any_enrollment(self):
        """Admin can drop any trainee's enrollment."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('enrollment-drop', kwargs={'pk': self.enrollment.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, EnrollmentStatus.DROPPED)


class CascadeAndSyncTests(EnrollmentTestBase):
    """Tests for cascade deletion and dynamic subject synchronization."""

    def test_23_deleting_course_cascades_enrollments(self):
        """Deleting a course also cascades to all associated enrollments."""
        enrollment = Enrollment.objects.create(trainee=self.trainee1, course=self.pub_course)
        SubjectProgress.objects.create(enrollment=enrollment, subject=self.subj1)

        self.pub_course.delete()
        self.assertFalse(Enrollment.objects.filter(pk=enrollment.pk).exists())
        self.assertFalse(SubjectProgress.objects.filter(enrollment_id=enrollment.pk).exists())

    def test_24_deleting_trainee_cascades_enrollments(self):
        """Deleting a trainee user cascades and deletes their enrollments."""
        enrollment = Enrollment.objects.create(trainee=self.trainee1, course=self.pub_course)
        self.trainee1.delete()
        self.assertFalse(Enrollment.objects.filter(pk=enrollment.pk).exists())

    def test_25_new_subject_added_to_course_syncs_on_detail_view(self):
        """Adding a new subject to a course dynamically syncs progress on detail view."""
        enrollment = Enrollment.objects.create(trainee=self.trainee1, course=self.pub_course)
        SubjectProgress.objects.create(enrollment=enrollment, subject=self.subj1, completed=True)
        SubjectProgress.objects.create(enrollment=enrollment, subject=self.subj2, completed=True)

        # Initially 2/2 = 100%
        self.assertEqual(enrollment.progress_percentage, 100.0)

        # Trainer adds Module 3
        subj3 = Subject.objects.create(course=self.pub_course, title='Module 3', order=3)

        # Trainee fetches detail
        self.client.force_authenticate(user=self.trainee1)
        url = reverse('enrollment-detail', kwargs={'pk': enrollment.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['subject_progresses']), 3)
        # 2 out of 3 completed = 66.67%
        self.assertEqual(response.data['progress_percentage'], 66.67)
