"""
Automated unit and integration test suite for the discussions module (Step 12).
"""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Role, UserProfile
from courses.models import Course, CourseLevel, CourseStatus, Subject
from enrollments.models import Enrollment, EnrollmentStatus
from .models import (
    DiscussionThread,
    DiscussionReply,
    ThreadType,
    ThreadUpvote,
    DiscussionNotification,
)


class DiscussionsTestCase(TestCase):
    """
    Test suite covering course discussions, Q&A threads, replies, upvotes,
    trainer endorsements, announcements, and in-app notifications.
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Create Admin
        self.admin_user = User.objects.create_user(
            username='admin_step12',
            email='admin12@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.admin_user, role=Role.ADMIN)

        # 2. Create Trainer
        self.trainer_user = User.objects.create_user(
            username='trainer_step12',
            email='trainer12@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainer_user, role=Role.TRAINER)

        # 3. Create Enrolled Trainee A
        self.trainee_a = User.objects.create_user(
            username='trainee_a_step12',
            email='trainea12@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainee_a, role=Role.TRAINEE)

        # 4. Create Enrolled Trainee B
        self.trainee_b = User.objects.create_user(
            username='trainee_b_step12',
            email='traineb12@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainee_b, role=Role.TRAINEE)

        # 5. Create Non-Enrolled Trainee C
        self.trainee_c = User.objects.create_user(
            username='trainee_c_step12',
            email='trainec12@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainee_c, role=Role.TRAINEE)

        # 6. Create Course & Subjects
        self.course = Course.objects.create(
            title='Step 12 Advanced Python Architecture',
            category='Software Engineering',
            level=CourseLevel.ADVANCED,
            status=CourseStatus.PUBLISHED,
            duration_hours=20,
            trainer=self.trainer_user,
        )
        self.subject1 = Subject.objects.create(
            course=self.course,
            title='Module 1: Metaclasses & Descriptors',
            description='Deep dive into python internals.',
            order=1,
        )
        self.subject2 = Subject.objects.create(
            course=self.course,
            title='Module 2: Concurrency & Asyncio',
            description='Async IO event loops.',
            order=2,
        )

        # Course 2 (Unrelated)
        self.course2 = Course.objects.create(
            title='Step 12 Unrelated Course',
            category='Design',
            level=CourseLevel.BEGINNER,
            status=CourseStatus.PUBLISHED,
            duration_hours=5,
            trainer=self.admin_user,
        )
        self.subject_other = Subject.objects.create(
            course=self.course2,
            title='Module X',
            description='Other content',
            order=1,
        )

        # Enroll Trainee A and B in course
        self.enrollment_a = Enrollment.objects.create(
            trainee=self.trainee_a,
            course=self.course,
            status=EnrollmentStatus.ENROLLED,
        )
        self.enrollment_b = Enrollment.objects.create(
            trainee=self.trainee_b,
            course=self.course,
            status=EnrollmentStatus.ENROLLED,
        )

    # -------------------------------------------------------------------------
    # Test 1: Access Permissions
    # -------------------------------------------------------------------------

    def test_enrolled_trainee_can_list_threads(self):
        self.client.force_authenticate(user=self.trainee_a)
        res = self.client.get(f'/api/discussions/courses/{self.course.id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_non_enrolled_trainee_cannot_view_threads(self):
        self.client.force_authenticate(user=self.trainee_c)
        res = self.client.get(f'/api/discussions/courses/{self.course.id}/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # Test 2: Thread Creation
    # -------------------------------------------------------------------------

    def test_trainee_can_create_question_thread(self):
        self.client.force_authenticate(user=self.trainee_a)
        payload = {
            'title': 'How do metaclasses work under the hood?',
            'content': 'I am trying to understand the __new__ vs __init__ lifecycle.',
            'thread_type': 'QUESTION',
            'subject_id': self.subject1.id,
        }
        res = self.client.post(f'/api/discussions/courses/{self.course.id}/', payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['title'], payload['title'])
        self.assertEqual(res.data['subject'], self.subject1.id)
        self.assertEqual(res.data['thread_type'], 'QUESTION')

    def test_trainee_cannot_create_announcement(self):
        self.client.force_authenticate(user=self.trainee_a)
        payload = {
            'title': 'Important: Final Exam Postponed',
            'content': 'This is a fake announcement by a student.',
            'thread_type': 'ANNOUNCEMENT',
        }
        res = self.client.post(f'/api/discussions/courses/{self.course.id}/', payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('thread_type', res.data)

    def test_trainer_can_create_announcement_and_notifies_enrolled(self):
        self.client.force_authenticate(user=self.trainer_user)
        payload = {
            'title': 'Welcome to Step 12 Advanced Python!',
            'content': 'Office hours are scheduled every Wednesday at 4 PM UTC.',
            'thread_type': 'ANNOUNCEMENT',
        }
        res = self.client.post(f'/api/discussions/courses/{self.course.id}/', payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['is_pinned'])

        # Verify enrolled trainees received notifications
        notif_a = DiscussionNotification.objects.filter(
            recipient=self.trainee_a,
            notification_type=DiscussionNotification.NotificationType.NEW_ANNOUNCEMENT,
        ).exists()
        notif_b = DiscussionNotification.objects.filter(
            recipient=self.trainee_b,
            notification_type=DiscussionNotification.NotificationType.NEW_ANNOUNCEMENT,
        ).exists()
        self.assertTrue(notif_a)
        self.assertTrue(notif_b)

    def test_invalid_subject_id_rejected(self):
        self.client.force_authenticate(user=self.trainee_a)
        payload = {
            'title': 'Cross-course subject test question',
            'content': 'Trying to link a subject from another course.',
            'thread_type': 'QUESTION',
            'subject_id': self.subject_other.id,
        }
        res = self.client.post(f'/api/discussions/courses/{self.course.id}/', payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('subject_id', res.data)

    # -------------------------------------------------------------------------
    # Test 3: Thread Details & Replies
    # -------------------------------------------------------------------------

    def test_enrolled_trainee_can_reply_and_notifies_author(self):
        # Create thread by trainee A
        thread = DiscussionThread.objects.create(
            course=self.course,
            author=self.trainee_a,
            title='Understanding Async IO Queues',
            content='How does task cancellation work with async queues?',
        )

        # Trainee B replies
        self.client.force_authenticate(user=self.trainee_b)
        res = self.client.post(f'/api/discussions/{thread.id}/replies/', {
            'content': 'You need to catch asyncio.CancelledError inside the worker loop.',
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(thread.replies.count(), 1)

        # Trainee A should have received a notification
        notif = DiscussionNotification.objects.filter(
            recipient=self.trainee_a,
            notification_type=DiscussionNotification.NotificationType.NEW_REPLY,
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn('trainee_b_step12', notif.message)

    def test_locked_thread_rejects_replies(self):
        thread = DiscussionThread.objects.create(
            course=self.course,
            author=self.trainee_a,
            title='Locked Thread Question',
            content='Content for locked thread.',
            is_locked=True,
        )
        self.client.force_authenticate(user=self.trainee_b)
        res = self.client.post(f'/api/discussions/{thread.id}/replies/', {
            'content': 'Attempting to reply to locked thread.',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('locked', res.data['detail'].lower())

    # -------------------------------------------------------------------------
    # Test 4: Upvote Toggling
    # -------------------------------------------------------------------------

    def test_upvote_toggle(self):
        thread = DiscussionThread.objects.create(
            course=self.course,
            author=self.trainee_a,
            title='Great Question on Descriptors',
            content='Explanation of __get__ and __set__ protocols.',
        )
        self.client.force_authenticate(user=self.trainee_b)

        # First upvote -> True, count 1
        res1 = self.client.post(f'/api/discussions/{thread.id}/upvote/')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertTrue(res1.data['upvoted'])
        self.assertEqual(res1.data['upvotes_count'], 1)

        # Second upvote -> False, count 0
        res2 = self.client.post(f'/api/discussions/{thread.id}/upvote/')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertFalse(res2.data['upvoted'])
        self.assertEqual(res2.data['upvotes_count'], 0)

    # -------------------------------------------------------------------------
    # Test 5: Resolution & Pinning
    # -------------------------------------------------------------------------

    def test_author_or_trainer_can_resolve_thread(self):
        thread = DiscussionThread.objects.create(
            course=self.course,
            author=self.trainee_a,
            title='How to resolve asyncio pending tasks?',
            content='Need clarification.',
        )

        # Trainee B (not author, not trainer) tries to resolve -> 403
        self.client.force_authenticate(user=self.trainee_b)
        res_fail = self.client.post(f'/api/discussions/{thread.id}/resolve/')
        self.assertEqual(res_fail.status_code, status.HTTP_403_FORBIDDEN)

        # Trainee A (author) resolves -> 200
        self.client.force_authenticate(user=self.trainee_a)
        res_ok = self.client.post(f'/api/discussions/{thread.id}/resolve/')
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        self.assertTrue(res_ok.data['is_resolved'])

        # Trainer un-resolves -> 200
        self.client.force_authenticate(user=self.trainer_user)
        res_trainer = self.client.post(f'/api/discussions/{thread.id}/resolve/')
        self.assertEqual(res_trainer.status_code, status.HTTP_200_OK)
        self.assertFalse(res_trainer.data['is_resolved'])

    def test_trainer_can_pin_thread(self):
        thread = DiscussionThread.objects.create(
            course=self.course,
            author=self.trainee_a,
            title='Syllabus FAQ',
            content='General syllabus information.',
        )

        # Trainee tries to pin -> 403
        self.client.force_authenticate(user=self.trainee_a)
        res_fail = self.client.post(f'/api/discussions/{thread.id}/pin/')
        self.assertEqual(res_fail.status_code, status.HTTP_403_FORBIDDEN)

        # Trainer pins -> 200
        self.client.force_authenticate(user=self.trainer_user)
        res_pin = self.client.post(f'/api/discussions/{thread.id}/pin/')
        self.assertEqual(res_pin.status_code, status.HTTP_200_OK)
        self.assertTrue(res_pin.data['is_pinned'])

    # -------------------------------------------------------------------------
    # Test 6: Instructor Endorsement of Replies
    # -------------------------------------------------------------------------

    def test_trainer_can_endorse_reply(self):
        thread = DiscussionThread.objects.create(
            course=self.course,
            author=self.trainee_a,
            title='Best practice for database connection pooling',
            content='Should we use asyncpg or psycopg3?',
        )
        reply = DiscussionReply.objects.create(
            thread=thread,
            author=self.trainee_b,
            content='Use asyncpg with SQLAlchemy async engine.',
        )

        # Trainee tries to endorse -> 403
        self.client.force_authenticate(user=self.trainee_a)
        res_fail = self.client.post(f'/api/discussions/replies/{reply.id}/endorse/')
        self.assertEqual(res_fail.status_code, status.HTTP_403_FORBIDDEN)

        # Trainer endorses -> 200
        self.client.force_authenticate(user=self.trainer_user)
        res_ok = self.client.post(f'/api/discussions/replies/{reply.id}/endorse/')
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        self.assertTrue(res_ok.data['is_instructor_endorsed'])

    # -------------------------------------------------------------------------
    # Test 7: Thread & Reply Edit / Delete
    # -------------------------------------------------------------------------

    def test_author_and_admin_can_edit_and_delete(self):
        thread = DiscussionThread.objects.create(
            course=self.course,
            author=self.trainee_a,
            title='Initial Thread Title',
            content='Initial content string here.',
        )

        # Trainee B cannot edit Trainee A's thread
        self.client.force_authenticate(user=self.trainee_b)
        res_unauth = self.client.patch(f'/api/discussions/{thread.id}/', {
            'title': 'Hacked Title By Other User',
        })
        self.assertEqual(res_unauth.status_code, status.HTTP_403_FORBIDDEN)

        # Trainee A can edit
        self.client.force_authenticate(user=self.trainee_a)
        res_edit = self.client.patch(f'/api/discussions/{thread.id}/', {
            'title': 'Updated Title By Author',
        })
        self.assertEqual(res_edit.status_code, status.HTTP_200_OK)
        self.assertEqual(res_edit.data['title'], 'Updated Title By Author')

        # Admin can delete
        self.client.force_authenticate(user=self.admin_user)
        res_del = self.client.delete(f'/api/discussions/{thread.id}/')
        self.assertEqual(res_del.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DiscussionThread.objects.filter(id=thread.id).exists())

    # -------------------------------------------------------------------------
    # Test 8: Trainer Inbox & Notifications
    # -------------------------------------------------------------------------

    def test_trainer_inbox_lists_questions(self):
        # Create 2 questions in trainer's course
        DiscussionThread.objects.create(
            course=self.course,
            author=self.trainee_a,
            title='Inbox Question 1',
            content='Question content 1.',
            is_resolved=False,
        )
        DiscussionThread.objects.create(
            course=self.course,
            author=self.trainee_b,
            title='Inbox Question 2',
            content='Question content 2.',
            is_resolved=True,
        )

        self.client.force_authenticate(user=self.trainer_user)
        res = self.client.get('/api/discussions/trainer/inbox/?resolved=false')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['title'], 'Inbox Question 1')

    def test_notifications_list_and_mark_read(self):
        thread = DiscussionThread.objects.create(
            course=self.course,
            author=self.trainee_a,
            title='Sample Thread',
            content='Sample content.',
        )
        notif = DiscussionNotification.objects.create(
            recipient=self.trainee_a,
            thread=thread,
            notification_type=DiscussionNotification.NotificationType.NEW_REPLY,
            title='New Reply Title',
            message='Some message body',
            is_read=False,
        )

        self.client.force_authenticate(user=self.trainee_a)

        # 1. Fetch notifications
        res_list = self.client.get('/api/discussions/notifications/')
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(res_list.data['unread_count'], 1)
        self.assertEqual(len(res_list.data['notifications']), 1)

        # 2. Mark single as read
        res_read = self.client.post(f'/api/discussions/notifications/{notif.id}/read/')
        self.assertEqual(res_read.status_code, status.HTTP_200_OK)
        self.assertTrue(res_read.data['is_read'])

        # 3. Mark all as read
        res_all = self.client.post('/api/discussions/notifications/read-all/')
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)
