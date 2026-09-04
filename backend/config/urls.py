"""
URL configuration for Capacity Connect project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),

    # API namespace
    path('api/auth/', include('core.urls')),
    path('api/courses/', include('courses.urls')),
    path('api/enrollments/', include('enrollments.urls')),
    path('api/assessments/', include('assessments.urls')),
    path('api/certificates/', include('certificates.urls')),
    path('api/discussions/', include('discussions.urls')),
    path('api/assignments/', include('assignments.urls')),
    path('api/', include('reviews.urls')),

    # DRF browsable API auth (login/logout for the browsable API)
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]

# Serve user-uploaded media files locally during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

