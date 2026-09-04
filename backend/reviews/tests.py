"""
Comprehensive automated tests for Course Reviews and Ratings (Step 14).
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Role, UserProfile
from courses.models import Course, CourseLevel, CourseStatus
from enrollments.models import Enrollment, EnrollmentStatus
from reviews.models import CourseReview

User = get_user_model()


class CourseReviewTests(TestCase):
    """
    Test suite for Step 14: Course Reviews, Ratings & Social Proof Engine.
    """

    def setUp(self):
        self.client = APIClient()

        # Users with explicit UserProfile creation
        self.trainer = User.objects.create_user(
            username='prof_albus',
            email='albus@example.com',
            password='password123',
        )
        UserProfile.objects.create(user=self.trainer, role=Role.TRAINER)

        self.trainee1 = User.objects.create_user(
            username='hermione_granger',
            email='hermione@example.com',
            password='password123',
        )
        UserProfile.objects.create(user=self.trainee1, role=Role.TRAINEE)

        self.trainee2 = User.objects.create_user(
            username='ron_weasley',
            email='ron@example.com',
            password='password123',
        )
        UserProfile.objects.create(user=self.trainee2, role=Role.TRAINEE)

        self.admin = User.objects.create_user(
            username='minerva_mcgonagall',
            email='minerva@example.com',
            password='password123',
            is_staff=True,
        )
        UserProfile.objects.create(user=self.admin, role=Role.ADMIN)

        # Published Course
        self.course = Course.objects.create(
            title='Advanced Transfiguration',
            description='In-depth transfiguration principles and techniques.',
            category='Magic',
            level=CourseLevel.ADVANCED,
            duration_hours=40,
            status=CourseStatus.PUBLISHED,
            trainer=self.trainer,
        )

        # Enrollments
        self.enrollment1 = Enrollment.objects.create(
            trainee=self.trainee1,
            course=self.course,
            status=EnrollmentStatus.ENROLLED,
        )

    def test_01_unauthenticated_cannot_submit_review(self):
        url = f'/api/courses/{self.course.id}/reviews/'
        res = self.client.post(url, {'rating': 5, 'comment': 'Brilliant course!'})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_02_non_enrolled_trainee_cannot_submit_review(self):
        self.client.force_authenticate(user=self.trainee2)
        url = f'/api/courses/{self.course.id}/reviews/'
        res = self.client.post(url, {
            'rating': 5,
            'title': 'Great Course',
            'comment': 'I am not enrolled but trying to review.',
        })
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_03_enrolled_trainee_can_submit_review(self):
        self.client.force_authenticate(user=self.trainee1)
        url = f'/api/courses/{self.course.id}/reviews/'
        res = self.client.post(url, {
            'rating': 5,
            'title': 'Exceptional content',
            'comment': 'Comprehensive coverage of transfiguration formulas.',
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['rating'], 5)
        self.assertEqual(res.data['trainee_username'], 'hermione_granger')

        # Verify course stats were updated
        self.course.refresh_from_db()
        self.assertEqual(float(self.course.average_rating), 5.0)
        self.assertEqual(self.course.review_count, 1)

    def test_04_rating_validation_bounds(self):
        self.client.force_authenticate(user=self.trainee1)
        url = f'/api/courses/{self.course.id}/reviews/'

        # Zero rating
        res_zero = self.client.post(url, {'rating': 0, 'comment': 'Too low'})
        self.assertEqual(res_zero.status_code, status.HTTP_400_BAD_REQUEST)

        # Exceeds 5
        res_high = self.client.post(url, {'rating': 6, 'comment': 'Too high'})
        self.assertEqual(res_high.status_code, status.HTTP_400_BAD_REQUEST)

        # Short comment
        res_short = self.client.post(url, {'rating': 4, 'comment': 'Bad'})
        self.assertEqual(res_short.status_code, status.HTTP_400_BAD_REQUEST)

    def test_05_single_review_per_trainee_updates_existing(self):
        self.client.force_authenticate(user=self.trainee1)
        url = f'/api/courses/{self.course.id}/reviews/'

        # Initial review: 4 stars
        res1 = self.client.post(url, {
            'rating': 4,
            'title': 'Good pace',
            'comment': 'Solid material throughout.',
        })
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Update to 5 stars
        res2 = self.client.post(url, {
            'rating': 5,
            'title': 'Revised: Truly Outstanding',
            'comment': 'Updated review after finishing the final project.',
        })
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data['rating'], 5)

        # Only 1 review should exist
        self.assertEqual(CourseReview.objects.filter(course=self.course).count(), 1)
        self.course.refresh_from_db()
        self.assertEqual(float(self.course.average_rating), 5.0)
        self.assertEqual(self.course.review_count, 1)

    def test_06_course_average_rating_and_count_calculation(self):
        # Enroll trainee2
        Enrollment.objects.create(
            trainee=self.trainee2,
            course=self.course,
            status=EnrollmentStatus.ENROLLED,
        )

        CourseReview.objects.create(
            course=self.course,
            trainee=self.trainee1,
            rating=5,
            comment='Superb training!',
        )
        CourseReview.objects.create(
            course=self.course,
            trainee=self.trainee2,
            rating=3,
            comment='Moderate difficulty.',
        )

        self.course.refresh_from_db()
        self.assertEqual(self.course.review_count, 2)
        # (5 + 3) / 2 = 4.0
        self.assertEqual(float(self.course.average_rating), 4.0)

    def test_07_trainer_cannot_review_own_course(self):
        self.client.force_authenticate(user=self.trainer)
        url = f'/api/courses/{self.course.id}/reviews/'
        res = self.client.post(url, {
            'rating': 5,
            'comment': 'My own course is the best!',
        })
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_08_public_can_view_visible_reviews_and_distribution(self):
        CourseReview.objects.create(
            course=self.course,
            trainee=self.trainee1,
            rating=5,
            title='Masterful',
            comment='Detailed and clear.',
        )

        # Anonymous GET request
        url = f'/api/courses/{self.course.id}/reviews/'
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['course_id'], self.course.id)
        self.assertEqual(len(res.data['reviews']), 1)
        self.assertEqual(res.data['rating_distribution'][5], 1)
        self.assertEqual(res.data['rating_distribution'][4], 0)

    def test_09_admin_can_moderate_or_hide_review(self):
        review = CourseReview.objects.create(
            course=self.course,
            trainee=self.trainee1,
            rating=1,
            comment='Inappropriate remark.',
            is_visible=True,
        )
        self.course.refresh_from_db()
        self.assertEqual(self.course.review_count, 1)

        # Admin moderates (hides) review
        self.client.force_authenticate(user=self.admin)
        mod_url = f'/api/reviews/{review.id}/moderate/'
        res = self.client.post(mod_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data['is_visible'])

        # Check public listing does not include hidden review
        self.client.logout()
        list_url = f'/api/courses/{self.course.id}/reviews/'
        list_res = self.client.get(list_url)
        self.assertEqual(len(list_res.data['reviews']), 0)

        # Course stats exclude hidden review
        self.course.refresh_from_db()
        self.assertEqual(self.course.review_count, 0)

    def test_10_review_owner_can_delete_review(self):
        review = CourseReview.objects.create(
            course=self.course,
            trainee=self.trainee1,
            rating=4,
            comment='Solid course.',
        )
        self.course.refresh_from_db()
        self.assertEqual(self.course.review_count, 1)

        self.client.force_authenticate(user=self.trainee1)
        del_url = f'/api/reviews/{review.id}/'
        res = self.client.delete(del_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertFalse(CourseReview.objects.filter(id=review.id).exists())
        self.course.refresh_from_db()
        self.assertEqual(self.course.review_count, 0)
        self.assertEqual(float(self.course.average_rating), 0.0)

    def test_11_non_owner_trainee_cannot_delete_review(self):
        review = CourseReview.objects.create(
            course=self.course,
            trainee=self.trainee1,
            rating=5,
            comment='Hermione review.',
        )
        self.client.force_authenticate(user=self.trainee2)
        del_url = f'/api/reviews/{review.id}/'
        res = self.client.delete(del_url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(CourseReview.objects.filter(id=review.id).exists())

    def test_12_trainer_feedback_portal(self):
        CourseReview.objects.create(
            course=self.course,
            trainee=self.trainee1,
            rating=5,
            title='Incredible Teacher',
            comment='Learned so much from Professor Albus.',
        )

        self.client.force_authenticate(user=self.trainer)
        res = self.client.get('/api/reviews/trainer/feedback/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['total_reviews'], 1)
        self.assertEqual(res.data['trainer_average_rating'], 5.0)
        self.assertEqual(res.data['reviews'][0]['trainee_username'], 'hermione_granger')

    def test_13_dropped_trainee_cannot_submit_review(self):
        self.enrollment1.status = EnrollmentStatus.DROPPED
        self.enrollment1.save()

        self.client.force_authenticate(user=self.trainee1)
        url = f'/api/courses/{self.course.id}/reviews/'
        res = self.client.post(url, {'rating': 2, 'comment': 'Dropped the course.'})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_14_my_review_endpoint(self):
        url = f'/api/courses/{self.course.id}/reviews/my-review/'

        # Before reviewing
        self.client.force_authenticate(user=self.trainee1)
        res_none = self.client.get(url)
        self.assertEqual(res_none.status_code, status.HTTP_200_OK)
        self.assertIsNone(res_none.data)

        # After creating review
        CourseReview.objects.create(
            course=self.course,
            trainee=self.trainee1,
            rating=5,
            title='Exemplary',
            comment='My genuine review.',
        )
        res_exists = self.client.get(url)
        self.assertEqual(res_exists.status_code, status.HTTP_200_OK)
        self.assertEqual(res_exists.data['rating'], 5)
        self.assertEqual(res_exists.data['title'], 'Exemplary')

    def test_15_course_list_serializer_includes_rating_stats(self):
        CourseReview.objects.create(
            course=self.course,
            trainee=self.trainee1,
            rating=4,
            comment='Good overview.',
        )
        self.course.refresh_from_db()

        self.client.force_authenticate(user=self.trainee1)
        res = self.client.get('/api/courses/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        course_item = next(c for c in res.data if c['id'] == self.course.id)
        self.assertIn('average_rating', course_item)
        self.assertIn('review_count', course_item)
        self.assertEqual(float(course_item['average_rating']), 4.0)
        self.assertEqual(course_item['review_count'], 1)
