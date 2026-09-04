"""
Views for course discussions, Q&A threads, replies, and notifications.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Role
from courses.models import Course, Subject
from courses.permissions import IsTrainerOrAdmin
from enrollments.models import Enrollment, EnrollmentStatus
from .models import (
    DiscussionThread,
    DiscussionReply,
    ThreadType,
    ThreadUpvote,
    DiscussionNotification,
)
from .serializers import (
    DiscussionThreadListSerializer,
    DiscussionThreadDetailSerializer,
    ThreadCreateSerializer,
    DiscussionReplySerializer,
    DiscussionReplyCreateSerializer,
    TrainerDiscussionInboxItemSerializer,
    DiscussionNotificationSerializer,
)


def _user_has_course_access(user, course):
    """
    Checks if user is admin, course trainer, or active enrolled trainee.
    """
    if not user or not user.is_authenticated:
        return False
    if hasattr(user, 'profile') and user.profile.role == Role.ADMIN:
        return True
    if course.trainer == user:
        return True
    return Enrollment.objects.filter(
        course=course,
        trainee=user,
    ).exclude(status=EnrollmentStatus.DROPPED).exists()


class CourseDiscussionThreadListCreateView(APIView):
    """
    GET /api/discussions/courses/<course_id>/ — List discussion threads for a course.
    POST /api/discussions/courses/<course_id>/ — Create a new thread.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id)
        if not _user_has_course_access(request.user, course):
            return Response(
                {'detail': 'You must be enrolled in this course to view discussions.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        threads = DiscussionThread.objects.filter(course=course).select_related(
            'author', 'author__profile', 'subject', 'course', 'course__trainer'
        ).prefetch_related('replies', 'upvotes')

        # Filter by subject
        subject_id = request.query_params.get('subject_id')
        if subject_id:
            threads = threads.filter(subject_id=subject_id)

        # Filter by thread_type
        thread_type = request.query_params.get('type')
        if thread_type:
            threads = threads.filter(thread_type=thread_type.upper())

        # Filter by resolved status
        resolved = request.query_params.get('resolved')
        if resolved is not None:
            is_resolved = resolved.lower() in ('true', '1')
            threads = threads.filter(is_resolved=is_resolved)

        # Search query
        search = request.query_params.get('search')
        if search:
            threads = threads.filter(
                Q(title__icontains=search) | Q(content__icontains=search)
            )

        serializer = DiscussionThreadListSerializer(
            threads, many=True, context={'request': request}
        )
        return Response(serializer.data)

    def post(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id)
        if not _user_has_course_access(request.user, course):
            return Response(
                {'detail': 'You must be enrolled in this course to start a discussion.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ThreadCreateSerializer(
            data=request.data,
            context={'request': request, 'course': course},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        subject = None
        subject_id = validated_data.get('subject_id')
        if subject_id:
            subject = get_object_or_404(Subject, pk=subject_id, course=course)

        thread_type = validated_data.get('thread_type', ThreadType.QUESTION)
        is_pinned = True if thread_type == ThreadType.ANNOUNCEMENT else False

        thread = DiscussionThread.objects.create(
            course=course,
            subject=subject,
            author=request.user,
            thread_type=thread_type,
            title=validated_data['title'],
            content=validated_data['content'],
            is_pinned=is_pinned,
        )

        # If announcement, notify all active enrolled trainees
        if thread_type == ThreadType.ANNOUNCEMENT:
            enrolled_user_ids = Enrollment.objects.filter(
                course=course,
                status=EnrollmentStatus.ENROLLED,
            ).values_list('trainee_id', flat=True)

            notifications = [
                DiscussionNotification(
                    recipient_id=uid,
                    thread=thread,
                    notification_type=DiscussionNotification.NotificationType.NEW_ANNOUNCEMENT,
                    title=f"New Announcement: {course.title}",
                    message=thread.title,
                )
                for uid in enrolled_user_ids if uid != request.user.id
            ]
            if notifications:
                DiscussionNotification.objects.bulk_create(notifications)

        detail_serializer = DiscussionThreadDetailSerializer(
            thread, context={'request': request}
        )
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)


class DiscussionThreadDetailView(APIView):
    """
    GET /api/discussions/<pk>/ — Retrieve thread with all replies.
    PATCH /api/discussions/<pk>/ — Edit thread title/content (Author or Admin only).
    DELETE /api/discussions/<pk>/ — Delete thread (Author or Admin only).
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(
            DiscussionThread.objects.select_related(
                'author', 'author__profile', 'subject', 'course', 'course__trainer'
            ).prefetch_related(
                'replies', 'replies__author', 'replies__author__profile', 'upvotes'
            ),
            pk=pk,
        )

    def get(self, request, pk):
        thread = self.get_object(pk)
        if not _user_has_course_access(request.user, thread.course):
            return Response(
                {'detail': 'You must be enrolled in this course to view this discussion.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = DiscussionThreadDetailSerializer(thread, context={'request': request})
        return Response(serializer.data)

    def patch(self, request, pk):
        thread = self.get_object(pk)
        is_admin = hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN
        if thread.author != request.user and not is_admin:
            return Response(
                {'detail': 'Only the author or an admin can edit this thread.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        title = request.data.get('title', '').strip()
        content = request.data.get('content', '').strip()

        if title:
            if len(title) < 5:
                return Response(
                    {'title': 'Title must be at least 5 characters.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            thread.title = title

        if content:
            if len(content) < 10:
                return Response(
                    {'content': 'Content must be at least 10 characters.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            thread.content = content

        thread.save()
        serializer = DiscussionThreadDetailSerializer(thread, context={'request': request})
        return Response(serializer.data)

    def delete(self, request, pk):
        thread = self.get_object(pk)
        is_admin = hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN
        if thread.author != request.user and not is_admin:
            return Response(
                {'detail': 'Only the author or an admin can delete this thread.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        thread.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DiscussionThreadResolveToggleView(APIView):
    """
    POST /api/discussions/<pk>/resolve/ — Toggle resolved status (Author, Trainer, or Admin).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        thread = get_object_or_404(DiscussionThread, pk=pk)
        is_admin = hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN
        is_trainer = thread.course.trainer == request.user
        is_author = thread.author == request.user

        if not (is_admin or is_trainer or is_author):
            return Response(
                {'detail': 'Only the author, course trainer, or admin can resolve this thread.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        thread.is_resolved = not thread.is_resolved
        thread.save(update_fields=['is_resolved', 'updated_at'])
        return Response({'id': thread.id, 'is_resolved': thread.is_resolved})


class DiscussionThreadPinToggleView(APIView):
    """
    POST /api/discussions/<pk>/pin/ — Toggle pinned status (Trainer or Admin only).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        thread = get_object_or_404(DiscussionThread, pk=pk)
        is_admin = hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN
        is_trainer = thread.course.trainer == request.user

        if not (is_admin or is_trainer):
            return Response(
                {'detail': 'Only the course trainer or an admin can pin threads.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        thread.is_pinned = not thread.is_pinned
        thread.save(update_fields=['is_pinned', 'updated_at'])
        return Response({'id': thread.id, 'is_pinned': thread.is_pinned})


class DiscussionThreadUpvoteToggleView(APIView):
    """
    POST /api/discussions/<pk>/upvote/ — Toggle upvote on a discussion thread.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        thread = get_object_or_404(DiscussionThread, pk=pk)
        if not _user_has_course_access(request.user, thread.course):
            return Response(
                {'detail': 'You must be enrolled in this course to upvote threads.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        existing = ThreadUpvote.objects.filter(thread=thread, user=request.user).first()
        if existing:
            existing.delete()
            upvoted = False
        else:
            ThreadUpvote.objects.create(thread=thread, user=request.user)
            upvoted = True

        return Response({
            'thread_id': thread.id,
            'upvoted': upvoted,
            'upvotes_count': thread.upvotes.count(),
        })


class DiscussionReplyListCreateView(APIView):
    """
    POST /api/discussions/<pk>/replies/ — Post a reply to a discussion thread.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        thread = get_object_or_404(DiscussionThread.objects.select_related('course'), pk=pk)
        if not _user_has_course_access(request.user, thread.course):
            return Response(
                {'detail': 'You must be enrolled in this course to reply to this discussion.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if thread.is_locked:
            return Response(
                {'detail': 'This thread is locked and cannot receive replies.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DiscussionReplyCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        content = serializer.validated_data['content']
        reply = DiscussionReply.objects.create(
            thread=thread,
            author=request.user,
            content=content,
        )

        # Notify the thread author if someone else replies
        if thread.author != request.user:
            DiscussionNotification.objects.create(
                recipient=thread.author,
                thread=thread,
                notification_type=DiscussionNotification.NotificationType.NEW_REPLY,
                title=f"New reply on '{thread.title}'",
                message=f"{request.user.username} replied: {content[:120]}",
            )

        out_serializer = DiscussionReplySerializer(reply, context={'request': request})
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class DiscussionReplyDetailView(APIView):
    """
    PATCH /api/discussions/replies/<pk>/ — Edit reply content (Author or Admin).
    DELETE /api/discussions/replies/<pk>/ — Delete reply (Author or Admin).
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(
            DiscussionReply.objects.select_related('author', 'thread', 'thread__course'),
            pk=pk,
        )

    def patch(self, request, pk):
        reply = self.get_object(pk)
        is_admin = hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN
        if reply.author != request.user and not is_admin:
            return Response(
                {'detail': 'Only the reply author or an admin can edit this reply.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = DiscussionReplyCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        reply.content = serializer.validated_data['content']
        reply.save(update_fields=['content', 'updated_at'])
        return Response(DiscussionReplySerializer(reply, context={'request': request}).data)

    def delete(self, request, pk):
        reply = self.get_object(pk)
        is_admin = hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN
        if reply.author != request.user and not is_admin:
            return Response(
                {'detail': 'Only the reply author or an admin can delete this reply.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        reply.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DiscussionReplyEndorseToggleView(APIView):
    """
    POST /api/discussions/replies/<pk>/endorse/ — Toggle instructor endorsement (Trainer or Admin).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        reply = get_object_or_404(
            DiscussionReply.objects.select_related('thread', 'thread__course'),
            pk=pk,
        )
        is_admin = hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN
        is_trainer = reply.thread.course.trainer == request.user

        if not (is_admin or is_trainer):
            return Response(
                {'detail': 'Only the course trainer or an admin can endorse replies.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        reply.is_instructor_endorsed = not reply.is_instructor_endorsed
        reply.save(update_fields=['is_instructor_endorsed', 'updated_at'])
        return Response({
            'id': reply.id,
            'is_instructor_endorsed': reply.is_instructor_endorsed,
        })


class TrainerDiscussionInboxView(APIView):
    """
    GET /api/discussions/trainer/inbox/ — List student questions for courses authored by current trainer.
    """
    permission_classes = [IsAuthenticated, IsTrainerOrAdmin]

    def get(self, request):
        is_admin = hasattr(request.user, 'profile') and request.user.profile.role == Role.ADMIN
        if is_admin:
            threads = DiscussionThread.objects.all()
        else:
            threads = DiscussionThread.objects.filter(course__trainer=request.user)

        # Filter by course if specified
        course_id = request.query_params.get('course_id')
        if course_id:
            threads = threads.filter(course_id=course_id)

        # Filter by resolved status if specified
        resolved = request.query_params.get('resolved')
        if resolved is not None:
            is_resolved = resolved.lower() in ('true', '1')
            threads = threads.filter(is_resolved=is_resolved)

        threads = threads.select_related(
            'course', 'subject', 'author'
        ).prefetch_related('replies').order_by('-created_at')

        serializer = TrainerDiscussionInboxItemSerializer(threads, many=True)
        return Response(serializer.data)


class DiscussionNotificationListView(APIView):
    """
    GET /api/discussions/notifications/ — List current user's unread & recent notifications.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifs = DiscussionNotification.objects.filter(
            recipient=request.user
        ).select_related('thread', 'thread__course')[:30]

        unread_count = DiscussionNotification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).count()

        serializer = DiscussionNotificationSerializer(notifs, many=True)
        return Response({
            'unread_count': unread_count,
            'notifications': serializer.data,
        })


class DiscussionNotificationMarkReadView(APIView):
    """
    POST /api/discussions/notifications/<pk>/read/ — Mark a specific notification as read.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        notif = get_object_or_404(DiscussionNotification, pk=pk, recipient=request.user)
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        return Response({'id': notif.id, 'is_read': True})


class DiscussionNotificationMarkAllReadView(APIView):
    """
    POST /api/discussions/notifications/read-all/ — Mark all notifications as read.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = DiscussionNotification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).update(is_read=True)
        return Response({'detail': f'{updated} notifications marked as read.'})
