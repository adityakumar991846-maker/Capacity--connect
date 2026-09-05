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
from .permissions import IsTrainerOrAdmin, IsAdmin
from .serializers import (
    CourseCreateUpdateSerializer,
    CourseDetailSerializer,
    CourseListSerializer,
    SubjectSerializer,
    TrainerCourseItemSerializer,
    TrainerCourseRosterItemSerializer,
    TrainerDashboardStatsSerializer,
    AdminPlatformStatsSerializer,
    AdminCourseListSerializer,
    AdminPlatformAnalyticsSerializer,
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
        if course.status == CourseStatus.PUBLISHED:
            raise PermissionDenied('Trainers cannot modify published courses.')
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


class TrainerDashboardStatsView(APIView):
    """
    GET /api/courses/trainer/dashboard-stats/
    Returns aggregate statistics for courses authored by the authenticated trainer.
    """
    permission_classes = [IsAuthenticated, IsTrainerOrAdmin]

    def get(self, request):
        user = request.user
        role = _get_user_role(user)

        if role == Role.ADMIN:
            courses_qs = Course.objects.all()
            from enrollments.models import Enrollment, EnrollmentStatus
            enrollments_qs = Enrollment.objects.all()
        else:
            courses_qs = Course.objects.filter(trainer=user)
            from enrollments.models import Enrollment, EnrollmentStatus
            enrollments_qs = Enrollment.objects.filter(course__trainer=user)

        total_courses = courses_qs.count()
        published_courses = courses_qs.filter(status=CourseStatus.PUBLISHED).count()
        draft_courses = courses_qs.filter(status=CourseStatus.DRAFT).count()
        archived_courses = courses_qs.filter(status=CourseStatus.ARCHIVED).count()

        total_enrollments = enrollments_qs.count()
        completed_enrollments = enrollments_qs.filter(status=EnrollmentStatus.COMPLETED).count()

        enrollment_list = list(enrollments_qs)
        if enrollment_list:
            avg_prog = round(sum(e.progress_percentage for e in enrollment_list) / len(enrollment_list), 2)
        else:
            avg_prog = 0.0

        data = {
            'total_courses': total_courses,
            'published_courses': published_courses,
            'draft_courses': draft_courses,
            'archived_courses': archived_courses,
            'total_enrollments': total_enrollments,
            'completed_enrollments': completed_enrollments,
            'average_progress': avg_prog,
        }
        serializer = TrainerDashboardStatsSerializer(data)
        return Response(serializer.data)


class TrainerMyCoursesView(APIView):
    """
    GET /api/courses/trainer/my-courses/
    Returns all courses authored by the authenticated trainer with embedded metrics.
    """
    permission_classes = [IsAuthenticated, IsTrainerOrAdmin]

    def get(self, request):
        user = request.user
        role = _get_user_role(user)

        if role == Role.ADMIN:
            courses = Course.objects.all().prefetch_related('subjects', 'enrollments')
        else:
            courses = Course.objects.filter(trainer=user).prefetch_related('subjects', 'enrollments')

        serializer = TrainerCourseItemSerializer(courses, many=True)
        return Response(serializer.data)


class TrainerCourseRosterView(APIView):
    """
    GET /api/courses/trainer/courses/<course_id>/roster/
    Returns the student roster and progress for a course owned by the trainer.
    """
    permission_classes = [IsAuthenticated, IsTrainerOrAdmin]

    def get(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id)
        role = _get_user_role(request.user)
        if role != Role.ADMIN and (role != Role.TRAINER or course.trainer != request.user):
            raise PermissionDenied('You do not have permission to view this roster.')

        enrollments = course.enrollments.select_related('trainee').all()
        roster_data = [
            {
                'enrollment_id': e.id,
                'trainee_id': e.trainee.id,
                'username': e.trainee.username,
                'email': e.trainee.email,
                'status': e.status,
                'progress_percentage': e.progress_percentage,
                'enrolled_at': e.enrolled_at,
                'completed_at': e.completed_at,
                'last_accessed_at': e.last_accessed_at,
            }
            for e in enrollments
        ]

        serializer = TrainerCourseRosterItemSerializer(roster_data, many=True)
        return Response(serializer.data)


class AdminPlatformStatsView(APIView):
    """
    GET /api/courses/admin/platform-stats/ — Platform-wide KPI dashboard metrics.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        from django.contrib.auth.models import User
        from enrollments.models import Enrollment, EnrollmentStatus
        from certificates.models import Certificate

        # User stats
        total_users = User.objects.count()
        total_trainers = User.objects.filter(profile__role=Role.TRAINER).count()
        total_trainees = User.objects.filter(profile__role=Role.TRAINEE).count()

        # Course stats
        total_courses = Course.objects.count()
        draft_courses = Course.objects.filter(status=CourseStatus.DRAFT).count()
        published_courses = Course.objects.filter(status=CourseStatus.PUBLISHED).count()
        archived_courses = Course.objects.filter(status=CourseStatus.ARCHIVED).count()
        rejected_courses = Course.objects.filter(status=CourseStatus.REJECTED).count()

        # Enrollment stats
        total_enrollments = Enrollment.objects.count()
        active_enrollments = Enrollment.objects.filter(status=EnrollmentStatus.ENROLLED).count()
        completed_enrollments = Enrollment.objects.filter(status=EnrollmentStatus.COMPLETED).count()
        dropped_enrollments = Enrollment.objects.filter(status=EnrollmentStatus.DROPPED).count()

        # Certificate stats
        total_certificates = Certificate.objects.count()
        revoked_certificates = Certificate.objects.filter(is_revoked=True).count()

        # Platform average completion
        all_enrollments = list(Enrollment.objects.exclude(status=EnrollmentStatus.DROPPED))
        if all_enrollments:
            platform_avg = round(
                sum(e.progress_percentage for e in all_enrollments) / len(all_enrollments), 2
            )
        else:
            platform_avg = 0.0

        data = {
            'total_users': total_users,
            'total_trainers': total_trainers,
            'total_trainees': total_trainees,
            'total_courses': total_courses,
            'draft_courses': draft_courses,
            'published_courses': published_courses,
            'archived_courses': archived_courses,
            'rejected_courses': rejected_courses,
            'total_enrollments': total_enrollments,
            'active_enrollments': active_enrollments,
            'completed_enrollments': completed_enrollments,
            'dropped_enrollments': dropped_enrollments,
            'total_certificates': total_certificates,
            'revoked_certificates': revoked_certificates,
            'platform_avg_completion': platform_avg,
        }
        serializer = AdminPlatformStatsSerializer(data)
        return Response(serializer.data)


class AdminCourseListView(APIView):
    """
    GET /api/courses/admin/courses/ — All courses with optional status filter.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        courses = Course.objects.select_related('trainer').prefetch_related('subjects', 'enrollments').all()

        status_filter = request.query_params.get('status')
        if status_filter:
            courses = courses.filter(status=status_filter.upper())

        serializer = AdminCourseListSerializer(courses, many=True)
        return Response(serializer.data)


class AdminCoursePublishView(APIView):
    """
    POST /api/courses/admin/courses/<pk>/publish/ — Approve and publish a DRAFT course.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        course = get_object_or_404(Course, pk=pk)

        if course.status != CourseStatus.DRAFT:
            return Response(
                {'detail': 'Only DRAFT courses can be published.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        course.status = CourseStatus.PUBLISHED
        course.rejection_reason = ''
        course.save(update_fields=['status', 'rejection_reason', 'updated_at'])
        return Response(CourseDetailSerializer(course).data)


class AdminCourseRejectView(APIView):
    """
    POST /api/courses/admin/courses/<pk>/reject/ — Reject a DRAFT course with reason.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        course = get_object_or_404(Course, pk=pk)

        if course.status != CourseStatus.DRAFT:
            return Response(
                {'detail': 'Only DRAFT courses can be rejected.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response(
                {'detail': 'A rejection reason is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        course.status = CourseStatus.REJECTED
        course.rejection_reason = reason
        course.save(update_fields=['status', 'rejection_reason', 'updated_at'])
        return Response(CourseDetailSerializer(course).data)


class AdminCourseArchiveView(APIView):
    """
    POST /api/courses/admin/courses/<pk>/archive/ — Archive a PUBLISHED course.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        course = get_object_or_404(Course, pk=pk)

        if course.status != CourseStatus.PUBLISHED:
            return Response(
                {'detail': 'Only PUBLISHED courses can be archived.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        course.status = CourseStatus.ARCHIVED
        course.save(update_fields=['status', 'updated_at'])
        return Response(CourseDetailSerializer(course).data)


class AdminPlatformAnalyticsView(APIView):
    """
    GET /api/courses/admin/analytics/ — Deep platform analytics and performance metrics.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        from enrollments.models import Enrollment, EnrollmentStatus
        from certificates.models import Certificate
        from django.db.models import Count

        # 1. Retention & Completion Funnel
        total_enrollments = Enrollment.objects.count()
        active_enrollments = Enrollment.objects.filter(status=EnrollmentStatus.ENROLLED).count()
        completed_enrollments = Enrollment.objects.filter(status=EnrollmentStatus.COMPLETED).count()
        dropped_enrollments = Enrollment.objects.filter(status=EnrollmentStatus.DROPPED).count()

        completion_rate = round((completed_enrollments / total_enrollments * 100), 1) if total_enrollments > 0 else 0.0
        retention_rate = round(((total_enrollments - dropped_enrollments) / total_enrollments * 100), 1) if total_enrollments > 0 else 0.0

        # 2. Category Distribution
        categories_data = []
        category_stats = (
            Course.objects.values('category')
            .annotate(
                courses_count=Count('id', distinct=True),
                enrollments_count=Count('enrollments', distinct=True),
            )
            .order_by('-enrollments_count')
        )
        for stat in category_stats:
            categories_data.append({
                'category': stat['category'] or 'General',
                'courses_count': stat['courses_count'],
                'enrollments_count': stat['enrollments_count'],
            })

        # 3. Top Performing Courses
        top_courses_qs = (
            Course.objects.filter(status=CourseStatus.PUBLISHED)
            .select_related('trainer')
            .annotate(
                enrollment_count=Count('enrollments', distinct=True),
            )
            .order_by('-enrollment_count')[:6]
        )
        top_courses = []
        for c in top_courses_qs:
            c_enrollments = c.enrollments.all()
            c_total = c_enrollments.count()
            c_completed = c_enrollments.filter(status=EnrollmentStatus.COMPLETED).count()
            c_rate = round((c_completed / c_total * 100), 1) if c_total > 0 else 0.0

            top_courses.append({
                'id': c.id,
                'title': c.title,
                'trainer_username': c.trainer.username,
                'category': c.category,
                'enrollment_count': c.enrollment_count,
                'average_rating': float(c.average_rating or 0.0),
                'completion_rate': c_rate,
            })

        # 4. Trainee Outcomes & Honors Breakdown
        certs = Certificate.objects.filter(is_revoked=False)
        total_certs = certs.count()
        distinction = certs.filter(final_grade_percentage__gte=90.0).count()
        merit = certs.filter(final_grade_percentage__gte=80.0, final_grade_percentage__lt=90.0).count()
        pass_cnt = certs.filter(final_grade_percentage__lt=80.0).count()
        placement_ready = certs.values('trainee').distinct().count()

        analytics_data = {
            'total_enrollments': total_enrollments,
            'active_enrollments': active_enrollments,
            'completed_enrollments': completed_enrollments,
            'dropped_enrollments': dropped_enrollments,
            'completion_rate': completion_rate,
            'retention_rate': retention_rate,
            'categories': categories_data,
            'top_courses': top_courses,
            'total_certificates': total_certs,
            'distinction_count': distinction,
            'merit_count': merit,
            'pass_count': pass_cnt,
            'placement_ready_trainees': placement_ready,
        }

        serializer = AdminPlatformAnalyticsSerializer(analytics_data)
        return Response(serializer.data)
