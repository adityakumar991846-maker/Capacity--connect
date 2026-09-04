"""
Serializers for the certificates module.
"""

from rest_framework import serializers
from .models import Certificate


class CertificateDetailSerializer(serializers.ModelSerializer):
    """Detailed certificate serializer for printable rendering."""
    course_id = serializers.IntegerField(source='course.id', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_category = serializers.CharField(source='course.category', read_only=True)
    trainer_name = serializers.SerializerMethodField()
    trainee_name = serializers.SerializerMethodField()
    trainee_username = serializers.CharField(source='trainee.username', read_only=True)
    duration_hours = serializers.IntegerField(source='course.duration_hours', read_only=True)
    honors_tier = serializers.CharField(read_only=True)

    class Meta:
        model = Certificate
        fields = [
            'id',
            'certificate_code',
            'verification_hash',
            'course_id',
            'course_title',
            'course_category',
            'duration_hours',
            'trainer_name',
            'trainee_name',
            'trainee_username',
            'final_grade_percentage',
            'honors_tier',
            'issued_at',
            'is_revoked',
            'revoked_at',
            'revocation_reason',
        ]

    def get_trainer_name(self, obj):
        if obj.course.trainer:
            full = f'{obj.course.trainer.first_name} {obj.course.trainer.last_name}'.strip()
            return full or obj.course.trainer.username
        return 'Capacity Connect Instructor'

    def get_trainee_name(self, obj):
        full = f'{obj.trainee.first_name} {obj.trainee.last_name}'.strip()
        return full or obj.trainee.username


class CertificateListSerializer(serializers.ModelSerializer):
    """List summary serializer for trainee certificates gallery."""
    course_id = serializers.IntegerField(source='course.id', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_category = serializers.CharField(source='course.category', read_only=True)
    duration_hours = serializers.IntegerField(source='course.duration_hours', read_only=True)
    trainer_name = serializers.SerializerMethodField()
    honors_tier = serializers.CharField(read_only=True)

    class Meta:
        model = Certificate
        fields = [
            'id',
            'certificate_code',
            'course_id',
            'course_title',
            'course_category',
            'duration_hours',
            'trainer_name',
            'final_grade_percentage',
            'honors_tier',
            'issued_at',
            'is_revoked',
        ]

    def get_trainer_name(self, obj):
        if obj.course.trainer:
            full = f'{obj.course.trainer.first_name} {obj.course.trainer.last_name}'.strip()
            return full or obj.course.trainer.username
        return 'Capacity Connect Instructor'


class CertificatePublicVerifySerializer(serializers.ModelSerializer):
    """
    Sanitized public verification serializer.
    STRICTLY omits trainee email, passwords, and private internal database IDs.
    """
    status = serializers.SerializerMethodField()
    trainee_name = serializers.SerializerMethodField()
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_category = serializers.CharField(source='course.category', read_only=True)
    trainer_name = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = [
            'certificate_code',
            'status',
            'trainee_name',
            'course_title',
            'course_category',
            'trainer_name',
            'final_grade_percentage',
            'issued_at',
            'is_revoked',
            'revoked_at',
            'revocation_reason',
        ]

    def get_status(self, obj):
        return 'REVOKED' if obj.is_revoked else 'VALID'

    def get_trainee_name(self, obj):
        full = f'{obj.trainee.first_name} {obj.trainee.last_name}'.strip()
        return full or obj.trainee.username

    def get_trainer_name(self, obj):
        if obj.course.trainer:
            full = f'{obj.course.trainer.first_name} {obj.course.trainer.last_name}'.strip()
            return full or obj.course.trainer.username
        return 'Capacity Connect Instructor'


class CertificateRevokeSerializer(serializers.Serializer):
    """Serializer for admin certificate revocation."""
    reason = serializers.CharField(required=True, allow_blank=False, max_length=500)


class CertificateTrainerRosterSerializer(serializers.ModelSerializer):
    """Trainer / Admin roster serializer for issued course certificates."""
    trainee_id = serializers.IntegerField(source='trainee.id', read_only=True)
    trainee_username = serializers.CharField(source='trainee.username', read_only=True)
    trainee_email = serializers.EmailField(source='trainee.email', read_only=True)

    class Meta:
        model = Certificate
        fields = [
            'id',
            'certificate_code',
            'trainee_id',
            'trainee_username',
            'trainee_email',
            'final_grade_percentage',
            'issued_at',
            'is_revoked',
            'revoked_at',
            'revocation_reason',
        ]


class AdminCertificateListSerializer(serializers.ModelSerializer):
    """Admin platform-wide certificate list serializer."""
    trainee_username = serializers.CharField(source='trainee.username', read_only=True)
    trainee_email = serializers.EmailField(source='trainee.email', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_id = serializers.IntegerField(source='course.id', read_only=True)

    class Meta:
        model = Certificate
        fields = [
            'id',
            'certificate_code',
            'trainee_username',
            'trainee_email',
            'course_title',
            'course_id',
            'final_grade_percentage',
            'issued_at',
            'is_revoked',
            'revoked_at',
            'revocation_reason',
        ]


class TraineeCertificateSummarySerializer(serializers.Serializer):
    """Aggregated portfolio statistics for a trainee."""
    total_certificates = serializers.IntegerField()
    cumulative_grade_average = serializers.FloatField()
    total_certified_hours = serializers.IntegerField()
    categories_mastered = serializers.ListField(child=serializers.CharField())
    distinctions_count = serializers.IntegerField()


class AcademicTranscriptItemSerializer(serializers.Serializer):
    """Individual course record in official academic transcript."""
    course_id = serializers.IntegerField()
    course_title = serializers.CharField()
    category = serializers.CharField()
    level = serializers.CharField()
    duration_hours = serializers.IntegerField()
    trainer_name = serializers.CharField()
    completion_date = serializers.DateTimeField()
    final_grade = serializers.FloatField()
    honors_tier = serializers.CharField()
    certificate_code = serializers.CharField()
    is_valid = serializers.BooleanField()


class AcademicTranscriptSerializer(serializers.Serializer):
    """Full official student academic transcript document."""
    student_id = serializers.IntegerField()
    student_name = serializers.CharField()
    student_email = serializers.EmailField()
    generated_at = serializers.DateTimeField()
    total_courses_completed = serializers.IntegerField()
    cumulative_grade_average = serializers.FloatField()
    total_hours_completed = serializers.IntegerField()
    records = AcademicTranscriptItemSerializer(many=True)
