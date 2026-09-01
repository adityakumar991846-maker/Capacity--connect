"""
Views for the courses module.

Provides API views for Course and Subject CRUD operations with
role-based visibility and ownership enforcement.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Role
from .models import Course, CourseStatus, Subject
from .permissions import IsTrainerOrAdmin
from .serializers import (
    CourseCreateUpdateSerializer,
    CourseDetailSerializer,
    CourseListSerializer,
    SubjectSerializer,
)


def _get_user_role(user):
    """Safely retrieve user profile role."""
    if user and hasattr(user, 'profile'):
        return user.profile.role
    return None


def _can_user_view_course(user, course):
    """Check if user has permission to view the given course."""
    role = _get_user_role(user)
    if role == Role.ADMIN:
        return True
    if role == Role.TRAINER:
        return course.trainer == user or course.status == CourseStatus.PUBLISHED
    if role == Role.TRAINEE:
        return course.status == CourseStatus.PUBLISHED
    return False


def _check_course_write_permission(user, course):
    """Check if user has permission to mutate the course (or its subjects)."""
    role = _get_user_role(user)
    if role == Role.ADMIN:
        return True
    if role == Role.TRAINER and course.trainer == user:
        return True
    raise PermissionDenied('You do not have permission to modify this course.')


class CourseListCreateView(APIView):
    """
    GET  /api/courses/ - List visible courses based on role
    POST /api/courses/ - Create a new course (Trainer or Admin only)
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsTrainerOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        role = _get_user_role(user)
        if role == Role.ADMIN:
            return Course.objects.all()
        if role == Role.TRAINER:
            return Course.objects.filter(
                Q(trainer=user) | Q(status=CourseStatus.PUBLISHED)
            )
        # Trainee and default
        return Course.objects.filter(status=CourseStatus.PUBLISHED)

    def get(self, request):
        courses = self.get_queryset()
        serializer = CourseListSerializer(courses, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CourseCreateUpdateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        course = serializer.save()
        return Response(
            CourseDetailSerializer(course).data,
            status=status.HTTP_201_CREATED,
        )


class CourseDetailView(APIView):
    """
    GET    /api/courses/<pk>/ - View course details
    PUT    /api/courses/<pk>/ - Full update of course (Owner or Admin)
    PATCH  /api/courses/<pk>/ - Partial update of course (Owner or Admin)
    DELETE /api/courses/<pk>/ - Delete course (Owner or Admin)
    """

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAuthenticated(), IsTrainerOrAdmin()]
        return [IsAuthenticated()]

    def get_object(self, pk):
        course = get_object_or_404(Course, pk=pk)
        user = self.request.user

        if self.request.method == 'GET':
            if not _can_user_view_course(user, course):
                raise get_object_or_404(Course, pk=0)  # Trigger 404 for unviewable
        else:
            _check_course_write_permission(user, course)

        return course

    def get(self, request, pk):
        course = self.get_object(pk)
        return Response(CourseDetailSerializer(course).data)

    def put(self, request, pk):
        course = self.get_object(pk)
        serializer = CourseCreateUpdateSerializer(
            course,
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        updated_course = serializer.save()
        return Response(CourseDetailSerializer(updated_course).data)

    def patch(self, request, pk):
        course = self.get_object(pk)
        serializer = CourseCreateUpdateSerializer(
            course,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        updated_course = serializer.save()
        return Response(CourseDetailSerializer(updated_course).data)

    def delete(self, request, pk):
        course = self.get_object(pk)
        course.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SubjectListCreateView(APIView):
    """
    GET  /api/courses/<course_id>/subjects/ - List subjects for a course
    POST /api/courses/<course_id>/subjects/ - Add subject to a course (Owner/Admin)
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsTrainerOrAdmin()]
        return [IsAuthenticated()]

    def get_course(self, course_id):
        course = get_object_or_404(Course, pk=course_id)
        user = self.request.user
        if self.request.method == 'GET':
            if not _can_user_view_course(user, course):
                raise get_object_or_404(Course, pk=0)
        else:
            _check_course_write_permission(user, course)
        return course

    def get(self, request, course_id):
        course = self.get_course(course_id)
        subjects = course.subjects.all()
        serializer = SubjectSerializer(subjects, many=True)
        return Response(serializer.data)

    def post(self, request, course_id):
        course = self.get_course(course_id)
        serializer = SubjectSerializer(
            data=request.data,
            context={'course': course, 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        subject = serializer.save(course=course)
        return Response(
            SubjectSerializer(subject).data,
            status=status.HTTP_201_CREATED,
        )


class SubjectDetailView(APIView):
    """
    GET    /api/courses/<course_id>/subjects/<pk>/ - View single subject
    PUT    /api/courses/<course_id>/subjects/<pk>/ - Update subject
    PATCH  /api/courses/<course_id>/subjects/<pk>/ - Partial update subject
    DELETE /api/courses/<course_id>/subjects/<pk>/ - Delete subject
    """

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAuthenticated(), IsTrainerOrAdmin()]
        return [IsAuthenticated()]

    def get_course_and_subject(self, course_id, pk):
        course = get_object_or_404(Course, pk=course_id)
        user = self.request.user
        if self.request.method == 'GET':
            if not _can_user_view_course(user, course):
                raise get_object_or_404(Course, pk=0)
        else:
            _check_course_write_permission(user, course)

        subject = get_object_or_404(Subject, pk=pk, course=course)
        return course, subject

    def get(self, request, course_id, pk):
        _, subject = self.get_course_and_subject(course_id, pk)
        return Response(SubjectSerializer(subject).data)

    def put(self, request, course_id, pk):
        course, subject = self.get_course_and_subject(course_id, pk)
        serializer = SubjectSerializer(
            subject,
            data=request.data,
            context={'course': course, 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(SubjectSerializer(updated).data)

    def patch(self, request, course_id, pk):
        course, subject = self.get_course_and_subject(course_id, pk)
        serializer = SubjectSerializer(
            subject,
            data=request.data,
            partial=True,
            context={'course': course, 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(SubjectSerializer(updated).data)

    def delete(self, request, course_id, pk):
        _, subject = self.get_course_and_subject(course_id, pk)
        subject.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
