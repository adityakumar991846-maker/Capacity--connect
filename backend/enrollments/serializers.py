"""
Serializers for course enrollments and trainee learning progress.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from core.models import Role
from courses.models import Course, CourseStatus, Subject
from .models import Enrollment, EnrollmentStatus, SubjectProgress

User = get_user_model()


class SubjectProgressSerializer(serializers.ModelSerializer):
    """Serializer for subject completion progress."""
    subject_id = serializers.ReadOnlyField(source='subject.id')
    subject_title = serializers.ReadOnlyField(source='subject.title')
    subject_order = serializers.ReadOnlyField(source='subject.order')

    class Meta:
        model = SubjectProgress
        fields = [
            'id',
            'subject_id',
            'subject_title',
            'subject_order',
            'completed',
            'completed_at',
        ]
        read_only_fields = ['id', 'subject_id', 'subject_title', 'subject_order', 'completed_at']


class EnrollmentTraineeSerializer(serializers.ModelSerializer):
    """Compact trainee representation."""
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class EnrollmentCourseSerializer(serializers.ModelSerializer):
    """Compact course representation for enrollments."""
    trainer_username = serializers.ReadOnlyField(source='trainer.username')

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'category',
            'level',
            'duration_hours',
            'status',
            'trainer_username',
        ]


class EnrollmentListSerializer(serializers.ModelSerializer):
    """Compact enrollment representation with calculated progress percentage."""
    trainee = EnrollmentTraineeSerializer(read_only=True)
    course = EnrollmentCourseSerializer(read_only=True)
    progress_percentage = serializers.ReadOnlyField()

    class Meta:
        model = Enrollment
        fields = [
            'id',
            'trainee',
            'course',
            'status',
            'progress_percentage',
            'enrolled_at',
            'completed_at',
            'last_accessed_at',
        ]


class EnrollmentDetailSerializer(serializers.ModelSerializer):
    """Detailed enrollment record including nested per-subject progress."""
    trainee = EnrollmentTraineeSerializer(read_only=True)
    course = EnrollmentCourseSerializer(read_only=True)
    progress_percentage = serializers.ReadOnlyField()
    subject_progresses = SubjectProgressSerializer(many=True, read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            'id',
            'trainee',
            'course',
            'status',
            'progress_percentage',
            'subject_progresses',
            'enrolled_at',
            'completed_at',
            'last_accessed_at',
        ]


class EnrollmentCreateSerializer(serializers.Serializer):
    """
    Handles trainee course enrollment.

    Validates:
    - User role must be TRAINEE.
    - Course must exist and have status=PUBLISHED.
    - User cannot enroll if already enrolled in the same course.
    """
    course_id = serializers.IntegerField(write_only=True)

    def validate_course_id(self, value):
        try:
            course = Course.objects.get(pk=value)
        except Course.DoesNotExist:
            raise serializers.ValidationError('Course not found.')

        if course.status != CourseStatus.PUBLISHED:
            raise serializers.ValidationError(
                f'Cannot enroll in a course with status "{course.get_status_display()}". Only PUBLISHED courses accept enrollments.'
            )
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        if not user or not hasattr(user, 'profile') or user.profile.role != Role.TRAINEE:
            raise serializers.ValidationError('Only trainees can enroll in courses.')

        course_id = attrs['course_id']
        if Enrollment.objects.filter(trainee=user, course_id=course_id).exists():
            raise serializers.ValidationError('You are already enrolled in this course.')

        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        course = Course.objects.get(pk=validated_data['course_id'])

        enrollment = Enrollment.objects.create(
            trainee=user,
            course=course,
            status=EnrollmentStatus.ENROLLED,
        )

        # Initialize SubjectProgress for all existing subjects in the course
        subjects = course.subjects.all().order_by('order')
        for subject in subjects:
            SubjectProgress.objects.create(
                enrollment=enrollment,
                subject=subject,
                completed=False,
            )

        return enrollment
