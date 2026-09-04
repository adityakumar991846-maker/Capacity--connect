"""
Serializers for discussions, replies, upvotes, and notifications.
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from core.models import Role
from courses.models import Course, Subject
from .models import (
    DiscussionThread,
    DiscussionReply,
    ThreadType,
    ThreadUpvote,
    DiscussionNotification,
)


class DiscussionReplySerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    author_role = serializers.SerializerMethodField()
    is_course_trainer = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionReply
        fields = [
            'id',
            'thread',
            'author',
            'author_username',
            'author_role',
            'is_course_trainer',
            'content',
            'is_instructor_endorsed',
            'can_edit',
            'can_delete',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'thread', 'author', 'created_at', 'updated_at']

    def get_author_role(self, obj):
        if hasattr(obj.author, 'profile'):
            return obj.author.profile.role
        return Role.TRAINEE

    def get_is_course_trainer(self, obj):
        return obj.author == obj.thread.course.trainer

    def get_can_edit(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.author == request.user

    def get_can_delete(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN:
            return True
        return obj.author == request.user


class DiscussionReplyCreateSerializer(serializers.ModelSerializer):
    content = serializers.CharField(min_length=2, trim_whitespace=True)

    class Meta:
        model = DiscussionReply
        fields = ['content']


class DiscussionThreadListSerializer(serializers.ModelSerializer):
    subject_title = serializers.CharField(source='subject.title', read_only=True, allow_null=True)
    author_username = serializers.CharField(source='author.username', read_only=True)
    author_role = serializers.SerializerMethodField()
    is_course_trainer = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()
    upvotes_count = serializers.SerializerMethodField()
    has_upvoted = serializers.SerializerMethodField()
    has_instructor_reply = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionThread
        fields = [
            'id',
            'course',
            'subject',
            'subject_title',
            'author',
            'author_username',
            'author_role',
            'is_course_trainer',
            'thread_type',
            'title',
            'is_pinned',
            'is_resolved',
            'is_locked',
            'replies_count',
            'upvotes_count',
            'has_upvoted',
            'has_instructor_reply',
            'created_at',
            'updated_at',
        ]

    def get_author_role(self, obj):
        if hasattr(obj.author, 'profile'):
            return obj.author.profile.role
        return Role.TRAINEE

    def get_is_course_trainer(self, obj):
        return obj.author == obj.course.trainer

    def get_replies_count(self, obj):
        return obj.replies.count()

    def get_upvotes_count(self, obj):
        return obj.upvotes.count()

    def get_has_upvoted(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.upvotes.filter(user=request.user).exists()

    def get_has_instructor_reply(self, obj):
        return obj.replies.filter(author=obj.course.trainer).exists()


class DiscussionThreadDetailSerializer(DiscussionThreadListSerializer):
    replies = DiscussionReplySerializer(many=True, read_only=True)
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    can_resolve = serializers.SerializerMethodField()
    can_pin = serializers.SerializerMethodField()
    can_endorse = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionThread
        fields = DiscussionThreadListSerializer.Meta.fields + [
            'content',
            'replies',
            'can_edit',
            'can_delete',
            'can_resolve',
            'can_pin',
            'can_endorse',
        ]

    def get_can_edit(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.author == request.user

    def get_can_delete(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN:
            return True
        return obj.author == request.user

    def get_can_resolve(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN:
            return True
        return obj.author == request.user or obj.course.trainer == request.user

    def get_can_pin(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN:
            return True
        return obj.course.trainer == request.user

    def get_can_endorse(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN:
            return True
        return obj.course.trainer == request.user


class ThreadCreateSerializer(serializers.ModelSerializer):
    subject_id = serializers.IntegerField(required=False, allow_null=True)
    title = serializers.CharField(min_length=5, max_length=255, trim_whitespace=True)
    content = serializers.CharField(min_length=10, trim_whitespace=True)

    class Meta:
        model = DiscussionThread
        fields = ['title', 'content', 'thread_type', 'subject_id']

    def validate(self, data):
        request = self.context.get('request')
        course = self.context.get('course')

        # Check thread_type permissions
        thread_type = data.get('thread_type', ThreadType.QUESTION)
        if thread_type == ThreadType.ANNOUNCEMENT:
            is_admin = hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN
            is_trainer = course.trainer == request.user
            if not (is_admin or is_trainer):
                raise serializers.ValidationError(
                    {"thread_type": "Only course trainers and admins can create announcements."}
                )

        # Check subject belongs to course if provided
        subject_id = data.get('subject_id')
        if subject_id:
            if not Subject.objects.filter(id=subject_id, course=course).exists():
                raise serializers.ValidationError(
                    {"subject_id": "The specified subject does not belong to this course."}
                )

        return data


class TrainerDiscussionInboxItemSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_id = serializers.IntegerField(source='course.id', read_only=True)
    subject_title = serializers.CharField(source='subject.title', read_only=True, allow_null=True)
    author_username = serializers.CharField(source='author.username', read_only=True)
    replies_count = serializers.SerializerMethodField()
    has_instructor_reply = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionThread
        fields = [
            'id',
            'course_id',
            'course_title',
            'subject_id',
            'subject_title',
            'author_username',
            'thread_type',
            'title',
            'content',
            'is_resolved',
            'is_pinned',
            'replies_count',
            'has_instructor_reply',
            'created_at',
        ]

    def get_replies_count(self, obj):
        return obj.replies.count()

    def get_has_instructor_reply(self, obj):
        return obj.replies.filter(author=obj.course.trainer).exists()


class DiscussionNotificationSerializer(serializers.ModelSerializer):
    thread_title = serializers.CharField(source='thread.title', read_only=True)
    course_id = serializers.IntegerField(source='thread.course.id', read_only=True)
    course_title = serializers.CharField(source='thread.course.title', read_only=True)

    class Meta:
        model = DiscussionNotification
        fields = [
            'id',
            'thread_id',
            'thread_title',
            'course_id',
            'course_title',
            'notification_type',
            'title',
            'message',
            'is_read',
            'created_at',
        ]
        read_only_fields = fields
