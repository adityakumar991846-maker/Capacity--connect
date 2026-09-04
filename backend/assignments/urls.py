"""
URL configuration for the assignments app.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Course assignments list & create
    path('courses/<int:course_id>/', views.CourseAssignmentListCreateView.as_view(), name='course-assignment-list-create'),

    # Assignment detail, edit, delete
    path('<int:pk>/', views.AssignmentDetailView.as_view(), name='assignment-detail'),
    path('<int:pk>/my-submission/', views.AssignmentMySubmissionView.as_view(), name='assignment-my-submission'),
    path('<int:pk>/submit/', views.AssignmentSubmitView.as_view(), name='assignment-submit'),
    path('<int:pk>/submissions/', views.AssignmentSubmissionListView.as_view(), name='assignment-submissions-list'),

    # Grading & reviews
    path('submissions/<int:pk>/grade/', views.SubmissionGradeView.as_view(), name='submission-grade'),
    path('trainer/pending-reviews/', views.TrainerPendingReviewsView.as_view(), name='trainer-pending-reviews'),
]
