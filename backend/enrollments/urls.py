"""
URL configuration for the enrollments app.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.EnrollmentListCreateView.as_view(), name='enrollment-list-create'),
    path('<int:pk>/', views.EnrollmentDetailView.as_view(), name='enrollment-detail'),
    path('<int:pk>/subjects/<int:subject_id>/complete/', views.SubjectCompletionToggleView.as_view(), name='enrollment-subject-complete'),
    path('<int:pk>/drop/', views.EnrollmentDropView.as_view(), name='enrollment-drop'),
    path('course/<int:course_id>/', views.CourseEnrollmentsListView.as_view(), name='course-enrollments-list'),
    
    # Admin enrollment overview
    path('admin/all/', views.AdminEnrollmentListView.as_view(), name='admin-enrollment-list'),
]
