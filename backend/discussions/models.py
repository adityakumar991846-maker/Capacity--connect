from django.contrib.auth.models import User
from django.db import models


class ThreadType(models.TextChoices):
    QUESTION = 'QUESTION', 'Question'
    DISCUSSION = 'DISCUSSION', 'Discussion'
    ANNOUNCEMENT = 'ANNOUNCEMENT', 'Announcement'


class DiscussionThread(models.Model):
    """
    Discussion thread within a course, optionally linked to a specific Subject.
    """
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='discussion_threads',
    )
    subject = models.ForeignKey(
        'courses.Subject',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='discussion_threads',
        help_text='Optional curriculum module/subject this discussion pertains to',
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='discussion_threads',
    )
    thread_type = models.CharField(
        max_length=20,
        choices=ThreadType.choices,
        default=ThreadType.QUESTION,
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    is_pinned = models.BooleanField(
        default=False,
        help_text='Pinned threads always appear at the top of the course forum',
    )
    is_resolved = models.BooleanField(
        default=False,
        help_text='Indicates question has been answered/resolved',
    )
    is_locked = models.BooleanField(
        default=False,
        help_text='Locked threads do not allow additional replies',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f"[{self.thread_type}] {self.title} ({self.course.title})"


class DiscussionReply(models.Model):
    """
    Reply to a discussion thread.
    """
    thread = models.ForeignKey(
        DiscussionThread,
        on_delete=models.CASCADE,
        related_name='replies',
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='discussion_replies',
    )
    content = models.TextField()
    is_instructor_endorsed = models.BooleanField(
        default=False,
        help_text='Endorsed by the course trainer as an official solution',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_instructor_endorsed', 'created_at']

    def __str__(self):
        return f"Reply by {self.author.username} on {self.thread.title}"


class ThreadUpvote(models.Model):
    """
    Tracks trainee/trainer upvotes on a discussion thread.
    """
    thread = models.ForeignKey(
        DiscussionThread,
        on_delete=models.CASCADE,
        related_name='upvotes',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='thread_upvotes',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('thread', 'user')

    def __str__(self):
        return f"{self.user.username} upvoted {self.thread.id}"


class DiscussionNotification(models.Model):
    """
    Lightweight in-app notification for new replies and announcements.
    """
    class NotificationType(models.TextChoices):
        NEW_REPLY = 'NEW_REPLY', 'New Reply'
        NEW_ANNOUNCEMENT = 'NEW_ANNOUNCEMENT', 'New Course Announcement'

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='discussion_notifications',
    )
    thread = models.ForeignKey(
        DiscussionThread,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title} (read={self.is_read})"
