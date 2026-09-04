"""
Serializers for the courses module.

Handles serialization and validation for Course and Subject models,
including role-based field permissions (e.g. status publishing restriction).
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from core.models import Role
from .models import Course, CourseLevel, CourseStatus, Subject

User = get_user_model()


class SubjectSerializer(serializers.ModelSerializer):
    """Serializer for Course subjects/modules."""

    class Meta:
        model = Subject
        fields = [
            'id',
            'course',
            'title',
            'description',
            'order',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'course', 'created_at', 'updated_at']

    def validate_order(self, value):
        if value < 0:
            raise serializers.ValidationError('Order must be a non-negative integer.')
        return value

    def validate(self, attrs):
        course = self.context.get('course') or (self.instance.course if self.instance else None)
        order = attrs.get('order', self.instance.order if self.instance else None)
        if course and order is not None:
            qs = Subject.objects.filter(course=course, order=order)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'order': f'A subject with order {order} already exists in this course.'}
                )
        return attrs


class CourseTrainerSerializer(serializers.ModelSerializer):
    """Compact trainer info for course representations."""

    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class CourseListSerializer(serializers.ModelSerializer):
    """Compact representation of a course for list views."""

    trainer = CourseTrainerSerializer(read_only=True)

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'category',
            'level',
            'status',
            'duration_hours',
            'trainer',
            'created_at',
            'updated_at',
        ]


class CourseDetailSerializer(serializers.ModelSerializer):
    """Detailed representation of a course including nested subjects."""

    trainer = CourseTrainerSerializer(read_only=True)
    subjects = SubjectSerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'description',
            'category',
            'level',
            'status',
            'duration_hours',
            'requirements',
            'learning_objectives',
            'trainer',
            'subjects',
            'created_at',
            'updated_at',
        ]


class CourseCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating courses.

    Enforces business rules:
    - Only Admins can set status to PUBLISHED.
    - Trainers can only set status to DRAFT or ARCHIVED.
    - Admins can assign any trainer (with TRAINER role).
    - Trainers automatically have their course assigned to themselves.
    """

    trainer = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
    )

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'description',
            'category',
            'level',
            'status',
            'duration_hours',
            'requirements',
            'learning_objectives',
            'trainer',
        ]
        read_only_fields = ['id']

    def validate_duration_hours(self, value):
        if value <= 0:
            raise serializers.ValidationError('Duration in hours must be greater than 0.')
        return value

    def validate_trainer(self, value):
        if value and (not hasattr(value, 'profile') or value.profile.role != Role.TRAINER):
            raise serializers.ValidationError('Assigned user must have the TRAINER role.')
        return value

    def validate_status(self, value):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        is_admin = (
            user
            and hasattr(user, 'profile')
            and user.profile.role == Role.ADMIN
        )

        if value == CourseStatus.PUBLISHED and not is_admin:
            raise PermissionDenied(
                'Only administrators can publish courses.'
            )
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        is_admin = (
            user
            and hasattr(user, 'profile')
            and user.profile.role == Role.ADMIN
        )

        # For non-admin, force trainer to current user
        if not is_admin and user:
            attrs['trainer'] = user
        elif is_admin and 'trainer' not in attrs and not self.instance:
            # Default trainer to current admin if not explicitly set
            attrs['trainer'] = user

        return attrs


class TrainerDashboardStatsSerializer(serializers.Serializer):
    """Serializer for aggregate trainer dashboard metrics."""
    total_courses = serializers.IntegerField()
    published_courses = serializers.IntegerField()
    draft_courses = serializers.IntegerField()
    archived_courses = serializers.IntegerField()
    total_enrollments = serializers.IntegerField()
    completed_enrollments = serializers.IntegerField()
    average_progress = serializers.FloatField()


class TrainerCourseItemSerializer(serializers.ModelSerializer):
    """Serializer for courses authored by the trainer with metrics."""
    subject_count = serializers.SerializerMethodField()
    enrollment_count = serializers.SerializerMethodField()
    completed_count = serializers.SerializerMethodField()
    average_progress = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'description',
            'category',
            'level',
            'status',
            'duration_hours',
            'requirements',
            'learning_objectives',
            'subject_count',
            'enrollment_count',
            'completed_count',
            'average_progress',
            'created_at',
            'updated_at',
        ]

    def get_subject_count(self, obj):
        return obj.subjects.count()

    def get_enrollment_count(self, obj):
        return obj.enrollments.count()

    def get_completed_count(self, obj):
        return obj.enrollments.filter(status='COMPLETED').count()

    def get_average_progress(self, obj):
        enrollments = list(obj.enrollments.all())
        if not enrollments:
            return 0.0
        total = sum(e.progress_percentage for e in enrollments)
        return round(total / len(enrollments), 2)


class TrainerCourseRosterItemSerializer(serializers.Serializer):
    """Serializer for enrolled trainee item in a trainer course roster."""
    enrollment_id = serializers.IntegerField()
    trainee_id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    status = serializers.CharField()
    progress_percentage = serializers.FloatField()
    enrolled_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)
    last_accessed_at = serializers.DateTimeField()
