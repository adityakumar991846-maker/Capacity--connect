/**
 * my-certificates.js
 * Frontend controller for Step 15: Trainee Credential Portfolio, Official Transcripts & Achievements Hub.
 */

const MyCertificatesController = {
    _certificates: [],
    _summary: null,
    _transcript: null,
    _activeFilter: 'ALL',
    _activeSearch: '',

    /**
     * Initializes the My Certificates space.
     */
    async init() {
        await this.loadSummary();
        await this.loadCertificates();
        this.setupFilters();
    },

    /**
     * Fetch achievement summary KPIs.
     */
    async loadSummary() {
        try {
            const data = await apiRequest('/certificates/my-summary/');
            this._summary = data;
            this.renderSummary(data);
        } catch (err) {
            console.debug('[MyCertificates] Error loading summary:', err.message);
        }
    },

    /**
     * Render achievement summary cards.
     */
    renderSummary(summary) {
        if (!summary) return;
        const certCountEl = document.getElementById('statTotalCertificates');
        const avgGradeEl = document.getElementById('statAverageGrade');
        const hoursEl = document.getElementById('statTotalCertifiedHours');
        const distinctionEl = document.getElementById('statDistinctions');

        if (certCountEl) certCountEl.textContent = summary.total_certificates || 0;
        if (avgGradeEl) avgGradeEl.textContent = `${(summary.cumulative_grade_average || 0).toFixed(1)}%`;
        if (hoursEl) hoursEl.textContent = `${summary.total_certified_hours || 0} hrs`;
        if (distinctionEl) distinctionEl.textContent = summary.distinctions_count || 0;
    },

    /**
     * Fetch all certificates for the trainee.
     */
    async loadCertificates() {
        const grid = document.getElementById('certificatesGrid');
        const emptyState = document.getElementById('certificatesEmptyState');
        const errorState = document.getElementById('certificatesErrorState');

        if (errorState) errorState.classList.add('d-none');
        if (emptyState) emptyState.classList.add('d-none');
        if (grid) {
            grid.innerHTML = `
                <div class="col-12 text-center py-5">
                    <div class="spinner-border text-primary" role="status"></div>
                    <p class="text-muted small mt-2">Loading your credential portfolio...</p>
                </div>
            `;
        }

        try {
            const data = await apiRequest('/certificates/my-certificates/');
            this._certificates = Array.isArray(data) ? data : [];
            this.applyFiltersAndRender();
        } catch (err) {
            console.error('[MyCertificates] Error loading certificates:', err);
            if (grid) grid.innerHTML = '';
            if (errorState) {
                errorState.classList.remove('d-none');
                const msgEl = errorState.querySelector('.error-message');
                if (msgEl) msgEl.textContent = err.message || 'Unable to load certificates.';
            }
        }
    },

    /**
     * Filter certificates and render portfolio cards.
     */
    applyFiltersAndRender() {
        const grid = document.getElementById('certificatesGrid');
        const emptyState = document.getElementById('certificatesEmptyState');
        if (!grid) return;

        let filtered = [...this._certificates];

        // Status / Honors Filter
        if (this._activeFilter === 'DISTINCTION') {
            filtered = filtered.filter(c => c.honors_tier === 'DISTINCTION');
        } else if (this._activeFilter === 'ACTIVE') {
            filtered = filtered.filter(c => !c.is_revoked);
        }

        // Search Filter
        if (this._activeSearch) {
            const q = this._activeSearch.toLowerCase();
            filtered = filtered.filter(c => 
                (c.course_title || '').toLowerCase().includes(q) ||
                (c.certificate_code || '').toLowerCase().includes(q) ||
                (c.course_category || '').toLowerCase().includes(q)
            );
        }

        if (filtered.length === 0) {
            grid.innerHTML = '';
            if (emptyState) emptyState.classList.remove('d-none');
            return;
        }

        if (emptyState) emptyState.classList.add('d-none');
        grid.innerHTML = filtered.map(c => this.renderCertificateCard(c)).join('');
    },

    /**
     * Render single certificate credential card.
     */
    renderCertificateCard(c) {
        const isRevoked = c.is_revoked;
        const honorsClass = {
            'DISTINCTION': 'bg-warning-subtle text-warning-emphasis border-warning',
            'MERIT': 'bg-info-subtle text-info-emphasis border-info',
            'PASS': 'bg-light text-secondary border-secondary',
        }[c.honors_tier] || 'bg-light text-secondary';

        const honorsBadge = `
            <span class="badge ${honorsClass} border px-2 py-1 small fw-bold">
                <i class="bi bi-patch-check-fill me-1"></i>${c.honors_tier || 'PASS'}
            </span>
        `;

        const statusBadge = isRevoked
            ? '<span class="badge bg-danger-subtle text-danger px-2 py-1 small"><i class="bi bi-x-circle-fill me-1"></i>Revoked</span>'
            : '<span class="badge bg-success-subtle text-success px-2 py-1 small"><i class="bi bi-check-circle-fill me-1"></i>Verified</span>';

        const issuedDate = c.issued_at ? new Date(c.issued_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '—';
        const verifyUrl = `${window.location.origin}/pages/verify-certificate.html?code=${encodeURIComponent(c.certificate_code)}`;

        return `
            <div class="col-md-6 col-xl-4">
                <div class="card h-100 border-0 shadow-sm rounded-3 overflow-hidden position-relative" style="background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);">
                    <div style="height: 6px; background: linear-gradient(90deg, #4f46e5, #06b6d4, #10b981);"></div>
                    <div class="card-body p-4 d-flex flex-column">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <span class="badge bg-secondary-subtle text-secondary px-2 py-1 small fw-semibold">
                                ${this.escapeHtml(c.course_category || 'General')}
                            </span>
                            <div class="d-flex gap-1">
                                ${honorsBadge}
                                ${statusBadge}
                            </div>
                        </div>

                        <h5 class="fw-bold text-dark mb-2">${this.escapeHtml(c.course_title)}</h5>
                        
                        <div class="text-muted small mb-3">
                            <div><i class="bi bi-person me-1 text-primary"></i>${this.escapeHtml(c.trainer_name)}</div>
                            <div><i class="bi bi-clock me-1 text-primary"></i>${c.duration_hours || 0} Hours &bull; Final Grade: <strong>${(c.final_grade_percentage || 0).toFixed(1)}%</strong></div>
                            <div><i class="bi bi-calendar3 me-1 text-primary"></i>Issued: ${issuedDate}</div>
                        </div>

                        <div class="p-2 bg-light rounded-2 font-monospace small text-muted text-truncate mb-3" style="font-size:0.75rem;">
                            <i class="bi bi-shield-lock me-1"></i>${this.escapeHtml(c.certificate_code)}
                        </div>

                        <div class="mt-auto pt-3 border-top d-flex gap-2">
                            <button class="btn btn-primary btn-sm flex-fill fw-semibold" onclick="MyCertificatesController.openCertificateModal(${c.id});">
                                <i class="bi bi-eye me-1"></i>View &amp; Print
                            </button>
                            <button class="btn btn-outline-secondary btn-sm" onclick="MyCertificatesController.copyVerificationLink('${c.certificate_code}');" title="Copy Verification Link">
                                <i class="bi bi-link-45deg"></i>
                            </button>
                            <a href="verify-certificate.html?code=${encodeURIComponent(c.certificate_code)}" target="_blank" class="btn btn-outline-primary btn-sm" title="Public Verification Page">
                                <i class="bi bi-box-arrow-up-right"></i>
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Copy public verification link to clipboard.
     */
    async copyVerificationLink(code) {
        const url = `${window.location.origin}/pages/verify-certificate.html?code=${encodeURIComponent(code)}`;
        try {
            await navigator.clipboard.writeText(url);
            alert('Public credential verification link copied to clipboard!');
        } catch (e) {
            prompt('Copy certificate verification link:', url);
        }
    },

    /**
     * Open single certificate print/preview modal.
     */
    async openCertificateModal(certId) {
        const modalEl = document.getElementById('certificateViewModal');
        const container = document.getElementById('certificateModalBody');
        if (!modalEl || !container) return;

        container.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status"></div>
                <p class="text-muted small mt-2">Loading certificate...</p>
            </div>
        `;

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();

        try {
            const cert = await apiRequest(`/certificates/${certId}/`);
            const issuedDate = cert.issued_at ? new Date(cert.issued_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' }) : '';

            container.innerHTML = `
                <div class="p-4 bg-white border border-2 rounded-4 shadow-sm position-relative text-center" id="printableCertificateArea" style="min-height: 480px; border-color: #cbd5e1 !important;">
                    <div style="height: 6px; background: linear-gradient(90deg, #4f46e5, #06b6d4, #10b981); position:absolute; top:0; left:0; right:0; border-top-left-radius: 1rem; border-top-right-radius: 1rem;"></div>
                    
                    <div class="my-3">
                        <span class="badge bg-primary px-3 py-1 text-uppercase fw-semibold" style="letter-spacing: 2px;">Official Credential</span>
                    </div>

                    <h2 class="display-6 fw-bold text-dark font-serif mb-1">Certificate of Completion</h2>
                    <p class="text-muted small mb-4">Capacity Connect Professional Skills Acceleration Program</p>

                    <p class="text-secondary mb-1">This is proudly presented to</p>
                    <h3 class="fw-bold text-primary mb-3">${this.escapeHtml(cert.trainee_name || cert.trainee_username)}</h3>

                    <p class="text-secondary px-md-5 mb-3" style="line-height: 1.6;">
                        For successfully mastering the comprehensive curriculum, passing all mandatory assessments and project deliverables for
                    </p>

                    <h4 class="fw-bold text-dark mb-2">${this.escapeHtml(cert.course_title)}</h4>
                    <p class="text-muted small mb-4">${cert.duration_hours || 0} Hours &bull; Final Grade: <strong>${(cert.final_grade_percentage || 0).toFixed(1)}%</strong> (${cert.honors_tier || 'PASS'})</p>

                    <div class="row pt-4 mt-4 border-top text-muted small align-items-end">
                        <div class="col-sm-4 text-sm-start mb-2 mb-sm-0">
                            <div class="fw-bold text-dark">${this.escapeHtml(cert.trainer_name)}</div>
                            <div style="font-size:0.75rem;">Lead Instructor</div>
                        </div>
                        <div class="col-sm-4 text-center mb-2 mb-sm-0">
                            <div class="font-monospace fw-bold text-dark" style="font-size:0.75rem;">${this.escapeHtml(cert.certificate_code)}</div>
                            <div style="font-size:0.72rem;">Credential ID</div>
                        </div>
                        <div class="col-sm-4 text-sm-end">
                            <div class="fw-bold text-dark">${issuedDate}</div>
                            <div style="font-size:0.75rem;">Date of Issue</div>
                        </div>
                    </div>
                </div>
            `;
        } catch (err) {
            container.innerHTML = `<div class="alert alert-danger">${this.escapeHtml(err.message)}</div>`;
        }
    },

    /**
     * Print certificate container.
     */
    printCertificate() {
        window.print();
    },

    /**
     * Open official academic transcript modal.
     */
    async openTranscriptModal() {
        const modalEl = document.getElementById('academicTranscriptModal');
        const container = document.getElementById('transcriptModalBody');
        if (!modalEl || !container) return;

        container.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status"></div>
                <p class="text-muted small mt-2">Generating official transcript...</p>
            </div>
        `;

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();

        try {
            const data = await apiRequest('/certificates/transcript/');
            this._transcript = data;
            const genDate = data.generated_at ? new Date(data.generated_at).toLocaleDateString() : '';

            const rowsHtml = (data.records || []).map((r, idx) => `
                <tr>
                    <td class="ps-3">${idx + 1}</td>
                    <td class="fw-semibold text-dark">${this.escapeHtml(r.course_title)}</td>
                    <td>${this.escapeHtml(r.category)}</td>
                    <td>${r.duration_hours} hrs</td>
                    <td class="fw-bold">${(r.final_grade || 0).toFixed(1)}%</td>
                    <td><span class="badge bg-light text-dark border">${r.honors_tier}</span></td>
                    <td class="font-monospace small">${this.escapeHtml(r.certificate_code)}</td>
                </tr>
            `).join('');

            container.innerHTML = `
                <div class="p-3 bg-white" id="printableTranscriptArea">
                    <div class="d-flex justify-content-between align-items-start border-bottom pb-3 mb-3">
                        <div>
                            <h4 class="fw-bold text-dark mb-1">Official Academic Transcript</h4>
                            <div class="text-muted small">Capacity Connect Skill Platform</div>
                        </div>
                        <div class="text-end text-muted small">
                            <div>Student ID: <strong>#${data.student_id}</strong></div>
                            <div>Generated: ${genDate}</div>
                        </div>
                    </div>

                    <div class="row g-3 mb-4 p-3 bg-light rounded-3">
                        <div class="col-sm-4">
                            <span class="text-muted small">Student Name:</span>
                            <div class="fw-bold text-dark">${this.escapeHtml(data.student_name)}</div>
                        </div>
                        <div class="col-sm-4">
                            <span class="text-muted small">Email Address:</span>
                            <div class="fw-bold text-dark">${this.escapeHtml(data.student_email)}</div>
                        </div>
                        <div class="col-sm-4">
                            <span class="text-muted small">Cumulative Average:</span>
                            <div class="fw-bold text-primary fs-6">${(data.cumulative_grade_average || 0).toFixed(1)}% (${data.total_courses_completed} Courses)</div>
                        </div>
                    </div>

                    <div class="table-responsive">
                        <table class="table table-bordered table-striped align-middle small mb-0">
                            <thead class="table-light">
                                <tr>
                                    <th class="ps-3" style="width:40px;">#</th>
                                    <th>Course Title</th>
                                    <th>Category</th>
                                    <th>Hours</th>
                                    <th>Grade</th>
                                    <th>Honors</th>
                                    <th>Credential ID</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${rowsHtml || '<tr><td colspan="7" class="text-center text-muted py-4">No completed courses on record.</td></tr>'}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        } catch (err) {
            container.innerHTML = `<div class="alert alert-danger">${this.escapeHtml(err.message)}</div>`;
        }
    },

    setupFilters() {
        const searchInput = document.getElementById('certSearchInput');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this._activeSearch = e.target.value.trim();
                this.applyFiltersAndRender();
            });
        }
    },

    filterTab(filter) {
        this._activeFilter = filter;
        document.querySelectorAll('.cert-filter-tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.filter === filter);
        });
        this.applyFiltersAndRender();
    },

    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
};
