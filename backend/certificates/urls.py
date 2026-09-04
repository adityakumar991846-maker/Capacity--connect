"""
URL configuration for the certificates app.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Trainee endpoints
    path('my-certificates/', views.TraineeMyCertificatesView.as_view(), name='trainee-my-certificates'),
    path('<int:pk>/', views.TraineeCertificateDetailView.as_view(), name='trainee-certificate-detail'),
    path('claim/<int:enrollment_id>/', views.TraineeClaimCertificateView.as_view(), name='trainee-claim-certificate'),

    # Public verification
    path('verify/<str:identifier>/', views.PublicCertificateVerifyView.as_view(), name='public-certificate-verify'),

    # Trainer & Admin governance
    path('trainer/courses/<int:course_id>/', views.TrainerCourseCertificatesView.as_view(), name='trainer-course-certificates'),
    path('<int:pk>/revoke/', views.AdminRevokeCertificateView.as_view(), name='admin-revoke-certificate'),
    path('<int:pk>/reinstate/', views.AdminReinstateCertificateView.as_view(), name='admin-reinstate-certificate'),
]
