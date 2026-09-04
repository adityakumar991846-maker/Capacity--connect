from django.contrib.auth.models import User
from django.db import models


class SubmissionType(models.TextChoices):
    LINK = 'LINK', 'External Link / URL'
    FILE = 'FILE', 'File Upload / Document'
    TEXT = 'TEXT', 'Text Response / Code'
    HYBRID = 'HYBRID', 'Link & Written Report'


class SubmissionStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    SUBMITTED = 'SUBMITTED', 'Submitted'
    UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
    GRADED = 'GRADED', 'Graded'
    RESUBMISSION_REQUESTED = 'RESUBMISSION_REQUESTED', 'Resubmission Requested'


class Assignment(models.Model):
    """
    Practical project or assignment task within a course or specific subject module.
    """
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='assignments',
    )
    subject = models.ForeignKey(
        'courses.Subject',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments',
        help_text='Optional curriculum module this assignment belongs to. If null, acts as a course capstone.',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(help_text='Detailed assignment guidelines, deliverables, and rubric')
    submission_type = models.CharField(
        max_length=20,
        choices=SubmissionType.choices,
        default=SubmissionType.LINK,
    )
    max_score = models.PositiveIntegerField(default=100)
    passing_score = models.PositiveIntegerField(default=60)
    due_date = models.DateTimeField(null=True, blank=True)
    is_mandatory = models.BooleanField(
        default=True,
        help_text='If true, passing this assignment is strictly required for certificate eligibility',
    )
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['course', 'subject__order', 'created_at']

    def __str__(self):
        return f"{self.title} ({self.course.title})"


class AssignmentSubmission(models.Model):
    """
    Deliverable submitted by an enrolled trainee for an assignment.
    """
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    trainee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assignment_submissions',
    )
    enrollment = models.ForeignKey(
        'enrollments.Enrollment',
        on_delete=models.CASCADE,
        related_name='assignment_submissions',
    )
    submission_link = models.URLField(blank=True, default='')
    submission_text = models.TextField(blank=True, default='')
    submission_file = models.FileField(
        upload_to='assignments/submissions/%Y/%m/',
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=30,
        choices=SubmissionStatus.choices,
        default=SubmissionStatus.SUBMITTED,
    )
    submitted_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('assignment', 'trainee')
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Submission by {self.trainee.username} for {self.assignment.title} ({self.status})"


class SubmissionReview(models.Model):
    """
    Formal evaluation and feedback recorded by the course trainer.
    """
    submission = models.OneToOneField(
        AssignmentSubmission,
        on_delete=models.CASCADE,
        related_name='review',
    )
    reviewer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assignment_reviews',
    )
    score = models.PositiveIntegerField()
    passed = models.BooleanField(default=False)
    feedback = models.TextField(help_text='Constructive critique, commendations, or guidance on what to improve')
    reviewed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-reviewed_at']

    def __str__(self):
        return f"Review ({self.score}/{self.submission.assignment.max_score}) for {self.submission}"
