/**
 * Public Certificate Verification Script
 * Supports querying /api/certificates/verify/<identifier>/ without auth.
 */

const CertificateVerifier = {
    init() {
        const form = document.getElementById('verifyForm');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                const input = document.getElementById('certIdentifierInput');
                const val = (input ? input.value : '').trim();
                if (val) {
                    this.verify(val);
                }
            });
        }

        // Auto-check URL query param (e.g. ?code=... or ?hash=... or ?id=...)
        const urlParams = new URLSearchParams(window.location.search);
        const identifier = urlParams.get('code') || urlParams.get('hash') || urlParams.get('id');
        if (identifier) {
            const input = document.getElementById('certIdentifierInput');
            if (input) input.value = identifier;
            this.verify(identifier);
        }
    },

    async verify(identifier) {
        const alertArea = document.getElementById('verifyAlertArea');
        const resultArea = document.getElementById('certificateResultArea');
        const btnSubmit = document.getElementById('btnVerifySubmit');

        if (alertArea) alertArea.innerHTML = '';
        if (resultArea) resultArea.classList.add('d-none');
        if (btnSubmit) {
            btnSubmit.disabled = true;
            btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Verifying...';
        }

        try {
            const endpoint = `/api/certificates/verify/${encodeURIComponent(identifier)}/`;
            const response = await fetch(endpoint, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' },
            });

            const data = await response.json();

            if (!response.ok) {
                const msg = data.detail || 'Certificate not found. The provided verification code is invalid.';
                if (alertArea) {
                    alertArea.innerHTML = `
                        <div class="alert alert-danger d-flex align-items-center rounded-3 shadow-sm py-3">
                            <i class="bi bi-x-octagon-fill fs-4 me-3"></i>
                            <div>
                                <h6 class="fw-bold mb-1">Invalid Certificate</h6>
                                <p class="mb-0 small">${msg}</p>
                            </div>
                        </div>
                    `;
                }
                return;
            }

            this.renderCertificate(data);
        } catch (err) {
            if (alertArea) {
                alertArea.innerHTML = `
                    <div class="alert alert-danger d-flex align-items-center rounded-3 shadow-sm py-3">
                        <i class="bi bi-exclamation-triangle-fill fs-4 me-3"></i>
                        <div>
                            <h6 class="fw-bold mb-1">Network Error</h6>
                            <p class="mb-0 small">Unable to reach the verification server. Please try again later.</p>
                        </div>
                    </div>
                `;
            }
        } finally {
            if (btnSubmit) {
                btnSubmit.disabled = false;
                btnSubmit.innerHTML = 'Verify';
            }
        }
    },

    renderCertificate(cert) {
        const resultArea = document.getElementById('certificateResultArea');
        if (!resultArea) return;

        // Populate fields
        const traineeNameEl = document.getElementById('certTraineeName');
        const courseTitleEl = document.getElementById('certCourseTitle');
        const courseCatEl = document.getElementById('certCourseCategory');
        const gradeEl = document.getElementById('certFinalGrade');
        const dateEl = document.getElementById('certIssuedDate');
        const trainerEl = document.getElementById('certTrainerName');
        const codeEl = document.getElementById('certCodeDisplay');
        const statusBadgeEl = document.getElementById('certStatusBadge');
        const stampEl = document.getElementById('certStamp');
        const stampIconEl = document.getElementById('certStampIcon');
        const revokedNotice = document.getElementById('certRevokedNotice');
        const revokedDetails = document.getElementById('certRevokedDetails');

        if (traineeNameEl) traineeNameEl.textContent = cert.trainee_name || 'Trainee';
        if (courseTitleEl) courseTitleEl.textContent = cert.course_title || 'Course';
        if (courseCatEl) courseCatEl.textContent = cert.course_category || 'General';
        if (gradeEl) gradeEl.textContent = `${cert.final_grade_percentage || 100.0}%`;

        if (dateEl) {
            const dateObj = cert.issued_at ? new Date(cert.issued_at) : new Date();
            dateEl.textContent = dateObj.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
            });
        }

        if (trainerEl) trainerEl.textContent = cert.trainer_name || 'Capacity Connect Instructor';
        if (codeEl) codeEl.textContent = cert.certificate_code || '';

        // Status styling
        const isRevoked = cert.is_revoked || cert.status === 'REVOKED';

        if (isRevoked) {
            if (statusBadgeEl) {
                statusBadgeEl.textContent = 'REVOKED';
                statusBadgeEl.className = 'badge bg-danger';
            }
            if (stampEl) {
                stampEl.className = 'cert-badge-stamp cert-badge-revoked';
            }
            if (stampIconEl) {
                stampIconEl.className = 'bi bi-x-octagon-fill fs-2';
            }
            if (revokedNotice) {
                revokedNotice.classList.remove('d-none');
            }
            if (revokedDetails) {
                const rDate = cert.revoked_at ? new Date(cert.revoked_at).toLocaleDateString() : '';
                revokedDetails.textContent = `Revoked${rDate ? ' on ' + rDate : ''}. Reason: ${cert.revocation_reason || 'Administrative action.'}`;
            }
        } else {
            if (statusBadgeEl) {
                statusBadgeEl.textContent = 'VALID';
                statusBadgeEl.className = 'badge bg-success';
            }
            if (stampEl) {
                stampEl.className = 'cert-badge-stamp';
            }
            if (stampIconEl) {
                stampIconEl.className = 'bi bi-award-fill fs-2';
            }
            if (revokedNotice) {
                revokedNotice.classList.add('d-none');
            }
        }

        resultArea.classList.remove('d-none');
        resultArea.scrollIntoView({ behavior: 'smooth' });
    }
};

document.addEventListener('DOMContentLoaded', () => {
    CertificateVerifier.init();
});
