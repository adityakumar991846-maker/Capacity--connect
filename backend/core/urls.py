"""
URL patterns for the core authentication module.

All patterns are included under /api/auth/ by the root URL config.
"""

from django.urls import path

from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='auth-register'),
    path('login/', views.LoginView.as_view(), name='auth-login'),
    path('logout/', views.LogoutView.as_view(), name='auth-logout'),
    path('me/', views.CurrentUserView.as_view(), name='auth-me'),

    # Admin user management
    path('admin/users/', views.AdminUserListView.as_view(), name='admin-user-list'),
    path('admin/users/<int:pk>/', views.AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/users/<int:pk>/deactivate/', views.AdminUserDeactivateView.as_view(), name='admin-user-deactivate'),
    path('admin/users/<int:pk>/activate/', views.AdminUserActivateView.as_view(), name='admin-user-activate'),
]
