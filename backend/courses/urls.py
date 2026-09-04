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
    path('<int:pk>/', views.CourseDetailView.as_view(), name='course-detail'),
    path('<int:course_id>/subjects/', views.SubjectListCreateView.as_view(), name='subject-list-create'),
    path('<int:course_id>/subjects/<int:pk>/', views.SubjectDetailView.as_view(), name='subject-detail'),
]
