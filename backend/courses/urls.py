"""
URL configuration for the courses app.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.CourseListCreateView.as_view(), name='course-list-create'),
    path('trainer/dashboard-stats/', views.TrainerDashboardStatsView.as_view(), name='trainer-dashboard-stats'),
    path('trainer/my-courses/', views.TrainerMyCoursesView.as_view(), name='trainer-my-courses'),
    path('trainer/courses/<int:course_id>/roster/', views.TrainerCourseRosterView.as_view(), name='trainer-course-roster'),

    # Admin governance routes
    path('admin/platform-stats/', views.AdminPlatformStatsView.as_view(), name='admin-platform-stats'),
    path('admin/courses/', views.AdminCourseListView.as_view(), name='admin-course-list'),
    path('admin/courses/<int:pk>/publish/', views.AdminCoursePublishView.as_view(), name='admin-course-publish'),
    path('admin/courses/<int:pk>/reject/', views.AdminCourseRejectView.as_view(), name='admin-course-reject'),
    path('admin/courses/<int:pk>/archive/', views.AdminCourseArchiveView.as_view(), name='admin-course-archive'),

    path('<int:pk>/', views.CourseDetailView.as_view(), name='course-detail'),
    path('<int:course_id>/subjects/', views.SubjectListCreateView.as_view(), name='subject-list-create'),
    path('<int:course_id>/subjects/<int:pk>/', views.SubjectDetailView.as_view(), name='subject-detail'),
]
