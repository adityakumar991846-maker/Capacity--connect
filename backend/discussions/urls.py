"""
URL configuration for the discussions app.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Course discussions list & create
    path('courses/<int:course_id>/', views.CourseDiscussionThreadListCreateView.as_view(), name='course-discussion-list-create'),

    # Thread operations
    path('<int:pk>/', views.DiscussionThreadDetailView.as_view(), name='discussion-thread-detail'),
    path('<int:pk>/resolve/', views.DiscussionThreadResolveToggleView.as_view(), name='discussion-thread-resolve'),
    path('<int:pk>/pin/', views.DiscussionThreadPinToggleView.as_view(), name='discussion-thread-pin'),
    path('<int:pk>/upvote/', views.DiscussionThreadUpvoteToggleView.as_view(), name='discussion-thread-upvote'),

    # Reply operations
    path('<int:pk>/replies/', views.DiscussionReplyListCreateView.as_view(), name='discussion-reply-list-create'),
    path('replies/<int:pk>/', views.DiscussionReplyDetailView.as_view(), name='discussion-reply-detail'),
    path('replies/<int:pk>/endorse/', views.DiscussionReplyEndorseToggleView.as_view(), name='discussion-reply-endorse'),

    # Trainer Q&A inquiries inbox
    path('trainer/inbox/', views.TrainerDiscussionInboxView.as_view(), name='trainer-discussion-inbox'),

    # Notifications
    path('notifications/', views.DiscussionNotificationListView.as_view(), name='discussion-notification-list'),
    path('notifications/<int:pk>/read/', views.DiscussionNotificationMarkReadView.as_view(), name='discussion-notification-mark-read'),
    path('notifications/read-all/', views.DiscussionNotificationMarkAllReadView.as_view(), name='discussion-notification-mark-all-read'),
]
