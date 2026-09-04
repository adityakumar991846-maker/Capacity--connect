"""
URL configuration for Capacity Connect project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),

    # API namespace
    path('api/auth/', include('core.urls')),
    path('api/courses/', include('courses.urls')),
    path('api/enrollments/', include('enrollments.urls')),
    path('api/assessments/', include('assessments.urls')),

    # DRF browsable API auth (login/logout for the browsable API)
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]
