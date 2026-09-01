"""
Models for course enrollment and trainee learning progress.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class EnrollmentStatus(models.TextChoices):
    """Status of a trainee's enrollment in a course."""
    ENROLLED = 'ENROLLED', 'Enrolled'
    COMPLETED = 'COMPLETED', 'Completed'
    DROPPED = 'DROPPED', 'Dropped'


class Enrollment(models.Model):
    """
    Represents a trainee's enrollment in a specific course.
    """
    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    status = models.CharField(
        max_length=20,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.ENROLLED,
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_accessed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-enrolled_at']
        unique_together = [('trainee', 'course')]
        verbose_name = 'Enrollment'
        verbose_name_plural = 'Enrollments'

    def __str__(self):
        return f'{self.trainee.username} - {self.course.title} ({self.get_status_display()})'

    @property
    def progress_percentage(self) -> float:
        """
        Calculate learning progress percentage:
        completed subjects / total subjects * 100
        - No subjects = 0%
        - All subjects completed = 100%
        - Guaranteed to stay between 0 and 100.
        """
        total_subjects = self.course.subjects.count()
        if total_subjects == 0:
            return 0.0

        # Count completed subject progress records for this enrollment and course
        completed_count = self.subject_progresses.filter(
            completed=True,
            subject__course=self.course,
        ).count()

        percentage = round((completed_count / total_subjects) * 100.0, 2)
        return max(0.0, min(100.0, percentage))

    def update_completion_status(self, save=True):
        """
        Recalculates status based on subject completion:
        - If all subjects are completed (and total > 0), set status to COMPLETED and record completed_at.
        - If any subject is incomplete and status was COMPLETED, revert status back to ENROLLED and clear completed_at.
        - If enrollment is DROPPED, status remains DROPPED.
        """
        if self.status == EnrollmentStatus.DROPPED:
            return

        total_subjects = self.course.subjects.count()
        if total_subjects == 0:
            if self.status == EnrollmentStatus.COMPLETED:
                self.status = EnrollmentStatus.ENROLLED
                self.completed_at = None
                if save:
                    self.save(update_fields=['status', 'completed_at', 'last_accessed_at'])
            return

        completed_count = self.subject_progresses.filter(
            completed=True,
            subject__course=self.course,
        ).count()

        if completed_count == total_subjects:
            self.status = EnrollmentStatus.COMPLETED
            if not self.completed_at:
                self.completed_at = timezone.now()
        else:
            if self.status == EnrollmentStatus.COMPLETED:
                self.status = EnrollmentStatus.ENROLLED
                self.completed_at = None

        if save:
            self.save(update_fields=['status', 'completed_at', 'last_accessed_at'])


class SubjectProgress(models.Model):
    """
    Tracks completion status for a specific subject/module within an enrollment.
    """
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='subject_progresses',
    )
    subject = models.ForeignKey(
        'courses.Subject',
        on_delete=models.CASCADE,
        related_name='progress_records',
    )
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['subject__order', 'id']
        unique_together = [('enrollment', 'subject')]
        verbose_name = 'Subject Progress'
        verbose_name_plural = 'Subject Progresses'

    def __str__(self):
        status_str = 'Done' if self.completed else 'Pending'
        return f'{self.enrollment.trainee.username} - {self.subject.title} [{status_str}]'

    def mark_completed(self, save=True):
        """Mark subject completed and update parent enrollment."""
        self.completed = True
        self.completed_at = timezone.now()
        if save:
            self.save(update_fields=['completed', 'completed_at'])
            self.enrollment.update_completion_status(save=True)

    def mark_incomplete(self, save=True):
        """Mark subject incomplete and update parent enrollment."""
        self.completed = False
        self.completed_at = None
        if save:
            self.save(update_fields=['completed', 'completed_at'])
            self.enrollment.update_completion_status(save=True)
