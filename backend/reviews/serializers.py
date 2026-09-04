"""
Serializers for Course Reviews (Step 14).
"""

from rest_framework import serializers
from .models import CourseReview


class CourseReviewListSerializer(serializers.ModelSerializer):
    """
    Public serializer for visible course reviews.
    """
    trainee_username = serializers.CharField(source='trainee.username', read_only=True)
    trainee_id = serializers.IntegerField(source='trainee.id', read_only=True)

    class Meta:
        model = CourseReview
        fields = [
            'id',
            'course',
            'trainee_id',
            'trainee_username',
            'rating',
            'title',
            'comment',
            'is_visible',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'course', 'trainee_id', 'trainee_username', 'is_visible', 'created_at', 'updated_at']


class CourseReviewCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating or updating a course review.
    """
    class Meta:
        model = CourseReview
        fields = ['id', 'rating', 'title', 'comment']

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('Rating must be an integer between 1 and 5.')
        return value

    def validate_comment(self, value):
        cleaned = value.strip()
        if len(cleaned) < 5:
            raise serializers.ValidationError('Review comment must be at least 5 characters.')
        return cleaned


class TrainerFeedbackItemSerializer(serializers.ModelSerializer):
    """
    Serializer for trainer dashboard review feedback.
    """
    trainee_username = serializers.CharField(source='trainee.username', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_id = serializers.IntegerField(source='course.id', read_only=True)

    class Meta:
        model = CourseReview
        fields = [
            'id',
            'course_id',
            'course_title',
            'trainee_username',
            'rating',
            'title',
            'comment',
            'created_at',
        ]
