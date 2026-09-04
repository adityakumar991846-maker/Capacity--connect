"""
Comprehensive test suite for the courses app.

25 test cases covering:
- Course creation
- Course update & deletion (trainer ownership & admin access)
- Role-based course visibility
- Subject creation, ordering, and cascade deletion
- Edge cases (trainer publishing restriction, invalid trainer assignment, duplicate order)
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Role, UserProfile
from .models import Course, CourseLevel, CourseStatus, Subject


class CourseTestBase(TestCase):
    """Base setup for course tests providing users of all 3 roles."""

    def setUp(self):
        self.client = APIClient()

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
        # Note: core signal auto-creates UserProfile for superuser

        # Trainee
        self.trainee = User.objects.create_user(
            username='trainee1',
            email='trainee1@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainee, role=Role.TRAINEE)


class CourseCreationTests(CourseTestBase):
    """Tests for POST /api/courses/"""

    def test_01_trainer_creates_course_succeeds(self):
        """Trainer creates course with valid data; trainer auto-assigned."""
        self.client.force_authenticate(user=self.trainer1)
        data = {
            'title': 'Python Fundamentals',
            'description': 'Learn Python from scratch.',
            'category': 'Programming',
            'level': CourseLevel.BEGINNER,
            'duration_hours': 20,
            'status': CourseStatus.DRAFT,
            'requirements': 'None',
            'learning_objectives': 'Variables, loops, functions',
        }
        url = reverse('course-list-create')
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Python Fundamentals')
        self.assertEqual(response.data['status'], CourseStatus.DRAFT)
        self.assertEqual(response.data['trainer']['id'], self.trainer1.id)

        # Verify DB
        course = Course.objects.get(title='Python Fundamentals')
        self.assertEqual(course.trainer, self.trainer1)

    def test_02_admin_creates_course_succeeds(self):
        """Admin creates course with valid data."""
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'title': 'Admin Created Course',
            'description': 'Course created by admin.',
            'category': 'Management',
            'level': CourseLevel.INTERMEDIATE,
            'duration_hours': 10,
            'status': CourseStatus.PUBLISHED,
        }
        url = reverse('course-list-create')
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], CourseStatus.PUBLISHED)

    def test_03_admin_creates_course_with_assigned_trainer(self):
        """Admin creates course and explicitly assigns a specific trainer."""
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'title': 'Assigned Course',
            'description': 'Admin assigned to trainer2.',
            'category': 'DevOps',
            'level': CourseLevel.ADVANCED,
            'duration_hours': 40,
            'trainer': self.trainer2.id,
        }
        url = reverse('course-list-create')
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['trainer']['id'], self.trainer2.id)

        course = Course.objects.get(title='Assigned Course')
        self.assertEqual(course.trainer, self.trainer2)

    def test_04_trainee_cannot_create_course(self):
        """Trainee receives 403 Forbidden when attempting to create a course."""
        self.client.force_authenticate(user=self.trainee)
        data = {
            'title': 'Trainee Course',
            'description': 'Should fail.',
            'category': 'General',
            'level': CourseLevel.BEGINNER,
            'duration_hours': 5,
        }
        url = reverse('course-list-create')
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_05_missing_required_fields_fails(self):
        """Missing title, description, category, or duration returns 400."""
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('course-list-create')

        # Empty body
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', response.data)
        self.assertIn('description', response.data)
        self.assertIn('category', response.data)


class CourseUpdateDeleteTests(CourseTestBase):
    """Tests for PUT, PATCH, DELETE /api/courses/<id>/"""

    def setUp(self):
        super().setUp()
        self.course1 = Course.objects.create(
            title='Trainer 1 Course',
            description='Original Description',
            category='Tech',
            level=CourseLevel.BEGINNER,
            duration_hours=15,
            status=CourseStatus.DRAFT,
            trainer=self.trainer1,
        )

    def test_06_trainer_updates_own_course_succeeds(self):
        """Trainer successfully updates their own course."""
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('course-detail', kwargs={'pk': self.course1.pk})
        data = {
            'title': 'Updated Course Title',
            'description': 'Updated Description',
            'category': 'Tech',
            'level': CourseLevel.INTERMEDIATE,
            'duration_hours': 25,
            'status': CourseStatus.ARCHIVED,
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated Course Title')
        self.assertEqual(response.data['status'], CourseStatus.ARCHIVED)

    def test_07_trainer_cannot_update_other_trainer_course(self):
        """Trainer 2 cannot update Trainer 1's course (403)."""
        self.client.force_authenticate(user=self.trainer2)
        url = reverse('course-detail', kwargs={'pk': self.course1.pk})
        data = {'title': 'Hacked Title'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_08_admin_can_update_any_course(self):
        """Admin can update any trainer's course."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('course-detail', kwargs={'pk': self.course1.pk})
        data = {'title': 'Admin Updated Title', 'status': CourseStatus.PUBLISHED}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Admin Updated Title')
        self.assertEqual(response.data['status'], CourseStatus.PUBLISHED)

    def test_09_trainer_deletes_own_course_succeeds(self):
        """Trainer can delete their own course."""
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('course-detail', kwargs={'pk': self.course1.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Course.objects.filter(pk=self.course1.pk).exists())

    def test_10_trainee_cannot_delete_course(self):
        """Trainee receives 403 on delete."""
        self.client.force_authenticate(user=self.trainee)
        url = reverse('course-detail', kwargs={'pk': self.course1.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CourseVisibilityTests(CourseTestBase):
    """Tests for role-based course list & detail visibility."""

    def setUp(self):
        super().setUp()
        self.published_course = Course.objects.create(
            title='Published Course',
            description='Everyone can see',
            category='General',
            level=CourseLevel.BEGINNER,
            duration_hours=10,
            status=CourseStatus.PUBLISHED,
            trainer=self.trainer1,
        )
        self.draft_course = Course.objects.create(
            title='Draft Course',
            description='Only trainer1 and admin',
            category='General',
            level=CourseLevel.INTERMEDIATE,
            duration_hours=12,
            status=CourseStatus.DRAFT,
            trainer=self.trainer1,
        )
        self.archived_course = Course.objects.create(
            title='Archived Course',
            description='Trainer2 archived',
            category='General',
            level=CourseLevel.ADVANCED,
            duration_hours=8,
            status=CourseStatus.ARCHIVED,
            trainer=self.trainer2,
        )

    def test_11_trainee_sees_only_published_courses(self):
        """Trainee only receives published courses in list view."""
        self.client.force_authenticate(user=self.trainee)
        url = reverse('course-list-create')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [c['title'] for c in response.data]
        self.assertIn('Published Course', titles)
        self.assertNotIn('Draft Course', titles)
        self.assertNotIn('Archived Course', titles)

    def test_12_trainee_cannot_view_draft_course_detail(self):
        """Trainee receives 404 when accessing draft course detail."""
        self.client.force_authenticate(user=self.trainee)
        url = reverse('course-detail', kwargs={'pk': self.draft_course.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_13_trainer_sees_own_courses_and_published_courses(self):
        """Trainer 1 sees own (draft/published) plus other's published courses."""
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('course-list-create')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [c['title'] for c in response.data]
        self.assertIn('Published Course', titles)
        self.assertIn('Draft Course', titles)
        # Trainer 1 should NOT see Trainer 2's archived course
        self.assertNotIn('Archived Course', titles)

    def test_14_admin_sees_all_courses(self):
        """Admin sees all courses regardless of status or trainer."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('course-list-create')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [c['title'] for c in response.data]
        self.assertIn('Published Course', titles)
        self.assertIn('Draft Course', titles)
        self.assertIn('Archived Course', titles)

    def test_15_unauthenticated_user_cannot_access_course_list(self):
        """Unauthenticated user receives 401 or 403."""
        url = reverse('course-list-create')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])



class SubjectTests(CourseTestBase):
    """Tests for Subject CRUD, ordering, and cascade behavior."""

    def setUp(self):
        super().setUp()
        self.course = Course.objects.create(
            title='Master Django',
            description='Comprehensive course',
            category='Backend',
            level=CourseLevel.ADVANCED,
            duration_hours=50,
            status=CourseStatus.DRAFT,
            trainer=self.trainer1,
        )
        self.published_course = Course.objects.create(
            title='Published Master Django',
            description='Comprehensive course',
            category='Backend',
            level=CourseLevel.ADVANCED,
            duration_hours=50,
            status=CourseStatus.PUBLISHED,
            trainer=self.trainer1,
        )

    def test_16_trainer_creates_subject_on_own_course(self):
        """Trainer adds subject to their own course."""
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('subject-list-create', kwargs={'course_id': self.course.pk})
        data = {
            'title': 'Module 1: Intro',
            'description': 'Getting started',
            'order': 1,
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Module 1: Intro')
        self.assertEqual(response.data['order'], 1)

    def test_17_trainer_cannot_create_subject_on_other_trainer_course(self):
        """Trainer 2 cannot add subject to Trainer 1's course."""
        self.client.force_authenticate(user=self.trainer2)
        url = reverse('subject-list-create', kwargs={'course_id': self.course.pk})
        data = {'title': 'Unauthorized Module', 'order': 1}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_18_admin_creates_subject_on_any_course(self):
        """Admin can add subject to any trainer's course."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('subject-list-create', kwargs={'course_id': self.course.pk})
        data = {'title': 'Admin Added Module', 'order': 1}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_19_subjects_returned_ordered_by_order_field(self):
        """Subjects are ordered by the order field."""
        Subject.objects.create(course=self.published_course, title='Module 3', order=3)
        Subject.objects.create(course=self.published_course, title='Module 1', order=1)
        Subject.objects.create(course=self.published_course, title='Module 2', order=2)

        self.client.force_authenticate(user=self.trainee)
        url = reverse('subject-list-create', kwargs={'course_id': self.published_course.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        orders = [s['order'] for s in response.data]
        self.assertEqual(orders, [1, 2, 3])

    def test_20_trainee_can_view_subjects_of_published_course(self):
        """Trainee can view subjects of a published course."""
        Subject.objects.create(course=self.published_course, title='Module 1', order=1)
        self.client.force_authenticate(user=self.trainee)
        url = reverse('subject-list-create', kwargs={'course_id': self.published_course.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_21_subject_update_and_delete_by_owner(self):
        """Trainer can update and delete subject on own draft course."""
        subject = Subject.objects.create(course=self.course, title='Old Title', order=1)
        self.client.force_authenticate(user=self.trainer1)

        url = reverse('subject-detail', kwargs={'course_id': self.course.pk, 'pk': subject.pk})

        # Update
        patch_res = self.client.patch(url, {'title': 'New Title'}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['title'], 'New Title')

        # Direct Delete
        del_res = self.client.delete(url)
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Subject.objects.filter(pk=subject.pk).exists())

    def test_21b_subject_delete_by_other_trainer_fails(self):
        """Trainer 2 cannot direct-delete a subject belonging to Trainer 1's course (403)."""
        subject = Subject.objects.create(course=self.course, title='T1 Subject', order=1)
        self.client.force_authenticate(user=self.trainer2)

        url = reverse('subject-detail', kwargs={'course_id': self.course.pk, 'pk': subject.pk})
        del_res = self.client.delete(url)
        self.assertEqual(del_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Subject.objects.filter(pk=subject.pk).exists())

    def test_21c_subject_delete_by_trainee_fails(self):
        """Trainee cannot direct-delete a subject from any course (403)."""
        subject = Subject.objects.create(course=self.course, title='Protected Subject', order=1)
        self.client.force_authenticate(user=self.trainee)

        url = reverse('subject-detail', kwargs={'course_id': self.course.pk, 'pk': subject.pk})
        del_res = self.client.delete(url)
        self.assertEqual(del_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Subject.objects.filter(pk=subject.pk).exists())

    def test_21d_subject_delete_by_admin_succeeds(self):
        """Admin can direct-delete a subject from any course (204)."""
        subject = Subject.objects.create(course=self.course, title='Admin Deletable Subject', order=1)
        self.client.force_authenticate(user=self.admin_user)

        url = reverse('subject-detail', kwargs={'course_id': self.course.pk, 'pk': subject.pk})
        del_res = self.client.delete(url)
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Subject.objects.filter(pk=subject.pk).exists())


