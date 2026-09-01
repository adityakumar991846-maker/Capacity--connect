"""
URL configuration for the courses app.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.CourseListCreateView.as_view(), name='course-list-create'),
    path('<int:pk>/', views.CourseDetailView.as_view(), name='course-detail'),
    path('<int:course_id>/subjects/', views.SubjectListCreateView.as_view(), name='subject-list-create'),
    path('<int:course_id>/subjects/<int:pk>/', views.SubjectDetailView.as_view(), name='subject-detail'),
]
