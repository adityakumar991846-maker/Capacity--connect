/**
 * Admin Dashboard Controller for Capacity Connect.
 * Manages platform-wide KPIs, course approvals, user management,
 * certificate governance, and enrollment overview.
 */
const AdminDashboard = {

    // =========================================================================
    // INITIALIZATION
    // =========================================================================

    async init() {
        this.setupEventListeners();
        await this.loadPlatformStats();
        await this.loadCourseApprovals();
    },

    // =========================================================================
    // PLATFORM STATISTICS
    // =========================================================================

    async loadPlatformStats() {
        try {
            const stats = await apiRequest('/courses/admin/platform-stats/');
            document.getElementById('statTotalUsers').textContent = stats.total_users || 0;
            document.getElementById('statTrainers').textContent = stats.total_trainers || 0;
            document.getElementById('statTrainees').textContent = stats.total_trainees || 0;
            document.getElementById('statTotalCourses').textContent = stats.total_courses || 0;
            document.getElementById('statEnrollments').textContent = stats.total_enrollments || 0;
            document.getElementById('statAvgCompletion').textContent = `${stats.platform_avg_completion || 0}%`;

            // Update pending badge
            const pendingBadge = document.getElementById('pendingApprovalsBadge');
            if (pendingBadge) pendingBadge.textContent = `${stats.draft_courses || 0} Pending`;
        } catch (err) {
            console.error('[AdminDashboard] Error loading stats:', err);
        }
    },

    // =========================================================================
    // COURSE APPROVALS
    // =========================================================================

    async loadCourseApprovals(statusFilter = '') {
        const container = document.getElementById('courseApprovalsContainer');
        if (!container) return;

        container.innerHTML = `
            <div class="text-center py-4">
                <div class="spinner-border spinner-border-sm text-primary"></div>
                <p class="text-muted small mt-2 mb-0">Loading courses...</p>
            </div>
        `;

        try {
            const url = statusFilter
                ? `/courses/admin/courses/?status=${statusFilter}`
                : '/courses/admin/courses/';
            const courses = await apiRequest(url);
            const courseList = Array.isArray(courses) ? courses : [];

            if (courseList.length === 0) {
                container.innerHTML = `
                    <div class="p-4 text-center bg-light rounded-3">
                        <i class="bi bi-check2-all fs-2 text-success mb-2 d-block"></i>
                        <h6 class="fw-bold text-dark">No Courses Found</h6>
                        <p class="text-muted small mb-0">No courses match the current filter.</p>
                    </div>
                `;
                return;
            }

            const rowsHtml = courseList.map(c => {
                const statusBadgeMap = {
                    'DRAFT': '<span class="badge bg-warning-subtle text-warning">Draft</span>',
                    'PUBLISHED': '<span class="badge bg-success-subtle text-success">Published</span>',
                    'ARCHIVED': '<span class="badge bg-secondary-subtle text-secondary">Archived</span>',
                    'REJECTED': '<span class="badge bg-danger-subtle text-danger">Rejected</span>',
                };
                const statusBadge = statusBadgeMap[c.status] || `<span class="badge bg-light text-muted">${c.status}</span>`;

                let actions = '';
                if (c.status === 'DRAFT') {
                    actions = `
                        <button class="btn btn-success btn-sm py-0 px-2 me-1" onclick="AdminDashboard.publishCourse(${c.id})" title="Approve & Publish">
                            <i class="bi bi-check-lg me-1"></i>Publish
                        </button>
                        <button class="btn btn-outline-danger btn-sm py-0 px-2" onclick="AdminDashboard.rejectCourse(${c.id})" title="Reject">
                            <i class="bi bi-x-lg me-1"></i>Reject
                        </button>
                    `;
                } else if (c.status === 'PUBLISHED') {
                    actions = `
                        <button class="btn btn-outline-secondary btn-sm py-0 px-2" onclick="AdminDashboard.archiveCourse(${c.id})" title="Archive">
                            <i class="bi bi-archive me-1"></i>Archive
                        </button>
                    `;
                } else if (c.status === 'REJECTED') {
                    actions = `
                        <button class="btn btn-success btn-sm py-0 px-2" onclick="AdminDashboard.publishCourse(${c.id})" title="Approve & Publish">
                            <i class="bi bi-check-lg me-1"></i>Publish
                        </button>
                    `;
                }

                const rejectionNote = c.rejection_reason
                    ? `<div class="text-danger small fst-italic mt-1"><i class="bi bi-exclamation-triangle me-1"></i>${this.escapeHtml(c.rejection_reason)}</div>`
                    : '';

                return `
                    <tr>
                        <td class="ps-3">
                            <div class="fw-semibold text-dark">${this.escapeHtml(c.title)}</div>
                            <div class="text-muted" style="font-size: 0.75rem;">${this.escapeHtml(c.category)} &bull; ${c.subject_count || 0} modules &bull; ${c.enrollment_count || 0} enrolled</div>
                            ${rejectionNote}
                        </td>
                        <td>${this.escapeHtml(c.trainer_username || '')}</td>
                        <td>${statusBadge}</td>
                        <td>${new Date(c.created_at).toLocaleDateString()}</td>
                        <td class="text-end pe-3">${actions}</td>
                    </tr>
                `;
            }).join('');

            container.innerHTML = `
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0 small">
                        <thead class="table-light text-secondary text-uppercase" style="font-size: 0.75rem;">
                            <tr>
                                <th class="ps-3">Course</th>
                                <th>Trainer</th>
                                <th>Status</th>
                                <th>Created</th>
                                <th class="text-end pe-3">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rowsHtml}
                        </tbody>
                    </table>
                </div>
            `;
        } catch (err) {
            console.error('[AdminDashboard] Error loading courses:', err);
            container.innerHTML = `<div class="alert alert-danger small m-3">${this.escapeHtml(err.message)}</div>`;
        }
    },

    async publishCourse(courseId) {
        if (!confirm('Are you sure you want to approve and publish this course?')) return;
        try {
            await apiRequest(`/courses/admin/courses/${courseId}/publish/`, { method: 'POST' });
            await this.loadCourseApprovals(this._activeCourseFilter || '');
            await this.loadPlatformStats();
        } catch (err) {
            alert(`Failed to publish: ${err.message}`);
        }
    },

    async rejectCourse(courseId) {
        const reason = prompt('Enter the rejection reason (required):');
        if (!reason || !reason.trim()) return;
        try {
            await apiRequest(`/courses/admin/courses/${courseId}/reject/`, {
                method: 'POST',
                body: JSON.stringify({ reason: reason.trim() }),
            });
            await this.loadCourseApprovals(this._activeCourseFilter || '');
            await this.loadPlatformStats();
        } catch (err) {
            alert(`Failed to reject: ${err.message}`);
        }
    },

    async archiveCourse(courseId) {
        if (!confirm('Are you sure you want to archive this course?')) return;
        try {
            await apiRequest(`/courses/admin/courses/${courseId}/archive/`, { method: 'POST' });
            await this.loadCourseApprovals(this._activeCourseFilter || '');
            await this.loadPlatformStats();
        } catch (err) {
            alert(`Failed to archive: ${err.message}`);
        }
    },

    _activeCourseFilter: '',

    filterCourses(status) {
        this._activeCourseFilter = status;
        // Update active tab styling
        document.querySelectorAll('.course-filter-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.status === status);
        });
        this.loadCourseApprovals(status);
    },

    // =========================================================================
    // USER MANAGEMENT
    // =========================================================================

    _activeUserRoleFilter: '',

    async loadUsers(roleFilter = '', search = '') {
        const container = document.getElementById('userRosterContainer');
        if (!container) return;

        container.innerHTML = `
            <div class="text-center py-4">
                <div class="spinner-border spinner-border-sm text-primary"></div>
                <p class="text-muted small mt-2 mb-0">Loading users...</p>
            </div>
        `;

        try {
            let url = '/auth/admin/users/';
            const params = [];
            if (roleFilter) params.push(`role=${roleFilter}`);
            if (search) params.push(`search=${encodeURIComponent(search)}`);
            if (params.length) url += '?' + params.join('&');

            const users = await apiRequest(url);
            const userList = Array.isArray(users) ? users : [];

            if (userList.length === 0) {
                container.innerHTML = `
                    <div class="p-4 text-center bg-light rounded-3">
                        <i class="bi bi-people fs-2 text-muted mb-2 d-block"></i>
                        <h6 class="fw-bold text-dark">No Users Found</h6>
                        <p class="text-muted small mb-0">No users match the current filter or search criteria.</p>
                    </div>
                `;
                return;
            }

            const rowsHtml = userList.map(u => {
                const roleBadgeMap = {
                    'ADMIN': '<span class="badge bg-danger-subtle text-danger">Admin</span>',
                    'TRAINER': '<span class="badge bg-warning-subtle text-warning">Trainer</span>',
                    'TRAINEE': '<span class="badge bg-info-subtle text-info">Trainee</span>',
                };
                const roleBadge = roleBadgeMap[u.role] || '<span class="badge bg-secondary">Unknown</span>';
                const statusBadge = u.is_active
                    ? '<span class="badge bg-success-subtle text-success">Active</span>'
                    : '<span class="badge bg-danger-subtle text-danger">Inactive</span>';

                const joinedDate = u.date_joined ? new Date(u.date_joined).toLocaleDateString() : '—';
                const lastLogin = u.last_login ? new Date(u.last_login).toLocaleDateString() : 'Never';

                let actionBtn = '';
                if (u.role !== 'ADMIN') {
                    actionBtn = u.is_active
                        ? `<button class="btn btn-outline-danger btn-sm py-0 px-2" onclick="AdminDashboard.deactivateUser(${u.id})" title="Deactivate"><i class="bi bi-person-slash"></i></button>`
                        : `<button class="btn btn-outline-success btn-sm py-0 px-2" onclick="AdminDashboard.activateUser(${u.id})" title="Activate"><i class="bi bi-person-check"></i></button>`;
                }

                return `
                    <tr>
                        <td class="ps-3">
                            <div class="fw-semibold text-dark">${this.escapeHtml(u.username)}</div>
                            <div class="text-muted" style="font-size: 0.75rem;">${this.escapeHtml(u.email)}</div>
                        </td>
                        <td>${roleBadge}</td>
                        <td>${statusBadge}</td>
                        <td>${joinedDate}</td>
                        <td>${lastLogin}</td>
                        <td class="text-end pe-3">
                            <button class="btn btn-outline-primary btn-sm py-0 px-2 me-1" onclick="AdminDashboard.openUserDetailModal(${u.id})" title="View Details"><i class="bi bi-eye"></i></button>
                            ${actionBtn}
                        </td>
                    </tr>
                `;
            }).join('');

            container.innerHTML = `
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0 small">
                        <thead class="table-light text-secondary text-uppercase" style="font-size: 0.75rem;">
                            <tr>
                                <th class="ps-3">User</th>
                                <th>Role</th>
                                <th>Status</th>
                                <th>Joined</th>
                                <th>Last Login</th>
                                <th class="text-end pe-3">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rowsHtml}
                        </tbody>
                    </table>
                </div>
            `;
        } catch (err) {
            console.error('[AdminDashboard] Error loading users:', err);
            container.innerHTML = `<div class="alert alert-danger small m-3">${this.escapeHtml(err.message)}</div>`;
        }
    },

    filterUsers(role) {
        this._activeUserRoleFilter = role;
        document.querySelectorAll('.user-filter-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.role === role);
        });
        const search = document.getElementById('userSearchInput')?.value || '';
        this.loadUsers(role, search);
    },

    handleUserSearch() {
        const search = document.getElementById('userSearchInput')?.value || '';
        this.loadUsers(this._activeUserRoleFilter, search);
    },

    async openUserDetailModal(userId) {
        const container = document.getElementById('userDetailContainer');
        if (!container) return;

        container.innerHTML = `
            <div class="text-center py-4">
                <div class="spinner-border spinner-border-sm text-primary"></div>
                <p class="text-muted small mt-2 mb-0">Loading user details...</p>
            </div>
        `;

        const modalEl = document.getElementById('userDetailModal');
        if (modalEl) {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        }

        try {
            const user = await apiRequest(`/auth/admin/users/${userId}/`);
            const roleBadgeMap = {
                'ADMIN': '<span class="badge bg-danger">Admin</span>',
                'TRAINER': '<span class="badge bg-warning text-dark">Trainer</span>',
                'TRAINEE': '<span class="badge bg-info">Trainee</span>',
            };

            container.innerHTML = `
                <div class="p-3">
                    <div class="d-flex align-items-center mb-3">
                        <div class="bg-primary-subtle text-primary rounded-circle d-flex align-items-center justify-content-center me-3" style="width:48px;height:48px;font-size:1.2rem;font-weight:bold;">
                            ${this.escapeHtml((user.username || 'U')[0].toUpperCase())}
                        </div>
                        <div>
                            <h5 class="fw-bold mb-0">${this.escapeHtml(user.username)}</h5>
                            <div class="text-muted small">${this.escapeHtml(user.email)}</div>
                        </div>
                    </div>
                    <div class="row g-3 mb-3">
                        <div class="col-6">
                            <div class="text-muted small">Role</div>
                            <div>${roleBadgeMap[user.role] || user.role}</div>
                        </div>
                        <div class="col-6">
                            <div class="text-muted small">Account Status</div>
                            <div>${user.is_active ? '<span class="text-success fw-semibold">Active</span>' : '<span class="text-danger fw-semibold">Inactive</span>'}</div>
                        </div>
                        <div class="col-6">
                            <div class="text-muted small">Date Joined</div>
                            <div class="fw-semibold">${user.date_joined ? new Date(user.date_joined).toLocaleDateString() : '—'}</div>
                        </div>
                        <div class="col-6">
                            <div class="text-muted small">Last Login</div>
                            <div class="fw-semibold">${user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}</div>
                        </div>
                    </div>
                    <hr>
                    <div class="row g-3 text-center">
                        <div class="col-4">
                            <div class="fs-4 fw-bold text-primary">${user.courses_count || 0}</div>
                            <div class="text-muted small">Courses Created</div>
                        </div>
                        <div class="col-4">
                            <div class="fs-4 fw-bold text-success">${user.enrollments_count || 0}</div>
                            <div class="text-muted small">Enrollments</div>
                        </div>
                        <div class="col-4">
                            <div class="fs-4 fw-bold text-warning">${user.certificates_count || 0}</div>
                            <div class="text-muted small">Certificates</div>
                        </div>
                    </div>
                </div>
            `;
        } catch (err) {
            console.error('[AdminDashboard] Error loading user detail:', err);
            container.innerHTML = `<div class="alert alert-danger small m-3">${this.escapeHtml(err.message)}</div>`;
        }
    },

    async deactivateUser(userId) {
        if (!confirm('Are you sure you want to deactivate this user?')) return;
        try {
            await apiRequest(`/auth/admin/users/${userId}/deactivate/`, { method: 'POST' });
            await this.loadUsers(this._activeUserRoleFilter, document.getElementById('userSearchInput')?.value || '');
            await this.loadPlatformStats();
        } catch (err) {
            alert(`Failed to deactivate: ${err.message}`);
        }
    },

    async activateUser(userId) {
        if (!confirm('Are you sure you want to reactivate this user?')) return;
        try {
            await apiRequest(`/auth/admin/users/${userId}/activate/`, { method: 'POST' });
            await this.loadUsers(this._activeUserRoleFilter, document.getElementById('userSearchInput')?.value || '');
            await this.loadPlatformStats();
        } catch (err) {
            alert(`Failed to activate: ${err.message}`);
        }
    },

    // =========================================================================
    // CERTIFICATE MANAGEMENT
    // =========================================================================

    async loadCertificates(search = '') {
        const container = document.getElementById('certificateManagementContainer');
        if (!container) return;

        container.innerHTML = `
            <div class="text-center py-4">
                <div class="spinner-border spinner-border-sm text-primary"></div>
                <p class="text-muted small mt-2 mb-0">Loading certificates...</p>
            </div>
        `;

        try {
            let url = '/certificates/admin/all/';
            if (search) url += `?search=${encodeURIComponent(search)}`;

            const certs = await apiRequest(url);
            const certList = Array.isArray(certs) ? certs : [];

            if (certList.length === 0) {
                container.innerHTML = `
                    <div class="p-4 text-center bg-light rounded-3">
                        <i class="bi bi-award fs-2 text-muted mb-2 d-block"></i>
                        <h6 class="fw-bold text-dark">No Certificates Found</h6>
                        <p class="text-muted small mb-0">No certificates match the search criteria.</p>
                    </div>
                `;
                return;
            }

            const rowsHtml = certList.map(c => {
                const statusBadge = c.is_revoked
                    ? '<span class="badge bg-danger-subtle text-danger">Revoked</span>'
                    : '<span class="badge bg-success-subtle text-success">Valid</span>';

                const actionBtn = c.is_revoked
                    ? `<button class="btn btn-outline-success btn-sm py-0 px-2" onclick="AdminDashboard.reinstateCertificate(${c.id})" title="Reinstate"><i class="bi bi-arrow-counterclockwise me-1"></i>Reinstate</button>`
                    : `<button class="btn btn-outline-danger btn-sm py-0 px-2" onclick="AdminDashboard.revokeCertificate(${c.id})" title="Revoke"><i class="bi bi-x-circle me-1"></i>Revoke</button>`;

                return `
                    <tr>
                        <td class="ps-3"><code class="text-primary fw-semibold">${this.escapeHtml(c.certificate_code)}</code></td>
                        <td>
                            <div class="fw-semibold">${this.escapeHtml(c.trainee_username)}</div>
                            <div class="text-muted" style="font-size:0.75rem;">${this.escapeHtml(c.trainee_email)}</div>
                        </td>
                        <td>${this.escapeHtml(c.course_title)}</td>
                        <td>${c.issued_at ? new Date(c.issued_at).toLocaleDateString() : '—'}</td>
                        <td>${statusBadge}</td>
                        <td class="text-end pe-3">${actionBtn}</td>
                    </tr>
                `;
            }).join('');

            container.innerHTML = `
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0 small">
                        <thead class="table-light text-secondary text-uppercase" style="font-size: 0.75rem;">
                            <tr>
                                <th class="ps-3">Code</th>
                                <th>Recipient</th>
                                <th>Course</th>
                                <th>Issued</th>
                                <th>Status</th>
                                <th class="text-end pe-3">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rowsHtml}
                        </tbody>
                    </table>
                </div>
            `;
        } catch (err) {
            console.error('[AdminDashboard] Error loading certificates:', err);
            container.innerHTML = `<div class="alert alert-danger small m-3">${this.escapeHtml(err.message)}</div>`;
        }
    },

    handleCertificateSearch() {
        const search = document.getElementById('certificateSearchInput')?.value || '';
        this.loadCertificates(search);
    },

    async revokeCertificate(certId) {
        const reason = prompt('Enter the revocation reason (required):');
        if (!reason || !reason.trim()) return;
        try {
            await apiRequest(`/certificates/${certId}/revoke/`, {
                method: 'POST',
                body: JSON.stringify({ reason: reason.trim() }),
            });
            await this.loadCertificates(document.getElementById('certificateSearchInput')?.value || '');
            await this.loadPlatformStats();
        } catch (err) {
            alert(`Failed to revoke: ${err.message}`);
        }
    },

    async reinstateCertificate(certId) {
        if (!confirm('Are you sure you want to reinstate this certificate?')) return;
        try {
            await apiRequest(`/certificates/${certId}/reinstate/`, { method: 'POST' });
            await this.loadCertificates(document.getElementById('certificateSearchInput')?.value || '');
            await this.loadPlatformStats();
        } catch (err) {
            alert(`Failed to reinstate: ${err.message}`);
        }
    },

    // =========================================================================
    // ENROLLMENT OVERVIEW
    // =========================================================================

    _activeEnrollmentFilter: '',

    async loadEnrollments(statusFilter = '') {
        const container = document.getElementById('enrollmentOverviewContainer');
        if (!container) return;

        container.innerHTML = `
            <div class="text-center py-4">
                <div class="spinner-border spinner-border-sm text-primary"></div>
                <p class="text-muted small mt-2 mb-0">Loading enrollments...</p>
            </div>
        `;

        try {
            let url = '/enrollments/admin/all/';
            if (statusFilter) url += `?status=${statusFilter}`;

            const enrollments = await apiRequest(url);
            const enrollList = Array.isArray(enrollments) ? enrollments : [];

            if (enrollList.length === 0) {
                container.innerHTML = `
                    <div class="p-4 text-center bg-light rounded-3">
                        <i class="bi bi-journal-bookmark fs-2 text-muted mb-2 d-block"></i>
                        <h6 class="fw-bold text-dark">No Enrollments Found</h6>
                        <p class="text-muted small mb-0">No enrollments match the current filter.</p>
                    </div>
                `;
                return;
            }

            const rowsHtml = enrollList.map(e => {
                const statusBadgeMap = {
                    'ENROLLED': '<span class="badge bg-primary-subtle text-primary">In Progress</span>',
                    'COMPLETED': '<span class="badge bg-success-subtle text-success">Completed</span>',
                    'DROPPED': '<span class="badge bg-secondary-subtle text-secondary">Dropped</span>',
                };
                const statusBadge = statusBadgeMap[e.status] || e.status;
                const progress = parseFloat(e.progress_percentage) || 0;

                return `
                    <tr>
                        <td class="ps-3">
                            <div class="fw-semibold">${this.escapeHtml(e.trainee_username)}</div>
                            <div class="text-muted" style="font-size:0.75rem;">${this.escapeHtml(e.trainee_email)}</div>
                        </td>
                        <td>${this.escapeHtml(e.course_title)}</td>
                        <td>${statusBadge}</td>
                        <td style="min-width:120px;">
                            <div class="d-flex justify-content-between small mb-1">
                                <span class="text-muted">Progress</span>
                                <strong>${progress}%</strong>
                            </div>
                            <div class="progress" style="height:5px;">
                                <div class="progress-bar ${e.status === 'COMPLETED' ? 'bg-success' : 'bg-primary'}" style="width:${progress}%;"></div>
                            </div>
                        </td>
                        <td>${e.enrolled_at ? new Date(e.enrolled_at).toLocaleDateString() : '—'}</td>
                    </tr>
                `;
            }).join('');

            container.innerHTML = `
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0 small">
                        <thead class="table-light text-secondary text-uppercase" style="font-size: 0.75rem;">
                            <tr>
                                <th class="ps-3">Trainee</th>
                                <th>Course</th>
                                <th>Status</th>
                                <th>Progress</th>
                                <th>Enrolled</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rowsHtml}
                        </tbody>
                    </table>
                </div>
            `;
        } catch (err) {
            console.error('[AdminDashboard] Error loading enrollments:', err);
            container.innerHTML = `<div class="alert alert-danger small m-3">${this.escapeHtml(err.message)}</div>`;
        }
    },

    filterEnrollments(status) {
        this._activeEnrollmentFilter = status;
        document.querySelectorAll('.enrollment-filter-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.status === status);
        });
        this.loadEnrollments(status);
    },

    // =========================================================================
    // EVENT LISTENERS
    // =========================================================================

    setupEventListeners() {
        // User search
        const userSearch = document.getElementById('userSearchInput');
        if (userSearch) {
            let debounce;
            userSearch.addEventListener('input', () => {
                clearTimeout(debounce);
                debounce = setTimeout(() => this.handleUserSearch(), 300);
            });
        }

        // Certificate search
        const certSearch = document.getElementById('certificateSearchInput');
        if (certSearch) {
            let debounce;
            certSearch.addEventListener('input', () => {
                clearTimeout(debounce);
                debounce = setTimeout(() => this.handleCertificateSearch(), 300);
            });
        }

        // Tab navigation
        document.querySelectorAll('.admin-section-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                const section = tab.dataset.section;
                this.showSection(section);
            });
        });
    },

    showSection(section) {
        // Hide all sections
        document.querySelectorAll('.admin-panel-section').forEach(s => s.classList.add('d-none'));
        // Show target section
        const target = document.getElementById(`section-${section}`);
        if (target) target.classList.remove('d-none');
        // Update tab styling
        document.querySelectorAll('.admin-section-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.section === section);
        });

        // Lazy load data for each section
        if (section === 'users') this.loadUsers();
        if (section === 'certificates') this.loadCertificates();
        if (section === 'enrollments') this.loadEnrollments();
        if (section === 'courses') this.loadCourseApprovals(this._activeCourseFilter || '');
    },

    // =========================================================================
    // UTILITY
    // =========================================================================

    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
};

window.AdminDashboard = AdminDashboard;