class PermissionEdgeCaseTests(CourseTestBase):
    """Tests for role restrictions, publishing workflow, and integrity constraints."""

    def test_22_trainer_cannot_publish_course(self):
        """Trainer cannot set status to PUBLISHED on creation or update."""
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('course-list-create')

        # Attempt create with PUBLISHED
        data = {
            'title': 'Trainer Publish Attempt',
            'description': 'Trying to auto-publish',
            'category': 'Security',
            'level': CourseLevel.BEGINNER,
            'duration_hours': 10,
            'status': CourseStatus.PUBLISHED,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Create valid DRAFT course
        data['status'] = CourseStatus.DRAFT
        create_res = self.client.post(url, data, format='json')
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        course_id = create_res.data['id']

        # Attempt update to PUBLISHED
        detail_url = reverse('course-detail', kwargs={'pk': course_id})
        update_res = self.client.patch(detail_url, {'status': CourseStatus.PUBLISHED}, format='json')
        self.assertEqual(update_res.status_code, status.HTTP_403_FORBIDDEN)

        # Admin CAN publish the course
        self.client.force_authenticate(user=self.admin_user)
        admin_res = self.client.patch(detail_url, {'status': CourseStatus.PUBLISHED}, format='json')
        self.assertEqual(admin_res.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_res.data['status'], CourseStatus.PUBLISHED)

    def test_22b_trainer_cannot_modify_published_course(self):
        """Trainer cannot modify an already PUBLISHED course (403 Forbidden)."""
        published_course = Course.objects.create(
            title='Already Published Course',
            description='Live course',
            category='Tech',
            level=CourseLevel.BEGINNER,
            duration_hours=10,
            status=CourseStatus.PUBLISHED,
            trainer=self.trainer1,
        )
        self.client.force_authenticate(user=self.trainer1)
        detail_url = reverse('course-detail', kwargs={'pk': published_course.pk})

        # Trainer PATCH attempt on published course fails with 403
        patch_res = self.client.patch(detail_url, {'title': 'Modified Title'}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_403_FORBIDDEN)

        # Trainer PUT attempt on published course fails with 403
        put_res = self.client.put(detail_url, {
            'title': 'New Title',
            'description': 'New Desc',
            'category': 'Tech',
            'level': CourseLevel.INTERMEDIATE,
            'duration_hours': 15,
            'status': CourseStatus.DRAFT,
        }, format='json')
        self.assertEqual(put_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_22c_trainer_cannot_modify_subjects_on_published_course(self):
        """Trainer cannot add, update, or delete subjects on an already PUBLISHED course (403)."""
        published_course = Course.objects.create(
            title='Locked Published Course',
            description='Live course',
            category='Tech',
            level=CourseLevel.BEGINNER,
            duration_hours=10,
            status=CourseStatus.PUBLISHED,
            trainer=self.trainer1,
        )
        subject = Subject.objects.create(course=published_course, title='Live Module', order=1)

        self.client.force_authenticate(user=self.trainer1)

        # Add subject fails with 403
        list_url = reverse('subject-list-create', kwargs={'course_id': published_course.pk})
        post_res = self.client.post(list_url, {'title': 'New Subject', 'order': 2}, format='json')
        self.assertEqual(post_res.status_code, status.HTTP_403_FORBIDDEN)

        # Update subject fails with 403
        detail_url = reverse('subject-detail', kwargs={'course_id': published_course.pk, 'pk': subject.pk})
        patch_res = self.client.patch(detail_url, {'title': 'Changed Title'}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_403_FORBIDDEN)

        # Delete subject fails with 403
        del_res = self.client.delete(detail_url)
        self.assertEqual(del_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_22d_admin_can_modify_published_course_and_subjects(self):
        """Admin can modify a published course and its subjects."""
        published_course = Course.objects.create(
            title='Admin Editable Published Course',
            description='Live course',
            category='Tech',
            level=CourseLevel.BEGINNER,
            duration_hours=10,
            status=CourseStatus.PUBLISHED,
            trainer=self.trainer1,
        )
        subject = Subject.objects.create(course=published_course, title='Live Module', order=1)

        self.client.force_authenticate(user=self.admin_user)

        # Admin updates published course -> 200 OK
        detail_url = reverse('course-detail', kwargs={'pk': published_course.pk})
        patch_res = self.client.patch(detail_url, {'title': 'Admin Updated Live Course'}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)

        # Admin updates subject on published course -> 200 OK
        subj_detail_url = reverse('subject-detail', kwargs={'course_id': published_course.pk, 'pk': subject.pk})
        subj_patch_res = self.client.patch(subj_detail_url, {'title': 'Admin Updated Module'}, format='json')
        self.assertEqual(subj_patch_res.status_code, status.HTTP_200_OK)

    def test_23_admin_assigns_non_trainer_user_fails(self):
        """Admin assigning a Trainee as trainer fails validation."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('course-list-create')
        data = {
            'title': 'Bad Trainer Assignment',
            'description': 'Assigning trainee as trainer',
            'category': 'Management',
            'level': CourseLevel.BEGINNER,
            'duration_hours': 10,
            'trainer': self.trainee.id,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('trainer', response.data)

    def test_24_duplicate_subject_order_within_same_course_fails(self):
        """Duplicate subject order within the same course returns 400."""
        course = Course.objects.create(
            title='Order Test Course',
            description='Test ordering',
            category='Tech',
            level=CourseLevel.BEGINNER,
            duration_hours=10,
            status=CourseStatus.DRAFT,
            trainer=self.trainer1,
        )
        Subject.objects.create(course=course, title='Module 1', order=1)

        self.client.force_authenticate(user=self.trainer1)
        url = reverse('subject-list-create', kwargs={'course_id': course.pk})
        data = {'title': 'Duplicate Order Module', 'order': 1}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('order', response.data)

    def test_25_deleting_course_cascades_subjects(self):
        """Deleting a course also deletes all associated subjects."""
        course = Course.objects.create(
            title='Cascade Test Course',
            description='Test cascade delete',
            category='Tech',
            level=CourseLevel.BEGINNER,
            duration_hours=10,
            status=CourseStatus.DRAFT,
            trainer=self.trainer1,
        )
        s1 = Subject.objects.create(course=course, title='Module 1', order=1)
        s2 = Subject.objects.create(course=course, title='Module 2', order=2)

        self.client.force_authenticate(user=self.trainer1)
        url = reverse('course-detail', kwargs={'pk': course.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Course.objects.filter(pk=course.pk).exists())
        self.assertFalse(Subject.objects.filter(pk=s1.pk).exists())
        self.assertFalse(Subject.objects.filter(pk=s2.pk).exists())


class TrainerStudioTests(CourseTestBase):
    """Tests for Trainer Studio endpoints: dashboard-stats, my-courses, and roster."""

    def setUp(self):
        super().setUp()

        # Create courses for trainer1
        self.course_draft = Course.objects.create(
            title='Trainer1 Draft Course',
            description='Draft description',
            category='Engineering',
            level=CourseLevel.BEGINNER,
            duration_hours=8,
            status=CourseStatus.DRAFT,
            trainer=self.trainer1,
        )
        self.s1 = Subject.objects.create(course=self.course_draft, title='Draft Module 1', order=1)

        self.course_published = Course.objects.create(
            title='Trainer1 Published Course',
            description='Published description',
            category='Engineering',
            level=CourseLevel.INTERMEDIATE,
            duration_hours=12,
            status=CourseStatus.PUBLISHED,
            trainer=self.trainer1,
        )
        self.s2 = Subject.objects.create(course=self.course_published, title='Pub Module 1', order=1)
        self.s3 = Subject.objects.create(course=self.course_published, title='Pub Module 2', order=2)

        # Create course for trainer2
        self.course_t2 = Course.objects.create(
            title='Trainer2 Course',
            description='T2 description',
            category='Design',
            level=CourseLevel.ADVANCED,
            duration_hours=15,
            status=CourseStatus.PUBLISHED,
            trainer=self.trainer2,
        )

        # Create enrollment for trainee in trainer1 published course
        from enrollments.models import Enrollment, EnrollmentStatus, SubjectProgress
        self.enrollment = Enrollment.objects.create(
            trainee=self.trainee,
            course=self.course_published,
            status=EnrollmentStatus.ENROLLED,
        )
        sp = SubjectProgress.objects.create(
            enrollment=self.enrollment,
            subject=self.s2,
            completed=True,
        )
        SubjectProgress.objects.create(
            enrollment=self.enrollment,
            subject=self.s3,
            completed=False,
        )

    def test_26_trainer_can_get_dashboard_stats(self):
        """Trainer receives correct aggregate stats for their own courses."""
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('trainer-dashboard-stats')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_courses'], 2)
        self.assertEqual(response.data['published_courses'], 1)
        self.assertEqual(response.data['draft_courses'], 1)
        self.assertEqual(response.data['total_enrollments'], 1)
        self.assertEqual(response.data['average_progress'], 50.0)

    def test_27_trainee_cannot_get_trainer_dashboard_stats(self):
        """Trainee is denied access to trainer dashboard stats."""
        self.client.force_authenticate(user=self.trainee)
        url = reverse('trainer-dashboard-stats')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_28_unauthenticated_cannot_get_trainer_dashboard_stats(self):
        """Unauthenticated request is rejected."""
        url = reverse('trainer-dashboard-stats')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_29_trainer_can_get_my_courses_with_counts(self):
        """Trainer receives list of authored courses with subject and enrollment counts."""
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('trainer-my-courses')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        # Check published course metrics
        pub_item = next(c for c in response.data if c['id'] == self.course_published.id)
        self.assertEqual(pub_item['subject_count'], 2)
        self.assertEqual(pub_item['enrollment_count'], 1)
        self.assertEqual(pub_item['average_progress'], 50.0)

    def test_30_trainer_my_courses_does_not_include_other_trainers_courses(self):
        """Trainer1 does not see Trainer2's courses in my-courses."""
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('trainer-my-courses')
        response = self.client.get(url)

        course_ids = [c['id'] for c in response.data]
        self.assertNotIn(self.course_t2.id, course_ids)

    def test_31_trainer_can_get_course_roster(self):
        """Trainer can view roster for their own course."""
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('trainer-course-roster', kwargs={'course_id': self.course_published.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['username'], 'trainee1')
        self.assertEqual(response.data[0]['progress_percentage'], 50.0)
        self.assertEqual(response.data[0]['status'], 'ENROLLED')

    def test_32_trainer_cannot_view_roster_for_other_trainers_course(self):
        """Trainer1 cannot view roster for Trainer2's course."""
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('trainer-course-roster', kwargs={'course_id': self.course_t2.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_33_trainee_cannot_view_roster(self):
        """Trainee cannot access course roster endpoint."""
        self.client.force_authenticate(user=self.trainee)
        url = reverse('trainer-course-roster', kwargs={'course_id': self.course_published.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_34_admin_can_view_trainer_stats_and_roster(self):
        """Admin can access stats and any course's roster."""
        self.client.force_authenticate(user=self.admin_user)

        # Admin stats
        url_stats = reverse('trainer-dashboard-stats')
        resp_stats = self.client.get(url_stats)
        self.assertEqual(resp_stats.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_stats.data['total_courses'], 3)

        # Admin roster for any course
        url_roster = reverse('trainer-course-roster', kwargs={'course_id': self.course_published.id})
        resp_roster = self.client.get(url_roster)
        self.assertEqual(resp_roster.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_roster.data), 1)


class AdminCourseGovernanceTests(TestCase):
    """Tests for Admin Platform Stats and Course Governance (Step 11)."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='admin_boss',
            email='admin_boss@example.com',
            password='Password123!',
        )
        self.admin.profile.role = Role.ADMIN
        self.admin.profile.save()

        self.trainer = User.objects.create_user(
            username='trainer_mark',
            email='trainer_mark@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainer, role=Role.TRAINER)

        self.trainee = User.objects.create_user(
            username='trainee_john',
            email='trainee_john@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainee, role=Role.TRAINEE)

        self.draft_course = Course.objects.create(
            title='Draft Course for Review',
            description='Test Desc',
            category='Tech',
            level=CourseLevel.BEGINNER,
            duration_hours=5,
            status=CourseStatus.DRAFT,
            trainer=self.trainer,
        )

        self.published_course = Course.objects.create(
            title='Live Active Course',
            description='Test Desc',
            category='Tech',
            level=CourseLevel.INTERMEDIATE,
            duration_hours=10,
            status=CourseStatus.PUBLISHED,
            trainer=self.trainer,
        )

    def test_admin_can_get_platform_stats(self):
        """Admin can get full platform stats."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/courses/admin/platform-stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_users', response.data)
        self.assertIn('total_courses', response.data)
        self.assertIn('draft_courses', response.data)
        self.assertIn('published_courses', response.data)

    def test_trainer_cannot_access_platform_stats(self):
        """Trainer receives 403 on admin platform stats."""
        self.client.force_authenticate(user=self.trainer)
        response = self.client.get('/api/courses/admin/platform-stats/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_trainee_cannot_access_platform_stats(self):
        """Trainee receives 403 on admin platform stats."""
        self.client.force_authenticate(user=self.trainee)
        response = self.client.get('/api/courses/admin/platform-stats/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_list_all_courses(self):
        """Admin can list all courses across all statuses."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/courses/admin/courses/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_admin_can_filter_courses_by_status(self):
        """Admin can filter courses by status query parameter."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/courses/admin/courses/?status=DRAFT')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['status'], 'DRAFT')

    def test_admin_can_publish_draft_course(self):
        """Admin can approve and publish a DRAFT course."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/courses/admin/courses/{self.draft_course.id}/publish/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.draft_course.refresh_from_db()
        self.assertEqual(self.draft_course.status, CourseStatus.PUBLISHED)

    def test_admin_cannot_publish_non_draft_course(self):
        """Admin receives 400 when attempting to publish an already published course."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/courses/admin/courses/{self.published_course.id}/publish/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_reject_draft_course_with_reason(self):
        """Admin can reject a DRAFT course with mandatory reason."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/courses/admin/courses/{self.draft_course.id}/reject/',
            {'reason': 'Needs more curriculum details.'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.draft_course.refresh_from_db()
        self.assertEqual(self.draft_course.status, CourseStatus.REJECTED)
        self.assertEqual(self.draft_course.rejection_reason, 'Needs more curriculum details.')

    def test_admin_can_archive_published_course(self):
        """Admin can archive an active published course."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/courses/admin/courses/{self.published_course.id}/archive/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.published_course.refresh_from_db()
        self.assertEqual(self.published_course.status, CourseStatus.ARCHIVED)

    def test_non_admin_cannot_publish_course(self):
        """Trainers and trainees cannot call the publish endpoint."""
        self.client.force_authenticate(user=self.trainer)
        response = self.client.post(f'/api/courses/admin/courses/{self.draft_course.id}/publish/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

