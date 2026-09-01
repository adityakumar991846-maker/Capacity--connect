"""
Django admin configuration for the enrollments app.
"""

from django.contrib import admin
from .models import Enrollment, SubjectProgress


class SubjectProgressInline(admin.TabularInline):
    """Inline view of subject completion records within an enrollment."""
    model = SubjectProgress
    extra = 0
    readonly_fields = ('subject', 'completed', 'completed_at')
    can_delete = False


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    """Admin configuration for Enrollment model."""
    list_display = (
        'trainee',
        'course',
        'status',
        'progress_percentage',
        'enrolled_at',
        'completed_at',
    )
    list_filter = ('status', 'enrolled_at', 'completed_at')
    search_fields = ('trainee__username', 'trainee__email', 'course__title')
    inlines = [SubjectProgressInline]


@admin.register(SubjectProgress)
class SubjectProgressAdmin(admin.ModelAdmin):
    """Admin configuration for SubjectProgress model."""
    list_display = ('enrollment', 'subject', 'completed', 'completed_at')
    list_filter = ('completed',)
    search_fields = ('enrollment__trainee__username', 'subject__title', 'enrollment__course__title')
