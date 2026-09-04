"""
Unit tests for the assessments app.

Covers:
- Trainer assessment CRUD & ownership validation
- MCQ question management & permissions
- Trainee anti-cheat quiz taking (correct answer omission)
- Automated grading & passing percentage threshold calculations
- Subject progress integration
- Attempt privacy & trainer roster visibility
- Admin oversight
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Role, UserProfile
from courses.models import Course, CourseLevel, CourseStatus, Subject
from enrollments.models import Enrollment, EnrollmentStatus, SubjectProgress
from .models import (
    Assessment,
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentStatus,
    Question,
    QuestionOptionChoice,
)

User = get_user_model()


class AssessmentTestBase(APITestCase):
    """Base setup with Admin, 2 Trainers, 2 Trainees, Courses, Subjects, and Enrollments."""

    def setUp(self):
        # Admin
        self.admin_user = User.objects.create_user(
            username='admin_user',
            email='admin@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.admin_user, role=Role.ADMIN)

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

        # Course 1 (owned by Trainer 1)
        self.course1 = Course.objects.create(
            title='Django Advanced',
            description='Advanced Django Mastery',
            category='Backend',
            level=CourseLevel.ADVANCED,
            duration_hours=40,
            status=CourseStatus.PUBLISHED,
            trainer=self.trainer1,
        )

        # Course 2 (owned by Trainer 2)
        self.course2 = Course.objects.create(
            title='React Fundamentals',
            description='Frontend React Architecture',
            category='Frontend',
            level=CourseLevel.BEGINNER,
            duration_hours=20,
            status=CourseStatus.PUBLISHED,
            trainer=self.trainer2,
        )

        # Subject on Course 1
        self.subject1 = Subject.objects.create(
            course=self.course1,
            title='Module 1: Models & ORM',
            description='Deep dive into Django ORM',
            order=1,
        )

        # Enrollment: Trainee 1 is enrolled in Course 1
        self.enrollment1 = Enrollment.objects.create(
            trainee=self.trainee1,
            course=self.course1,
            status=EnrollmentStatus.ENROLLED,
        )


class TrainerAssessmentManagementTests(AssessmentTestBase):
    """Tests for trainer assessment creation, modification, and question authoring."""

    def test_01_trainer_creates_assessment_for_own_course(self):
        """Trainer 1 creates an assessment on their own course."""
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('trainer-course-assessment-list-create', kwargs={'course_id': self.course1.pk})
        data = {
            'title': 'ORM Quiz',
            'description': 'Test your ORM skills',
            'passing_percentage': 80,
            'duration_minutes': 25,
            'status': AssessmentStatus.DRAFT,
            'subject': self.subject1.pk,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'ORM Quiz')
        self.assertEqual(response.data['passing_percentage'], 80)
        self.assertEqual(response.data['course'], self.course1.pk)

    def test_02_trainer_cannot_create_assessment_for_other_trainer_course(self):
        """Trainer 2 cannot create assessment on Trainer 1's course (403)."""
        self.client.force_authenticate(user=self.trainer2)
        url = reverse('trainer-course-assessment-list-create', kwargs={'course_id': self.course1.pk})
        data = {
            'title': 'Unauthorized Quiz',
            'passing_percentage': 70,
            'duration_minutes': 30,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_03_trainee_cannot_create_assessment(self):
        """Trainee receives 403 when trying to create an assessment."""
        self.client.force_authenticate(user=self.trainee1)
        url = reverse('trainer-course-assessment-list-create', kwargs={'course_id': self.course1.pk})
        response = self.client.post(url, {'title': 'Hacked Quiz'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_04_trainer_updates_own_assessment(self):
        """Trainer 1 can update metadata and publish own assessment."""
        assessment = Assessment.objects.create(
            course=self.course1,
            title='Draft Quiz',
            passing_percentage=60,
            created_by=self.trainer1,
        )
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('trainer-assessment-detail', kwargs={'pk': assessment.pk})
        patch_res = self.client.patch(url, {'title': 'Updated Quiz', 'status': AssessmentStatus.PUBLISHED}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['title'], 'Updated Quiz')
        self.assertEqual(patch_res.data['status'], AssessmentStatus.PUBLISHED)

    def test_05_trainer_cannot_update_other_trainer_assessment(self):
        """Trainer 2 cannot update Trainer 1's assessment (403)."""
        assessment = Assessment.objects.create(
            course=self.course1,
            title='T1 Quiz',
            created_by=self.trainer1,
        )
        self.client.force_authenticate(user=self.trainer2)
        url = reverse('trainer-assessment-detail', kwargs={'pk': assessment.pk})
        patch_res = self.client.patch(url, {'title': 'Tampered Title'}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_06_trainer_adds_mcq_to_own_assessment(self):
        """Trainer 1 adds an MCQ question to their assessment."""
        assessment = Assessment.objects.create(
            course=self.course1,
            title='Quiz with MCQs',
            created_by=self.trainer1,
        )
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('trainer-question-create', kwargs={'assessment_id': assessment.pk})
        data = {
            'question_text': 'What does ORM stand for?',
            'option_a': 'Object Relational Mapping',
            'option_b': 'Online Routing Module',
            'option_c': 'Operational Resource Manager',
            'option_d': 'Object Repository Model',
            'correct_answer': 'A',
            'explanation': 'ORM maps objects to relational databases.',
            'marks': 2,
            'order': 1,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['correct_answer'], 'A')
        self.assertEqual(response.data['marks'], 2)

    def test_07_trainer_cannot_add_mcq_to_other_trainer_assessment(self):
        """Trainer 2 cannot add questions to Trainer 1's assessment (403)."""
        assessment = Assessment.objects.create(
            course=self.course1,
            title='T1 Quiz',
            created_by=self.trainer1,
        )
        self.client.force_authenticate(user=self.trainer2)
        url = reverse('trainer-question-create', kwargs={'assessment_id': assessment.pk})
        data = {
            'question_text': 'Unauthorized Question?',
            'option_a': 'A',
            'option_b': 'B',
            'option_c': 'C',
            'option_d': 'D',
            'correct_answer': 'A',
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_08_trainer_updates_and_deletes_own_question(self):
        """Trainer 1 can update and delete their own MCQ question."""
        assessment = Assessment.objects.create(
            course=self.course1,
            title='Question Delete Test',
            created_by=self.trainer1,
        )
        q = Question.objects.create(
            assessment=assessment,
            question_text='Old Q',
            option_a='1',
            option_b='2',
            option_c='3',
            option_d='4',
            correct_answer='B',
            marks=1,
            order=1,
        )
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('trainer-question-detail', kwargs={'pk': q.pk})

        # Update
        patch_res = self.client.patch(url, {'question_text': 'Updated Q', 'correct_answer': 'C'}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['correct_answer'], 'C')

        # Delete
        del_res = self.client.delete(url)
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Question.objects.filter(pk=q.pk).exists())

    def test_09_trainer_cannot_delete_other_trainer_question(self):
        """Trainer 2 cannot delete questions on Trainer 1's assessment (403)."""
        assessment = Assessment.objects.create(
            course=self.course1,
            title='T1 Quiz',
            created_by=self.trainer1,
        )
        q = Question.objects.create(
            assessment=assessment,
            question_text='T1 Question',
            option_a='1', option_b='2', option_c='3', option_d='4',
            correct_answer='A',
        )
        self.client.force_authenticate(user=self.trainer2)
        url = reverse('trainer-question-detail', kwargs={'pk': q.pk})
        del_res = self.client.delete(url)
        self.assertEqual(del_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Question.objects.filter(pk=q.pk).exists())

    def test_10_trainee_cannot_add_edit_delete_questions(self):
        """Trainee receives 403 on question endpoints."""
        assessment = Assessment.objects.create(
            course=self.course1,
            title='Protected Quiz',
            created_by=self.trainer1,
        )
        q = Question.objects.create(
            assessment=assessment,
            question_text='Sample Q',
            option_a='1', option_b='2', option_c='3', option_d='4',
            correct_answer='A',
        )
        self.client.force_authenticate(user=self.trainee1)

        create_url = reverse('trainer-question-create', kwargs={'assessment_id': assessment.pk})
        self.assertEqual(self.client.post(create_url, {}).status_code, status.HTTP_403_FORBIDDEN)

        detail_url = reverse('trainer-question-detail', kwargs={'pk': q.pk})
        self.assertEqual(self.client.patch(detail_url, {}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(detail_url).status_code, status.HTTP_403_FORBIDDEN)


class TraineeQuizEngineTests(AssessmentTestBase):
    """Tests for trainee quiz taking, anti-cheat protections, scoring, and progress."""

    def setUp(self):
        super().setUp()
        self.published_quiz = Assessment.objects.create(
            course=self.course1,
            subject=self.subject1,
            title='Final ORM Exam',
            description='Comprehensive evaluation',
            passing_percentage=75,
            duration_minutes=30,
            status=AssessmentStatus.PUBLISHED,
            created_by=self.trainer1,
        )
        self.q1 = Question.objects.create(
            assessment=self.published_quiz,
            question_text='What is a QuerySet?',
            option_a='A collection of database queries',
            option_b='A lazy collection of database objects',
            option_c='A SQL database table',
            option_d='A Django template tag',
            correct_answer='B',
            explanation='QuerySets are lazy collections of model instances.',
            marks=2,
            order=1,
        )
        self.q2 = Question.objects.create(
            assessment=self.published_quiz,
            question_text='Which method executes a database query immediately?',
            option_a='.filter()',
            option_b='.exclude()',
            option_c='.count()',
            option_d='.all()',
            correct_answer='C',
            explanation='.count() hits the database immediately with SELECT COUNT(*).',
            marks=2,
            order=2,
        )

        self.draft_quiz = Assessment.objects.create(
            course=self.course1,
            title='Unpublished Draft Quiz',
            status=AssessmentStatus.DRAFT,
            created_by=self.trainer1,
        )

    def test_11_enrolled_trainee_lists_published_assessments(self):
        """Enrolled Trainee 1 sees published assessments, but not drafts."""
        self.client.force_authenticate(user=self.trainee1)
        url = reverse('trainee-course-assessment-list', kwargs={'course_id': self.course1.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [a['title'] for a in response.data]
        self.assertIn('Final ORM Exam', titles)
        self.assertNotIn('Unpublished Draft Quiz', titles)

    def test_12_unenrolled_trainee_cannot_list_assessments(self):
        """Trainee 2 (not enrolled in Course 1) cannot list its assessments (403)."""
        self.client.force_authenticate(user=self.trainee2)
        url = reverse('trainee-course-assessment-list', kwargs={'course_id': self.course1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_13_trainee_cannot_see_draft_assessment(self):
        """Trainee 1 receives 403 when trying to access /take/ on a DRAFT assessment."""
        self.client.force_authenticate(user=self.trainee1)
        url = reverse('trainee-assessment-take', kwargs={'pk': self.draft_quiz.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_14_trainee_take_endpoint_omits_correct_answer_and_explanation(self):
        """Anti-cheat verification: /take/ endpoint strictly omits answers and explanations."""
        self.client.force_authenticate(user=self.trainee1)
        url = reverse('trainee-assessment-take', kwargs={'pk': self.published_quiz.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['questions']), 2)

        for q in response.data['questions']:
            self.assertNotIn('correct_answer', q)
            self.assertNotIn('explanation', q)
            self.assertNotIn('is_correct', q)
            self.assertNotIn('marks_obtained', q)
            self.assertIn('question_text', q)
            self.assertIn('option_a', q)
            self.assertIn('option_b', q)
            self.assertIn('option_c', q)
            self.assertIn('option_d', q)

    def test_15_trainee_submits_quiz_and_calculates_score_correctly(self):
        """Trainee submits 1 correct and 1 incorrect answer -> 50% FAIL (passing is 75%)."""
        self.client.force_authenticate(user=self.trainee1)
        url = reverse('trainee-assessment-submit', kwargs={'pk': self.published_quiz.pk})
        payload = {
            'answers': [
                {'question_id': self.q1.pk, 'selected_option': 'B'},  # Correct (2 marks)
                {'question_id': self.q2.pk, 'selected_option': 'A'},  # Incorrect (0 marks, correct is C)
            ]
        }
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['score'], 2)
        self.assertEqual(response.data['total_marks'], 4)
        self.assertEqual(response.data['percentage'], 50.0)
        self.assertFalse(response.data['passed'])

        # Check DB attempt
        attempt = AssessmentAttempt.objects.get(pk=response.data['id'])
        self.assertEqual(attempt.trainee, self.trainee1)
        self.assertEqual(attempt.score, 2)
        self.assertFalse(attempt.passed)

        # After submission, answers detail includes review
        self.assertEqual(len(response.data['answers']), 2)
        ans1 = next(a for a in response.data['answers'] if a['question_id'] == self.q1.pk)
        self.assertTrue(ans1['is_correct'])
        self.assertEqual(ans1['correct_answer'], 'B')

        ans2 = next(a for a in response.data['answers'] if a['question_id'] == self.q2.pk)
        self.assertFalse(ans2['is_correct'])
        self.assertEqual(ans2['correct_answer'], 'C')

    def test_16_trainee_submits_all_correct_and_passes(self):
        """Trainee submits all correct answers -> 100% PASS."""
        self.client.force_authenticate(user=self.trainee1)
        url = reverse('trainee-assessment-submit', kwargs={'pk': self.published_quiz.pk})
        payload = {
            'answers': [
                {'question_id': self.q1.pk, 'selected_option': 'B'},  # Correct
                {'question_id': self.q2.pk, 'selected_option': 'C'},  # Correct
            ]
        }
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['score'], 4)
        self.assertEqual(response.data['total_marks'], 4)
        self.assertEqual(response.data['percentage'], 100.0)
        self.assertTrue(response.data['passed'])

    def test_17_passing_subject_assessment_marks_subject_progress_complete(self):
        """Passing an assessment linked to a Subject auto-marks SubjectProgress as completed."""
        self.client.force_authenticate(user=self.trainee1)
        url = reverse('trainee-assessment-submit', kwargs={'pk': self.published_quiz.pk})
        payload = {
            'answers': [
                {'question_id': self.q1.pk, 'selected_option': 'B'},
                {'question_id': self.q2.pk, 'selected_option': 'C'},
            ]
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['passed'])

        # Verify SubjectProgress
        sp = SubjectProgress.objects.get(enrollment=self.enrollment1, subject=self.subject1)
        self.assertTrue(sp.completed)

    def test_18_trainee_can_view_own_attempt_detail(self):
        """Trainee can view their past attempt results."""
        attempt = AssessmentAttempt.objects.create(
            assessment=self.published_quiz,
            trainee=self.trainee1,
            score=4,
            total_marks=4,
            percentage=100.0,
            passed=True,
        )
        self.client.force_authenticate(user=self.trainee1)
        url = reverse('trainee-attempt-detail', kwargs={'pk': attempt.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['score'], 4)
        self.assertEqual(response.data['percentage'], 100.0)

    def test_19_trainee_cannot_view_other_trainees_attempt_detail(self):
        """Trainee 2 cannot view Trainee 1's attempt (403)."""
        attempt = AssessmentAttempt.objects.create(
            assessment=self.published_quiz,
            trainee=self.trainee1,
            score=4,
            total_marks=4,
            percentage=100.0,
            passed=True,
        )
        self.client.force_authenticate(user=self.trainee2)
        url = reverse('trainee-attempt-detail', kwargs={'pk': attempt.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_20_trainer_can_view_student_results_for_own_course(self):
        """Trainer 1 can view all student results for their assessment."""
        AssessmentAttempt.objects.create(
            assessment=self.published_quiz,
            trainee=self.trainee1,
            score=4,
            total_marks=4,
            percentage=100.0,
            passed=True,
        )
        self.client.force_authenticate(user=self.trainer1)
        url = reverse('trainer-assessment-results', kwargs={'assessment_id': self.published_quiz.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['trainee_username'], 'trainee1')
        self.assertEqual(response.data[0]['percentage'], 100.0)

    def test_21_trainer_cannot_view_results_for_other_trainer_course(self):
        """Trainer 2 cannot view results for Trainer 1's assessment (403)."""
        self.client.force_authenticate(user=self.trainer2)
        url = reverse('trainer-assessment-results', kwargs={'assessment_id': self.published_quiz.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_22_admin_can_manage_and_view_all_assessments_and_results(self):
        """Admin can access trainer management and results endpoints for any course."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('trainer-assessment-results', kwargs={'assessment_id': self.published_quiz.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
