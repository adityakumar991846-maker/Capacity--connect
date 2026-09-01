"""
Django admin configuration for the courses app.
"""

from django.contrib import admin
from .models import Course, Subject


class SubjectInline(admin.TabularInline):
    """Inline subject editing within course admin."""
    model = Subject
    extra = 1
    ordering = ('order',)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Admin configuration for Course model."""
    list_display = (
        'title',
        'trainer',
        'category',
        'level',
        'status',
        'duration_hours',
        'created_at',
    )
    list_filter = ('status', 'level', 'category')
    search_fields = ('title', 'description', 'trainer__username')
    inlines = [SubjectInline]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    """Admin configuration for Subject model."""
    list_display = ('title', 'course', 'order', 'created_at')
    list_filter = ('course',)
    search_fields = ('title', 'description', 'course__title')
