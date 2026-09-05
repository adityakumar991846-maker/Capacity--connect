"""
URL configuration for the assessments app.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Trainer routes
    path('trainer/courses/<int:course_id>/', views.TrainerCourseAssessmentListCreateView.as_view(), name='trainer-course-assessment-list-create'),
    path('trainer/<int:pk>/', views.TrainerAssessmentDetailView.as_view(), name='trainer-assessment-detail'),
    path('trainer/<int:assessment_id>/questions/', views.TrainerQuestionCreateView.as_view(), name='trainer-question-create'),
    path('trainer/questions/<int:pk>/', views.TrainerQuestionDetailView.as_view(), name='trainer-question-detail'),
    path('trainer/<int:assessment_id>/results/', views.TrainerAssessmentResultsView.as_view(), name='trainer-assessment-results'),

    # Trainee routes
    path('trainee/courses/<int:course_id>/', views.TraineeCourseAssessmentListView.as_view(), name='trainee-course-assessment-list'),
    path('trainee/<int:pk>/take/', views.TraineeAssessmentTakeView.as_view(), name='trainee-assessment-take'),
    path('trainee/<int:pk>/submit/', views.TraineeAssessmentSubmitView.as_view(), name='trainee-assessment-submit'),
    path('trainee/attempts/<int:pk>/', views.TraineeAttemptDetailView.as_view(), name='trainee-attempt-detail'),
    path('trainee/my-attempts/', views.TraineeMyAttemptsView.as_view(), name='trainee-my-attempts'),

    # Admin routes
    path('admin/all/', views.AdminAssessmentListView.as_view(), name='admin-assessment-list'),
]
