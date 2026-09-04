"""
Course management models for Capacity Connect.

Defines Course and Subject models with status workflow,
trainer ownership, and ordered subjects/modules.
"""

from django.conf import settings
from django.db import models


class CourseLevel(models.TextChoices):
    """Difficulty level of a course."""
    BEGINNER = 'BEGINNER', 'Beginner'
    INTERMEDIATE = 'INTERMEDIATE', 'Intermediate'
    ADVANCED = 'ADVANCED', 'Advanced'


class CourseStatus(models.TextChoices):
    """
    Publication status of a course.

    - DRAFT: trainer is preparing the course.
    - PUBLISHED: only Admin can publish/approve the course.
    - ARCHIVED: course is no longer active.
    """
    DRAFT = 'DRAFT', 'Draft'
    PUBLISHED = 'PUBLISHED', 'Published'
    ARCHIVED = 'ARCHIVED', 'Archived'
    REJECTED = 'REJECTED', 'Rejected'


class Course(models.Model):
    """
    A training course created and owned by a trainer.

    Trainers can create/edit their own courses but cannot publish them.
    Only admins can set the status to PUBLISHED.
    """
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=100)
    level = models.CharField(
        max_length=20,
        choices=CourseLevel.choices,
    )
    duration_hours = models.PositiveIntegerField(
        help_text='Estimated duration in hours',
    )
    status = models.CharField(
        max_length=20,
        choices=CourseStatus.choices,
        default=CourseStatus.DRAFT,
    )
    requirements = models.TextField(
        blank=True,
        default='',
        help_text='Prerequisites or requirements',
    )
    learning_objectives = models.TextField(
        blank=True,
        default='',
        help_text='What students will learn',
    )
    rejection_reason = models.TextField(
        blank=True,
        default='',
        help_text='Admin feedback when a course submission is rejected',
    )
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='courses',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Course'
        verbose_name_plural = 'Courses'

    def __str__(self):
        return f'{self.title} ({self.get_status_display()})'


class Subject(models.Model):
    """
    A subject or module within a course.

    Subjects are ordered within their parent course via the ``order`` field.
    Each (course, order) pair must be unique.
    """
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    order = models.PositiveIntegerField(default=0)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='subjects',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        unique_together = [('course', 'order')]
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'

    def __str__(self):
        return f'{self.order}. {self.title}'
