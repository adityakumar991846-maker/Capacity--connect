/**
 * Capacity Connect — Trainer Studio & Course Management Controller (trainer-dashboard.js)
 *
 * Orchestrates:
 * - Real-time KPI synchronization (courses authored, active enrollments, pass rates)
 * - Course Catalog CRUD (create, edit, delete draft courses)
 * - Subject / Module Builder (add, edit, delete, reorder course modules)
 * - Student Enrollment Roster inspection per course
 *
 * Communicates with backend REST API via authenticated apiRequest() using Supabase Bearer tokens.
 */

'use strict';

const TrainerStudio = {
    _courses: [],
    _currentEditingCourseId: null,
    _activeSubjectCourseId: null,

    /**
     * Initializes the Trainer Dashboard space.
     */
    async init() {
        try {
            await Dashboard.init('TRAINER');
            await this.loadDashboardStats();
            await this.loadMyCourses();
            this.setupEventListeners();
        } catch (err) {
            console.error('[TrainerStudio] Initialization error:', err);
            this.showGlobalAlert('Failed to load trainer dashboard. Please refresh.', 'danger');
        }
    },

    /**
     * Fetch aggregate statistics for the trainer.
     */
    async loadDashboardStats() {
        try {
            const stats = await apiRequest('/courses/trainer/dashboard-stats/');
            this.renderStats(stats);
        } catch (err) {
            console.error('[TrainerStudio] Error fetching dashboard stats:', err);
        }
    },

    /**
     * Populates all KPI counters across the page.
     */
    renderStats(stats) {
        const totalCoursesEl = document.getElementById('statTotalCourses');
        const totalTraineesEl = document.getElementById('statTotalTrainees');
        const activeCoursesEl = document.getElementById('statActiveCourses');
        const avgCompletionEl = document.getElementById('statAvgCompletion');
        const sidebarCoursesCountEl = document.getElementById('sidebarCoursesCount');

        if (totalCoursesEl) totalCoursesEl.textContent = stats.total_courses ?? 0;
        if (totalTraineesEl) totalTraineesEl.textContent = stats.total_enrollments ?? 0;
        if (activeCoursesEl) activeCoursesEl.textContent = stats.published_courses ?? 0;
        if (avgCompletionEl) avgCompletionEl.textContent = `${stats.average_progress ?? 0}%`;
        if (sidebarCoursesCountEl) sidebarCoursesCountEl.textContent = stats.total_courses ?? 0;
    },

    /**
     * Fetch all courses authored by the current trainer.
     */
    async loadMyCourses() {
        const container = document.getElementById('courseCatalogContainer');
        if (!container) return;

        try {
            container.innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border spinner-border-sm text-primary mb-2" role="status"></div>
                    <p class="text-muted small mb-0">Loading course catalog...</p>
                </div>
            `;

            const courses = await apiRequest('/courses/trainer/my-courses/');
            this._courses = Array.isArray(courses) ? courses : [];
            this.renderCourseCatalog(this._courses);
        } catch (err) {
            console.error('[TrainerStudio] Error loading courses:', err);
            container.innerHTML = `
                <div class="alert alert-danger small m-3">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>Failed to load courses: ${this.escapeHtml(err.message)}
                </div>
            `;
        }
    },

    /**
     * Renders the trainer's course catalog table or empty state.
     */
    renderCourseCatalog(courses) {
        const container = document.getElementById('courseCatalogContainer');
        if (!container) return;

        if (courses.length === 0) {
            container.innerHTML = `
                <div class="p-5 text-center bg-light rounded-3">
                    <div class="bg-warning-subtle text-warning rounded-circle d-inline-flex align-items-center justify-content-center p-3 mb-3">
                        <i class="bi bi-journal-plus fs-2 text-dark"></i>
                    </div>
                    <h5 class="fw-bold text-dark mb-1">No Courses Created Yet</h5>
                    <p class="text-muted small mb-3">Start empowering trainees by authoring your first training course module.</p>
                    <button class="btn btn-primary btn-sm px-3 rounded-2" onclick="TrainerStudio.openCreateCourseModal()">
                        <i class="bi bi-plus-circle me-1"></i>Create First Course
                    </button>
                </div>
            `;
            return;
        }

        const rowsHtml = courses.map(course => {
            const statusBadgeClass = course.status === 'PUBLISHED'
                ? 'bg-success text-white'
                : (course.status === 'ARCHIVED' ? 'bg-secondary text-white' : 'bg-warning text-dark');

            const levelBadgeClass = course.level === 'ADVANCED'
                ? 'bg-danger-subtle text-danger'
                : (course.level === 'INTERMEDIATE' ? 'bg-primary-subtle text-primary' : 'bg-success-subtle text-success');

            const avgProg = parseFloat(course.average_progress) || 0;

            return `
                <tr>
                    <td class="ps-3">
                        <div class="fw-bold text-dark">${this.escapeHtml(course.title)}</div>
                        <div class="text-muted small">${this.escapeHtml(course.category || 'General')} &bull; ${course.duration_hours || 0} hrs</div>
                    </td>
                    <td>
                        <span class="badge ${levelBadgeClass} fw-semibold">${course.level}</span>
                    </td>
                    <td>
                        <span class="badge ${statusBadgeClass} fw-semibold">${course.status}</span>
                    </td>
                    <td>
                        <span class="badge bg-light text-dark border">
                            <i class="bi bi-layers me-1 text-primary"></i>${course.subject_count} Modules
                        </span>
                    </td>
                    <td>
                        <div class="small fw-semibold text-dark mb-1">${course.enrollment_count} Students</div>
                        <div class="progress" style="height: 5px; width: 100px;">
                            <div class="progress-bar bg-success" role="progressbar" style="width: ${avgProg}%;"></div>
                        </div>
                    </td>
                    <td class="text-end pe-3">
                        <div class="dropdown">
                            <button class="btn btn-light btn-sm rounded-2 border-0" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                                <i class="bi bi-three-dots-vertical"></i>
                            </button>
                            <ul class="dropdown-menu dropdown-menu-end shadow-sm border-0 small">
                                <li>
                                    <a class="dropdown-item" href="#" onclick="TrainerStudio.openSubjectManagerModal(${course.id}); return false;">
                                        <i class="bi bi-list-nested me-2 text-primary"></i>Manage Modules (${course.subject_count})
                                    </a>
                                </li>
                                <li>
                                    <a class="dropdown-item" href="#" onclick="TrainerStudio.openAssessmentManagerModal(${course.id}, '${this.escapeHtml(course.title)}'); return false;">
                                        <i class="bi bi-patch-question me-2 text-warning"></i>Manage Assessments
                                    </a>
                                </li>
                                <li>
                                    <a class="dropdown-item" href="#" onclick="TrainerStudio.openRosterModal(${course.id}, '${this.escapeHtml(course.title)}'); return false;">
                                        <i class="bi bi-people me-2 text-info"></i>Student Roster (${course.enrollment_count})
                                    </a>
                                </li>
                                <li>
                                    <a class="dropdown-item" href="#" onclick="TrainerStudio.openCourseCertificatesModal(${course.id}, '${this.escapeHtml(course.title)}'); return false;">
                                        <i class="bi bi-award me-2 text-success"></i>Issued Certificates
                                    </a>
                                </li>
                                <li><hr class="dropdown-divider"></li>
                                <li>
                                    <a class="dropdown-item" href="#" onclick="TrainerStudio.openEditCourseModal(${course.id}); return false;">
                                        <i class="bi bi-pencil me-2 text-secondary"></i>Edit Details
                                    </a>
                                </li>
                                ${course.status !== 'PUBLISHED' ? `
                                <li>
                                    <a class="dropdown-item text-danger" href="#" onclick="TrainerStudio.confirmDeleteCourse(${course.id}); return false;">
                                        <i class="bi bi-trash me-2"></i>Delete Draft
                                    </a>
                                </li>
                                ` : ''}
                            </ul>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        container.innerHTML = `
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <thead class="table-light text-secondary small text-uppercase">
                        <tr>
                            <th class="ps-3">Course Title</th>
                            <th>Level</th>
                            <th>Status</th>
                            <th>Curriculum</th>
                            <th>Enrollment & Progress</th>
                            <th class="text-end pe-3">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rowsHtml}
                    </tbody>
                </table>
            </div>
        `;
    },

    /**
     * Opens the modal to create a new course.
     */
    openCreateCourseModal() {
        this._currentEditingCourseId = null;
        const form = document.getElementById('courseForm');
        if (form) form.reset();

        const titleEl = document.getElementById('courseModalTitle');
        if (titleEl) titleEl.textContent = 'Create New Course';

        const submitBtn = document.getElementById('courseModalSubmitBtn');
        if (submitBtn) submitBtn.textContent = 'Create Course';

        const modalEl = document.getElementById('courseModal');
        if (modalEl) {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        }
    },

    /**
     * Opens the modal to edit an existing course.
     */
    openEditCourseModal(courseId) {
        const course = this._courses.find(c => c.id === courseId);
        if (!course) return;

        this._currentEditingCourseId = courseId;
        const form = document.getElementById('courseForm');
        if (!form) return;

        document.getElementById('courseInputTitle').value = course.title || '';
        document.getElementById('courseInputCategory').value = course.category || '';
        document.getElementById('courseInputLevel').value = course.level || 'BEGINNER';
        document.getElementById('courseInputDuration').value = course.duration_hours || 10;
        document.getElementById('courseInputDescription').value = course.description || '';
        document.getElementById('courseInputLearningObjectives').value = course.learning_objectives || '';
        document.getElementById('courseInputRequirements').value = course.requirements || '';

        const titleEl = document.getElementById('courseModalTitle');
        if (titleEl) titleEl.textContent = 'Edit Course Details';

        const submitBtn = document.getElementById('courseModalSubmitBtn');
        if (submitBtn) submitBtn.textContent = 'Save Changes';

        const modalEl = document.getElementById('courseModal');
        if (modalEl) {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        }
    },

    /**
     * Handles Course form submission (Create or Update).
     */
    async handleCourseSubmit(e) {
        e.preventDefault();
        const submitBtn = document.getElementById('courseModalSubmitBtn');
        if (submitBtn) submitBtn.disabled = true;

        const title = document.getElementById('courseInputTitle').value.trim();
        const category = document.getElementById('courseInputCategory').value.trim();
        const level = document.getElementById('courseInputLevel').value;
        const duration_hours = parseInt(document.getElementById('courseInputDuration').value, 10);
        const description = document.getElementById('courseInputDescription').value.trim();
        const learning_objectives = document.getElementById('courseInputLearningObjectives').value.trim();
        const requirements = document.getElementById('courseInputRequirements').value.trim();

        if (!title || !category || !duration_hours || !description) {
            alert('Please fill in all required fields.');
            if (submitBtn) submitBtn.disabled = false;
            return;
        }

        const payload = {
            title,
            category,
            level,
            duration_hours,
            description,
            learning_objectives,
            requirements,
            status: 'DRAFT',
        };

        try {
            if (this._currentEditingCourseId) {
                await apiRequest(`/courses/${this._currentEditingCourseId}/`, {
                    method: 'PATCH',
                    body: JSON.stringify(payload),
                });
                this.showGlobalAlert('Course updated successfully.', 'success');
            } else {
                await apiRequest('/courses/', {
                    method: 'POST',
                    body: JSON.stringify(payload),
                });
                this.showGlobalAlert('Course draft created successfully! Add modules below.', 'success');
            }

            const modalEl = document.getElementById('courseModal');
            if (modalEl) {
                const modal = bootstrap.Modal.getInstance(modalEl);
                if (modal) modal.hide();
            }

            await this.loadDashboardStats();
            await this.loadMyCourses();
        } catch (err) {
            console.error('[TrainerStudio] Error saving course:', err);
            alert(`Error saving course: ${err.message}`);
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    },

    /**
     * Deletes a draft course after confirmation.
     */
    async confirmDeleteCourse(courseId) {
        if (!confirm('Are you sure you want to delete this course draft? This cannot be undone.')) {
            return;
        }

        try {
            await apiRequest(`/courses/${courseId}/`, { method: 'DELETE' });
            this.showGlobalAlert('Course deleted.', 'info');
            await this.loadDashboardStats();
            await this.loadMyCourses();
        } catch (err) {
            console.error('[TrainerStudio] Error deleting course:', err);
            alert(`Failed to delete course: ${err.message}`);
        }
    },

    /**
     * Opens the Subject / Module Builder modal for a course.
     */
    async openSubjectManagerModal(courseId) {
        this._activeSubjectCourseId = courseId;
        const course = this._courses.find(c => c.id === courseId);
        const courseTitle = course ? course.title : 'Course';

        const titleEl = document.getElementById('subjectModalCourseTitle');
        if (titleEl) titleEl.textContent = `Curriculum Builder: ${courseTitle}`;

        const modalEl = document.getElementById('subjectManagerModal');
        if (modalEl) {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        }

        await this.loadCourseSubjects(courseId);
    },

    /**
     * Loads and renders subjects list inside the Subject Manager modal.
     */
    async loadCourseSubjects(courseId) {
        const listContainer = document.getElementById('subjectListContainer');
        if (!listContainer) return;

        listContainer.innerHTML = `
            <div class="text-center py-3">
                <div class="spinner-border spinner-border-sm text-primary"></div>
            </div>
        `;

        try {
            const subjects = await apiRequest(`/courses/${courseId}/subjects/`);
            const subjectList = Array.isArray(subjects) ? subjects : [];

            // Auto-populate next sequence order in the Add form
            const nextOrderInput = document.getElementById('subjectInputOrder');
            if (nextOrderInput) {
                nextOrderInput.value = subjectList.length > 0
                    ? Math.max(...subjectList.map(s => s.order || 0)) + 1
                    : 1;
            }

            if (subjectList.length === 0) {
                listContainer.innerHTML = `
                    <div class="p-3 text-center bg-light rounded-3 small text-muted">
                        No modules added yet. Use the form below to add your first module.
                    </div>
                `;
                return;
            }

            listContainer.innerHTML = `
                <div class="list-group list-group-flush">
                    ${subjectList.map(subj => `
                        <div class="list-group-item d-flex justify-content-between align-items-center px-0 py-2 border-bottom">
                            <div>
                                <span class="badge bg-primary text-white me-2">Module ${subj.order}</span>
                                <strong class="text-dark">${this.escapeHtml(subj.title)}</strong>
                                ${subj.description ? `<div class="text-muted small mt-1 ms-1">${this.escapeHtml(subj.description)}</div>` : ''}
                            </div>
                            <div>
                                <button class="btn btn-outline-danger btn-sm py-0 px-2" onclick="TrainerStudio.handleDeleteSubject(${courseId}, ${subj.id})" title="Delete Module">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        } catch (err) {
            console.error('[TrainerStudio] Error loading subjects:', err);
            listContainer.innerHTML = `<div class="alert alert-danger small">${this.escapeHtml(err.message)}</div>`;
        }
    },

    /**
     * Handles adding a new subject to a course.
     */
    async handleAddSubject(e) {
        e.preventDefault();
        const courseId = this._activeSubjectCourseId;
        if (!courseId) return;

        const titleInput = document.getElementById('subjectInputTitle');
        const orderInput = document.getElementById('subjectInputOrder');
        const descInput = document.getElementById('subjectInputDescription');
        const btn = document.getElementById('btnAddSubject');

        const title = titleInput.value.trim();
        const order = parseInt(orderInput.value, 10);
        const description = descInput.value.trim();

        if (!title || isNaN(order)) {
            alert('Please provide a module title and sequence order number.');
            return;
        }

        if (btn) btn.disabled = true;

        try {
            await apiRequest(`/courses/${courseId}/subjects/`, {
                method: 'POST',
                body: JSON.stringify({
                    title,
                    order,
                    description,
                }),
            });

            titleInput.value = '';
            descInput.value = '';
            await this.loadCourseSubjects(courseId);
            await this.loadMyCourses();
        } catch (err) {
            console.error('[TrainerStudio] Error adding subject:', err);
            alert(`Failed to add module: ${err.message}`);
        } finally {
            if (btn) btn.disabled = false;
        }
    },

    /**
     * Handles deleting a subject.
     */
    async handleDeleteSubject(courseId, subjectId) {
        if (!confirm('Are you sure you want to delete this module?')) return;

        try {
            await apiRequest(`/courses/${courseId}/subjects/${subjectId}/`, { method: 'DELETE' });
            await this.loadCourseSubjects(courseId);
            await this.loadMyCourses();
        } catch (err) {
            console.error('[TrainerStudio] Error deleting subject:', err);
            alert(`Failed to delete module: ${err.message}`);
        }
    },

    /**
     * Opens the Student Enrollment Roster modal for a course.
     */
    async openRosterModal(courseId, courseTitle) {
        const titleEl = document.getElementById('rosterModalCourseTitle');
        if (titleEl) titleEl.textContent = `Student Roster: ${courseTitle}`;

        const container = document.getElementById('rosterContainer');
        if (container) {
            container.innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border spinner-border-sm text-primary"></div>
                    <p class="text-muted small mt-2 mb-0">Loading student roster...</p>
                </div>
            `;
        }

        const modalEl = document.getElementById('rosterModal');
        if (modalEl) {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        }

        try {
            const roster = await apiRequest(`/courses/trainer/courses/${courseId}/roster/`);
            const rosterList = Array.isArray(roster) ? roster : [];

            if (rosterList.length === 0) {
                container.innerHTML = `
                    <div class="p-4 text-center bg-light rounded-3">
                        <i class="bi bi-people fs-2 text-muted mb-2 d-block"></i>
                        <h6 class="fw-bold text-dark">No Enrolled Students Yet</h6>
                        <p class="text-muted small mb-0">When trainees enroll in this course, their real-time progress will appear here.</p>
                    </div>
                `;
                return;
            }

            const rowsHtml = rosterList.map(item => {
                const isCompleted = item.status === 'COMPLETED';
                const statusBadge = isCompleted
                    ? '<span class="badge bg-success">Completed</span>'
                    : '<span class="badge bg-primary-subtle text-primary">In Progress</span>';

                const enrolledDate = item.enrolled_at ? new Date(item.enrolled_at).toLocaleDateString() : '—';
                const progress = parseFloat(item.progress_percentage) || 0;

                return `
                    <tr>
                        <td class="ps-3">
                            <div class="fw-bold text-dark">${this.escapeHtml(item.username)}</div>
                            <div class="text-muted small">${this.escapeHtml(item.email)}</div>
                        </td>
                        <td>${enrolledDate}</td>
                        <td>${statusBadge}</td>
                        <td style="min-width: 140px;">
                            <div class="d-flex justify-content-between small text-muted mb-1">
                                <span>Progress</span>
                                <strong class="text-dark">${progress}%</strong>
                            </div>
                            <div class="progress" style="height: 6px;">
                                <div class="progress-bar ${isCompleted ? 'bg-success' : 'bg-primary'}" style="width: ${progress}%;"></div>
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');

            container.innerHTML = `
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0 small">
                        <thead class="table-light text-secondary text-uppercase" style="font-size: 0.75rem;">
                            <tr>
                                <th class="ps-3">Trainee</th>
                                <th>Enrolled Date</th>
                                <th>Status</th>
                                <th>Curriculum Progress</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rowsHtml}
                        </tbody>
                    </table>
                </div>
            `;
        } catch (err) {
            console.error('[TrainerStudio] Error loading roster:', err);
            container.innerHTML = `<div class="alert alert-danger small m-3">${this.escapeHtml(err.message)}</div>`;
        }
    },

    /**
     * Opens Course Certificates Roster Modal.
     */
    async openCourseCertificatesModal(courseId, courseTitle = '') {
        const titleEl = document.getElementById('certificatesModalCourseTitle');
        if (titleEl) titleEl.textContent = `Issued Certificates: ${courseTitle}`;

        const container = document.getElementById('courseCertificatesContainer');
        if (container) {
            container.innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border spinner-border-sm text-primary"></div>
                    <p class="text-muted small mt-2 mb-0">Loading issued credentials...</p>
                </div>
            `;
        }

        const modalEl = document.getElementById('courseCertificatesModal');
        if (modalEl) {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        }

        try {
            const certs = await apiRequest(`/certificates/trainer/courses/${courseId}/`);
            const certList = Array.isArray(certs) ? certs : [];

            if (certList.length === 0) {
                container.innerHTML = `
                    <div class="p-4 text-center bg-light rounded-3">
                        <i class="bi bi-award fs-2 text-muted mb-2 d-block"></i>
                        <h6 class="fw-bold text-dark">No Certificates Issued Yet</h6>
                        <p class="text-muted small mb-0">When enrolled trainees complete all course modules and pass required assessments, their verified credentials will appear here.</p>
                    </div>
                `;
                return;
            }

            const rowsHtml = certList.map(c => {
                const isRevoked = !!c.revoked_at;
                const statusBadge = isRevoked
                    ? '<span class="badge bg-danger-subtle text-danger fw-semibold"><i class="bi bi-x-circle me-1"></i>Revoked</span>'
                    : '<span class="badge bg-success-subtle text-success fw-semibold"><i class="bi bi-patch-check-fill me-1"></i>Active</span>';

                const issuedDate = c.issue_date ? new Date(c.issue_date).toLocaleDateString() : '—';
                const gradeDisplay = c.grade ? `<span class="badge bg-secondary-subtle text-secondary">${this.escapeHtml(c.grade)}</span>` : '—';

                return `
                    <tr>
                        <td class="ps-3">
                            <div class="fw-bold text-dark">${this.escapeHtml(c.trainee_name || 'Trainee')}</div>
                            <div class="text-muted small">${this.escapeHtml(c.trainee_email || '')}</div>
                        </td>
                        <td>
                            <code class="user-select-all fw-semibold text-primary">${this.escapeHtml(c.certificate_code)}</code>
                        </td>
                        <td>${issuedDate}</td>
                        <td>${gradeDisplay}</td>
                        <td>${statusBadge}</td>
                        <td class="text-end pe-3">
                            <a href="/pages/verify-certificate.html?code=${encodeURIComponent(c.certificate_code)}" target="_blank" class="btn btn-outline-primary btn-sm py-0 px-2" title="Public Verification Link">
                                <i class="bi bi-box-arrow-up-right me-1"></i>Verify
                            </a>
                        </td>
                    </tr>
                `;
            }).join('');

            container.innerHTML = `
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0 small">
                        <thead class="table-light text-secondary text-uppercase" style="font-size: 0.75rem;">
                            <tr>
                                <th class="ps-3">Recipient</th>
                                <th>Certificate Code</th>
                                <th>Issued On</th>
                                <th>Grade</th>
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
            console.error('[TrainerStudio] Error loading course certificates:', err);
            container.innerHTML = `<div class="alert alert-danger small m-3">${this.escapeHtml(err.message)}</div>`;
        }
    },

    // =========================================================================
    // ASSESSMENT STUDIO METHODS
    // =========================================================================

    _activeAssessmentCourseId: null,
    _activeAssessmentCourseTitle: '',
    _activeAssessmentId: null,
    _activeAssessmentTitle: '',

    /**
     * Opens the Assessment Studio modal for a specific course.
     */
    async openAssessmentManagerModal(courseId, courseTitle = '') {
        this._activeAssessmentCourseId = courseId;
        this._activeAssessmentCourseTitle = courseTitle || 'Course';

        const titleEl = document.getElementById('assessmentModalCourseTitle');
        if (titleEl) titleEl.textContent = `Assessments: ${courseTitle}`;

        const form = document.getElementById('createAssessmentForm');
        if (form) form.reset();

        // Populate Subject dropdown for this course
        const subjectSelect = document.getElementById('assessmentInputSubject');
        if (subjectSelect) {
            subjectSelect.innerHTML = '<option value="">Course Final Assessment (No Module)</option>';
            try {
                const subjects = await apiRequest(`/courses/${courseId}/subjects/`);
                if (Array.isArray(subjects)) {
                    subjects.forEach(s => {
                        const opt = document.createElement('option');
                        opt.value = s.id;
                        opt.textContent = `Module ${s.order}: ${s.title}`;
                        subjectSelect.appendChild(opt);
                    });
                }
            } catch (e) {
                console.warn('[TrainerStudio] Could not load subjects for assessment dropdown:', e);
            }
        }

        const modalEl = document.getElementById('assessmentManagerModal');
        if (modalEl) {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        }

        await this.loadCourseAssessments(courseId);
    },

    /**
     * Fetches and renders assessments for the active course.
     */
    async loadCourseAssessments(courseId) {
        const container = document.getElementById('assessmentListContainer');
        if (!container) return;

        try {
            container.innerHTML = `
                <div class="text-center py-3">
                    <div class="spinner-border spinner-border-sm text-primary mb-1"></div>
                    <p class="text-muted small mb-0">Loading assessments...</p>
                </div>
            `;

            const assessments = await apiRequest(`/assessments/trainer/courses/${courseId}/`);
            if (!Array.isArray(assessments) || assessments.length === 0) {
                container.innerHTML = `
                    <div class="alert alert-light border small text-muted text-center py-3 mb-0">
                        <i class="bi bi-patch-question me-1"></i>No assessments created yet for this course.
                    </div>
                `;
                return;
            }

            const rowsHtml = assessments.map(a => {
                const statusBadge = a.status === 'PUBLISHED'
                    ? '<span class="badge bg-success-subtle text-success">Published</span>'
                    : '<span class="badge bg-warning-subtle text-warning">Draft</span>';

                return `
                    <div class="d-flex align-items-center justify-content-between p-2 mb-2 bg-white rounded border shadow-sm">
                        <div>
                            <div class="fw-semibold text-dark small">${this.escapeHtml(a.title)}</div>
                            <div class="text-muted" style="font-size: 0.75rem;">
                                Pass: ${a.passing_percentage}% &bull; ${a.duration_minutes} mins &bull; ${a.question_count || 0} Questions (${a.total_marks || 0} Marks) &bull; ${statusBadge}
                            </div>
                        </div>
                        <div class="d-flex align-items-center gap-1">
                            <button class="btn btn-outline-primary btn-sm py-1 px-2" title="Manage MCQs"
                                    onclick="TrainerStudio.openQuestionBuilderModal(${a.id}, '${this.escapeHtml(a.title)}');">
                                <i class="bi bi-card-checklist me-1"></i>Questions (${a.question_count || 0})
                            </button>
                            <button class="btn btn-outline-info btn-sm py-1 px-2" title="View Results"
                                    onclick="TrainerStudio.openAssessmentResultsModal(${a.id}, '${this.escapeHtml(a.title)}');">
                                <i class="bi bi-bar-chart me-1"></i>Results (${a.attempt_count || 0})
                            </button>
                            <button class="btn btn-outline-danger btn-sm py-1 px-2" title="Delete Assessment"
                                    onclick="TrainerStudio.deleteAssessment(${a.id});">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                `;
            }).join('');

            container.innerHTML = rowsHtml;
        } catch (err) {
            console.error('[TrainerStudio] Error loading assessments:', err);
            container.innerHTML = `<div class="alert alert-danger small mb-0">${this.escapeHtml(err.message)}</div>`;
        }
    },

    /**
     * Handles creating a new assessment.
     */
    async handleCreateAssessment(e) {
        e.preventDefault();
        if (!this._activeAssessmentCourseId) return;

        const title = document.getElementById('assessmentInputTitle')?.value.trim();
        const subjectVal = document.getElementById('assessmentInputSubject')?.value;
        const passing = parseInt(document.getElementById('assessmentInputPassing')?.value, 10);
        const duration = parseInt(document.getElementById('assessmentInputDuration')?.value, 10);
        const statusVal = document.getElementById('assessmentInputStatus')?.value || 'DRAFT';
        const description = document.getElementById('assessmentInputDescription')?.value.trim();

        if (!title) return;

        const btn = document.getElementById('btnCreateAssessment');
        if (btn) btn.disabled = true;

        try {
            const payload = {
                title,
                passing_percentage: passing || 70,
                duration_minutes: duration || 30,
                status: statusVal,
                description,
            };
            if (subjectVal) {
                payload.subject = parseInt(subjectVal, 10);
            }

            await apiRequest(`/assessments/trainer/courses/${this._activeAssessmentCourseId}/`, {
                method: 'POST',
                body: JSON.stringify(payload),
            });

            document.getElementById('createAssessmentForm')?.reset();
            await this.loadCourseAssessments(this._activeAssessmentCourseId);
        } catch (err) {
            console.error('[TrainerStudio] Error creating assessment:', err);
            alert(`Failed to create assessment: ${err.message}`);
        } finally {
            if (btn) btn.disabled = false;
        }
    },

    /**
     * Deletes an assessment.
     */
    async deleteAssessment(assessmentId) {
        if (!confirm('Are you sure you want to delete this assessment? All associated questions and trainee attempts will be removed.')) {
            return;
        }

        try {
            await apiRequest(`/assessments/trainer/${assessmentId}/`, { method: 'DELETE' });
            if (this._activeAssessmentCourseId) {
                await this.loadCourseAssessments(this._activeAssessmentCourseId);
            }
        } catch (err) {
            console.error('[TrainerStudio] Error deleting assessment:', err);
            alert(`Failed to delete assessment: ${err.message}`);
        }
    },

    /**
     * Opens Question Builder Modal for an assessment.
     */
    async openQuestionBuilderModal(assessmentId, assessmentTitle = '') {
        this._activeAssessmentId = assessmentId;
        this._activeAssessmentTitle = assessmentTitle || 'Assessment';

        // Hide Assessment manager modal temporarily
        const mgrEl = document.getElementById('assessmentManagerModal');
        if (mgrEl) {
            const mgrModal = bootstrap.Modal.getInstance(mgrEl);
            if (mgrModal) mgrModal.hide();
        }

        const titleEl = document.getElementById('questionModalTitle');
        if (titleEl) titleEl.textContent = `Question Builder`;

        const subTitleEl = document.getElementById('questionModalSubtitle');
        if (subTitleEl) subTitleEl.textContent = `${assessmentTitle}`;

        const form = document.getElementById('addQuestionForm');
        if (form) form.reset();

        const modalEl = document.getElementById('questionBuilderModal');
        if (modalEl) {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        }

        await this.loadAssessmentQuestions(assessmentId);
    },

    /**
     * Returns from Question Builder back to Assessment Studio modal.
     */
    backToAssessmentManager() {
        const qEl = document.getElementById('questionBuilderModal');
        if (qEl) {
            const qModal = bootstrap.Modal.getInstance(qEl);
            if (qModal) qModal.hide();
        }

        if (this._activeAssessmentCourseId) {
            this.openAssessmentManagerModal(this._activeAssessmentCourseId, this._activeAssessmentCourseTitle);
        }
    },

    /**
     * Fetches and renders all MCQ questions in the active assessment.
     */
    async loadAssessmentQuestions(assessmentId) {
        const container = document.getElementById('questionListContainer');
        if (!container) return;

        try {
            container.innerHTML = `
                <div class="text-center py-3">
                    <div class="spinner-border spinner-border-sm text-primary mb-1"></div>
                    <p class="text-muted small mb-0">Loading questions...</p>
                </div>
            `;

            const data = await apiRequest(`/assessments/trainer/${assessmentId}/`);
            const questions = data.questions || [];

            if (questions.length === 0) {
                container.innerHTML = `
                    <div class="alert alert-light border small text-muted text-center py-3 mb-0">
                        <i class="bi bi-card-checklist me-1"></i>No questions added yet. Use the form below to add MCQs.
                    </div>
                `;
                return;
            }

            const questionsHtml = questions.map((q, idx) => {
                const getOptClass = (optKey) => optKey === q.correct_answer ? 'text-success fw-bold' : 'text-muted';

                return `
                    <div class="card border mb-3 shadow-sm rounded-3">
                        <div class="card-body p-3">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <span class="badge bg-primary-subtle text-primary">Q${q.order || (idx + 1)} (${q.marks} Mark${q.marks > 1 ? 's' : ''})</span>
                                <button class="btn btn-outline-danger btn-sm py-0 px-2" onclick="TrainerStudio.deleteQuestion(${q.id});">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </div>
                            <h6 class="fw-bold text-dark mb-2">${this.escapeHtml(q.question_text)}</h6>
                            <div class="row g-1 small mb-2">
                                <div class="col-sm-6 ${getOptClass('A')}"><strong>A:</strong> ${this.escapeHtml(q.option_a)}</div>
                                <div class="col-sm-6 ${getOptClass('B')}"><strong>B:</strong> ${this.escapeHtml(q.option_b)}</div>
                                <div class="col-sm-6 ${getOptClass('C')}"><strong>C:</strong> ${this.escapeHtml(q.option_c)}</div>
                                <div class="col-sm-6 ${getOptClass('D')}"><strong>D:</strong> ${this.escapeHtml(q.option_d)}</div>
                            </div>
                            <div class="text-success small fw-semibold">
                                <i class="bi bi-check-circle-fill me-1"></i>Correct Answer: Option ${q.correct_answer}
                            </div>
                            ${q.explanation ? `<div class="text-muted small fst-italic mt-1">Note: ${this.escapeHtml(q.explanation)}</div>` : ''}
                        </div>
                    </div>
                `;
            }).join('');

            container.innerHTML = questionsHtml;

            // Auto-increment next order in form
            const orderInput = document.getElementById('qInputOrder');
            if (orderInput) orderInput.value = questions.length + 1;

        } catch (err) {
            console.error('[TrainerStudio] Error loading questions:', err);
            container.innerHTML = `<div class="alert alert-danger small mb-0">${this.escapeHtml(err.message)}</div>`;
        }
    },

    /**
     * Handles adding a new MCQ question.
     */
    async handleAddQuestion(e) {
        e.preventDefault();
        if (!this._activeAssessmentId) return;

        const text = document.getElementById('qInputText')?.value.trim();
        const optA = document.getElementById('qInputOptionA')?.value.trim();
        const optB = document.getElementById('qInputOptionB')?.value.trim();
        const optC = document.getElementById('qInputOptionC')?.value.trim();
        const optD = document.getElementById('qInputOptionD')?.value.trim();
        const correct = document.getElementById('qInputCorrect')?.value;
        const marks = parseInt(document.getElementById('qInputMarks')?.value, 10) || 1;
        const order = parseInt(document.getElementById('qInputOrder')?.value, 10) || 1;
        const explanation = document.getElementById('qInputExplanation')?.value.trim();

        if (!text || !optA || !optB || !optC || !optD || !correct) return;

        const btn = document.getElementById('btnAddQuestion');
        if (btn) btn.disabled = true;

        try {
            await apiRequest(`/assessments/trainer/${this._activeAssessmentId}/questions/`, {
                method: 'POST',
                body: JSON.stringify({
                    question_text: text,
                    option_a: optA,
                    option_b: optB,
                    option_c: optC,
                    option_d: optD,
                    correct_answer: correct,
                    marks,
                    order,
                    explanation,
                }),
            });

            document.getElementById('addQuestionForm')?.reset();
            await this.loadAssessmentQuestions(this._activeAssessmentId);
        } catch (err) {
            console.error('[TrainerStudio] Error adding question:', err);
            alert(`Failed to add question: ${err.message}`);
        } finally {
            if (btn) btn.disabled = false;
        }
    },

    /**
     * Deletes an MCQ question.
     */
    async deleteQuestion(questionId) {
        if (!confirm('Are you sure you want to delete this question?')) return;

        try {
            await apiRequest(`/assessments/trainer/questions/${questionId}/`, { method: 'DELETE' });
            if (this._activeAssessmentId) {
                await this.loadAssessmentQuestions(this._activeAssessmentId);
            }
        } catch (err) {
            console.error('[TrainerStudio] Error deleting question:', err);
            alert(`Failed to delete question: ${err.message}`);
        }
    },

    /**
     * Opens Assessment Results Roster Modal.
     */
    async openAssessmentResultsModal(assessmentId, assessmentTitle = '') {
        const titleEl = document.getElementById('assessmentResultsModalTitle');
        if (titleEl) titleEl.textContent = `Results: ${assessmentTitle}`;

        const container = document.getElementById('assessmentResultsContainer');
        if (container) {
            container.innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border spinner-border-sm text-primary mb-2"></div>
                    <p class="text-muted small mb-0">Loading results...</p>
                </div>
            `;
        }

        const modalEl = document.getElementById('assessmentResultsModal');
        if (modalEl) {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        }

        try {
            const results = await apiRequest(`/assessments/trainer/${assessmentId}/results/`);
            if (!Array.isArray(results) || results.length === 0) {
                if (container) {
                    container.innerHTML = `
                        <div class="p-4 text-center text-muted">
                            <i class="bi bi-emoji-smile fs-3 d-block mb-2 text-secondary"></i>
                            <p class="small mb-0">No trainee attempts recorded for this assessment yet.</p>
                        </div>
                    `;
                }
                return;
            }

            const rowsHtml = results.map(r => {
                const dateStr = r.submitted_at ? new Date(r.submitted_at).toLocaleDateString() : '—';
                const passBadge = r.passed
                    ? '<span class="badge bg-success-subtle text-success fw-bold">PASS</span>'
                    : '<span class="badge bg-danger-subtle text-danger fw-bold">FAIL</span>';

                return `
                    <tr>
                        <td class="ps-3">
                            <div class="fw-semibold text-dark">${this.escapeHtml(r.trainee_username)}</div>
                            <div class="text-muted small" style="font-size: 0.75rem;">${this.escapeHtml(r.trainee_email || '')}</div>
                        </td>
                        <td>${dateStr}</td>
                        <td><strong>${r.score}</strong> / ${r.total_marks} (${r.percentage}%)</td>
                        <td>${passBadge}</td>
                    </tr>
                `;
            }).join('');

            if (container) {
                container.innerHTML = `
                    <div class="table-responsive">
                        <table class="table table-hover align-middle mb-0 small">
                            <thead class="table-light text-secondary text-uppercase" style="font-size: 0.75rem;">
                                <tr>
                                    <th class="ps-3">Trainee</th>
                                    <th>Attempt Date</th>
                                    <th>Score & %</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${rowsHtml}
                            </tbody>
                        </table>
                    </div>
                `;
            }

        } catch (err) {
            console.error('[TrainerStudio] Error loading results:', err);
            if (container) container.innerHTML = `<div class="alert alert-danger small m-3">${this.escapeHtml(err.message)}</div>`;
        }
    },

    /**
     * Displays a dismissible global alert banner on the dashboard.
     */
    showGlobalAlert(message, type = 'info') {
        const alertBox = document.getElementById('globalAlertContainer');
        if (!alertBox) return;

        alertBox.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show small shadow-sm" role="alert">
                <i class="bi ${type === 'success' ? 'bi-check-circle-fill' : 'bi-info-circle-fill'} me-2"></i>
                ${this.escapeHtml(message)}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
    },

    /**
     * Binds form submission handlers.
     */
    setupEventListeners() {
        const courseForm = document.getElementById('courseForm');
        if (courseForm) {
            courseForm.addEventListener('submit', (e) => this.handleCourseSubmit(e));
        }

        const subjectForm = document.getElementById('addSubjectForm');
        if (subjectForm) {
            subjectForm.addEventListener('submit', (e) => this.handleAddSubject(e));
        }

        const assessmentForm = document.getElementById('createAssessmentForm');
        if (assessmentForm) {
            assessmentForm.addEventListener('submit', (e) => this.handleCreateAssessment(e));
        }

        const questionForm = document.getElementById('addQuestionForm');
        if (questionForm) {
            questionForm.addEventListener('submit', (e) => this.handleAddQuestion(e));
        }
    },

    /**
     * Load student reviews and instructor quality feedback (Step 14).
     */
    async loadTrainerFeedback() {
        const container = document.getElementById('trainerFeedbackContainer');
        const badge = document.getElementById('trainerAvgRatingBadge');
        if (!container) return;

        try {
            const data = await apiRequest('/reviews/trainer/feedback/');
            const avg = data.trainer_average_rating || 0.0;
            const reviews = data.reviews || [];

            if (badge) {
                badge.textContent = `★ ${avg.toFixed(1)} (${data.total_reviews || 0})`;
            }

            if (reviews.length === 0) {
                container.innerHTML = `
                    <div class="text-center py-3 text-muted small">
                        <i class="bi bi-chat-square-heart me-1"></i>No student reviews received yet.
                    </div>
                `;
                return;
            }

            container.innerHTML = reviews.slice(0, 5).map(r => {
                const dateStr = r.created_at ? new Date(r.created_at).toLocaleDateString() : '';
                return `
                    <div class="border-bottom pb-2 mb-2 small">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="fw-bold text-dark text-truncate" style="max-width: 140px;">${this.escapeHtml(r.trainee_username)}</span>
                            <span class="text-warning fw-bold">★ ${r.rating}</span>
                        </div>
                        <div class="text-muted" style="font-size:0.75rem;">${this.escapeHtml(r.course_title)} &bull; ${dateStr}</div>
                        <p class="text-secondary mb-0 mt-1" style="font-size:0.8rem; line-height:1.4;">${this.escapeHtml(r.comment)}</p>
                    </div>
                `;
            }).join('');
        } catch (err) {
            console.debug('[TrainerStudio] Could not load trainer feedback:', err.message);
            container.innerHTML = `<div class="text-muted small">Unable to load reviews.</div>`;
        }
    },

    /**
     * XSS sanitizer helper.
     */
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

// Global export
window.TrainerStudio = TrainerStudio;
