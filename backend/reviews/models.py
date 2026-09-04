"""
Models for Course Reviews and Ratings (Step 14).
"""

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class CourseReview(models.Model):
    """
    Verified review and 1-5 star rating left by an enrolled trainee.
    """
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='course_reviews',
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Rating score between 1 and 5 stars',
    )
    title = models.CharField(
        max_length=150,
        blank=True,
        default='',
        help_text='Short headline summarizing the review',
    )
    comment = models.TextField(
        help_text='Detailed student review feedback and commentary',
    )
    is_visible = models.BooleanField(
        default=True,
        help_text='Admin moderation visibility flag',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['course', 'trainee'],
                name='unique_trainee_course_review',
            )
        ]
        verbose_name = 'Course Review'
        verbose_name_plural = 'Course Reviews'

    def __str__(self):
        return f'{self.trainee.username} - {self.course.title} ({self.rating}?)'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Automatically update the cached course rating stats
        if hasattr(self.course, 'update_rating_stats'):
            self.course.update_rating_stats()

    def delete(self, *args, **kwargs):
        course = self.course
        super().delete(*args, **kwargs)
        if hasattr(course, 'update_rating_stats'):
            course.update_rating_stats()
