"""
Models for the assessments and quiz engine.

Defines Assessment, Question (MCQ), AssessmentAttempt, and AssessmentAnswer models.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class AssessmentStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    PUBLISHED = 'PUBLISHED', 'Published'
    ARCHIVED = 'ARCHIVED', 'Archived'


class QuestionOptionChoice(models.TextChoices):
    A = 'A', 'Option A'
    B = 'B', 'Option B'
    C = 'C', 'Option C'
    D = 'D', 'Option D'


class Assessment(models.Model):
    """
    An assessment or quiz associated with a course or an individual subject/module.
    """
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='assessments',
    )
    subject = models.ForeignKey(
        'courses.Subject',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='assessments',
        help_text='Optional subject module association.',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    passing_percentage = models.PositiveIntegerField(
        default=70,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text='Percentage required to pass (1-100)',
    )
    duration_minutes = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(1)],
        help_text='Time limit in minutes',
    )
    status = models.CharField(
        max_length=20,
        choices=AssessmentStatus.choices,
        default=AssessmentStatus.DRAFT,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_assessments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Assessment'
        verbose_name_plural = 'Assessments'

    def __str__(self):
        return f'{self.title} ({self.course.title})'

    @property
    def total_marks(self) -> int:
        """Calculate total marks from all questions."""
        return sum(q.marks for q in self.questions.all())

    @property
    def question_count(self) -> int:
        """Count total questions."""
        return self.questions.count()


class Question(models.Model):
    """
    A multiple-choice question (MCQ) within an assessment.
    """
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='questions',
    )
    question_text = models.TextField()
    option_a = models.TextField()
    option_b = models.TextField()
    option_c = models.TextField()
    option_d = models.TextField()
    correct_answer = models.CharField(
        max_length=1,
        choices=QuestionOptionChoice.choices,
    )
    explanation = models.TextField(
        blank=True,
        default='',
        help_text='Explanation revealed to trainees only after submission.',
    )
    marks = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Question'
        verbose_name_plural = 'Questions'

    def __str__(self):
        return f'Q{self.order}: {self.question_text[:50]}'


class AssessmentAttempt(models.Model):
    """
    Records a trainee's attempt on a specific assessment.
    Grading is calculated entirely on the server.
    """
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='attempts',
    )
    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assessment_attempts',
    )
    score = models.PositiveIntegerField(default=0)
    total_marks = models.PositiveIntegerField(default=0)
    percentage = models.FloatField(default=0.0)
    passed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Assessment Attempt'
        verbose_name_plural = 'Assessment Attempts'

    def __str__(self):
        status_str = 'PASS' if self.passed else 'FAIL'
        return f'{self.trainee.username} - {self.assessment.title} [{status_str} {self.percentage}%]'


class AssessmentAnswer(models.Model):
    """
    Records the trainee's selected answer for an individual question in an attempt.
    """
    attempt = models.ForeignKey(
        AssessmentAttempt,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
    )
    selected_option = models.CharField(
        max_length=1,
        choices=QuestionOptionChoice.choices,
        null=True,
        blank=True,
    )
    is_correct = models.BooleanField(default=False)
    marks_obtained = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['question__order', 'id']
        unique_together = [('attempt', 'question')]
        verbose_name = 'Assessment Answer'
        verbose_name_plural = 'Assessment Answers'

    def __str__(self):
        return f'{self.attempt.trainee.username} - Q{self.question.order}: {self.selected_option} ({"Correct" if self.is_correct else "Incorrect"})'
