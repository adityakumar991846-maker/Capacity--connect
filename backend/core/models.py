"""
Core models for Capacity Connect.

Defines the role-based UserProfile that extends Django's built-in User model.
"""

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Role(models.TextChoices):
    """Application-level roles for Capacity Connect users."""
    TRAINEE = 'TRAINEE', 'Trainee'
    TRAINER = 'TRAINER', 'Trainer'
    ADMIN = 'ADMIN', 'Admin'


class UserProfile(models.Model):
    """
    One-to-one extension of Django's User model.

    Every user in the system has exactly one UserProfile that stores their
    application role (Trainee, Trainer, or Admin).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
    )

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_admin_profile_for_superuser(sender, instance, created, **kwargs):
    """
    Automatically create an ADMIN profile when a superuser is created
    (e.g. via ``createsuperuser``) and doesn't already have a profile.
    """
    if created and instance.is_superuser:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={'role': Role.ADMIN},
        )
