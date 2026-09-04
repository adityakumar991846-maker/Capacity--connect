"""
URL patterns for reviews app (Step 14).
"""

from django.urls import path
from . import views

urlpatterns = [
    # Course specific reviews
    path('courses/<int:course_id>/reviews/', views.CourseReviewListCreateView.as_view(), name='course-review-list-create'),
    path('courses/<int:course_id>/reviews/my-review/', views.CourseMyReviewView.as_view(), name='course-my-review'),

    # Direct review operations
    path('reviews/<int:pk>/', views.CourseReviewDetailView.as_view(), name='review-detail'),
    path('reviews/<int:pk>/moderate/', views.CourseReviewModerateView.as_view(), name='review-moderate'),

    # Trainer feedback portal
    path('reviews/trainer/feedback/', views.TrainerFeedbackListView.as_view(), name='trainer-feedback-list'),
]
