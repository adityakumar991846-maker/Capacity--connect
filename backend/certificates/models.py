"""
Models for the certificates and credential verification engine.
"""

import hashlib
import secrets
from django.conf import settings
from django.db import models
from django.utils import timezone


class CertificateStatus:
    ACTIVE = 'ACTIVE'
    REVOKED = 'REVOKED'


def _generate_default_code():
    year = timezone.now().year
    chunk1 = secrets.token_hex(2).upper()
    chunk2 = secrets.token_hex(2).upper()
    return f'CC-{year}-{chunk1}-{chunk2}'


def _generate_default_hash():
    token = secrets.token_hex(32)
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


class Certificate(models.Model):
    """
    An immutable digital certificate issued to a trainee upon 100% course completion.
    """
    enrollment = models.OneToOneField(
        'enrollments.Enrollment',
        on_delete=models.CASCADE,
        related_name='certificate',
    )
    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='certificates',
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='certificates',
    )
    certificate_code = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        default=_generate_default_code,
    )
    verification_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        default=_generate_default_hash,
    )
    final_grade_percentage = models.FloatField(default=100.0)
    issued_at = models.DateTimeField(auto_now_add=True)
    is_revoked = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.TextField(blank=True, default='')
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='revoked_certificates',
    )

    class Meta:
        ordering = ['-issued_at']
        unique_together = [('trainee', 'course')]
        verbose_name = 'Certificate'
        verbose_name_plural = 'Certificates'

    def __str__(self):
        status_str = CertificateStatus.REVOKED if self.is_revoked else CertificateStatus.ACTIVE
        return f'{self.certificate_code} — {self.trainee.username} ({self.course.title}) [{status_str}]'

    @property
    def status(self):
        return CertificateStatus.REVOKED if self.is_revoked else CertificateStatus.ACTIVE

    def revoke(self, admin_user=None, reason='', revoked_by_user=None):
        """Revoke this certificate."""
        user = admin_user or revoked_by_user
        self.is_revoked = True
        self.revoked_at = timezone.now()
        self.revoked_by = user
        self.revocation_reason = reason
        self.save(update_fields=['is_revoked', 'revoked_at', 'revoked_by', 'revocation_reason'])

    def reinstate(self):
        """Reinstate a previously revoked certificate."""
        self.is_revoked = False
        self.revoked_at = None
        self.revoked_by = None
        self.revocation_reason = ''
        self.save(update_fields=['is_revoked', 'revoked_at', 'revoked_by', 'revocation_reason'])
