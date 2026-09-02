/**
 * Capacity Connect — My Courses Controller (my-courses.js)
 *
 * Handles trainee enrolled courses portfolio, status tab filtering
 * (All, In Progress, Completed), search, progress display, and navigation to learning workspace.
 */

'use strict';

const MyCoursesController = {
    _enrollments: [],
    _activeTab: 'ALL',
    _activeSearch: '',

    /**
     * Initializes the My Courses page.
     */
    async init() {
        await this.loadEnrollments();
        this.setupFilters();
    },

    /**
     * Fetch trainee enrollments from backend API.
     */
    async loadEnrollments() {
        const grid = document.getElementById('myCoursesGrid');
        const emptyState = document.getElementById('myCoursesEmptyState');
        const errorState = document.getElementById('myCoursesErrorState');

        if (errorState) errorState.classList.add('d-none');
        if (emptyState) emptyState.classList.add('d-none');
        if (grid) {
            grid.innerHTML = this.renderSkeletons(4);
            grid.classList.remove('d-none');
        }

        try {
            const data = await TraineeLearning.fetchMyEnrollments();
            this._enrollments = (Array.isArray(data) ? data : []).filter(e => e.status !== 'DROPPED');

            this.updateTabCounts();
            this.applyFiltersAndRender();

            // Update sidebar badge
            const sidebarCount = document.getElementById('sidebarMyCoursesCount');
            if (sidebarCount) {
                sidebarCount.textContent = this._enrollments.length;
            }

        } catch (err) {
            console.error('[MyCourses] Error loading enrollments:', err);
            if (grid) grid.classList.add('d-none');
            if (errorState) {
                errorState.classList.remove('d-none');
                const msgEl = errorState.querySelector('.error-message');
                if (msgEl) msgEl.textContent = err.message || 'Unable to load your enrollments.';
            }
        }
    },

    /**
     * Update tab count badges.
     */
    updateTabCounts() {
        const allCount = this._enrollments.length;
        const inProgressCount = this._enrollments.filter(e => e.status === 'ENROLLED').length;
        const completedCount = this._enrollments.filter(e => e.status === 'COMPLETED').length;

        const elAll = document.getElementById('tabCountAll');
        const elInProgress = document.getElementById('tabCountInProgress');
        const elCompleted = document.getElementById('tabCountCompleted');

        if (elAll) elAll.textContent = allCount;
        if (elInProgress) elInProgress.textContent = inProgressCount;
        if (elCompleted) elCompleted.textContent = completedCount;
    },

    /**
     * Set up tab switching and search input listeners.
     */
    setupFilters() {
        // Tab buttons
        document.querySelectorAll('.cc-status-tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                document.querySelectorAll('.cc-status-tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this._activeTab = btn.getAttribute('data-status') || 'ALL';
                this.applyFiltersAndRender();
            });
        });

        // Search input
        const searchInput = document.getElementById('myCoursesSearchInput');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this._activeSearch = e.target.value.trim().toLowerCase();
                this.applyFiltersAndRender();
            });
        }
    },

    /**
     * Filter enrollments by active tab and search query, then render cards.
     */
    applyFiltersAndRender() {
        const grid = document.getElementById('myCoursesGrid');
        const emptyState = document.getElementById('myCoursesEmptyState');
        if (!grid) return;

        const filtered = this._enrollments.filter(enrollment => {
            // Status Tab Filter
            if (this._activeTab === 'ENROLLED' && enrollment.status !== 'ENROLLED') {
                return false;
            }
            if (this._activeTab === 'COMPLETED' && enrollment.status !== 'COMPLETED') {
                return false;
            }

            // Search Query
            if (this._activeSearch) {
                const courseTitle = (enrollment.course && enrollment.course.title || '').toLowerCase();
                const category = (enrollment.course && enrollment.course.category || '').toLowerCase();
                if (!courseTitle.includes(this._activeSearch) && !category.includes(this._activeSearch)) {
                    return false;
                }
            }

            return true;
        });

        if (filtered.length === 0) {
            grid.innerHTML = '';
            grid.classList.add('d-none');
            if (emptyState) {
                emptyState.classList.remove('d-none');
                const titleEl = emptyState.querySelector('.empty-title');
                const msgEl = emptyState.querySelector('.empty-message');

                if (this._enrollments.length === 0) {
                    if (titleEl) titleEl.textContent = 'No Enrolled Courses';
                    if (msgEl) msgEl.textContent = 'You have not enrolled in any courses yet. Browse the catalog to start building your skills.';
                } else {
                    if (titleEl) titleEl.textContent = 'No Matching Courses';
                    if (msgEl) msgEl.textContent = 'No enrolled courses match your current search or tab filter.';
                }
            }
            return;
        }

        if (emptyState) emptyState.classList.add('d-none');
        grid.classList.remove('d-none');
        grid.innerHTML = filtered.map(enrollment => this.renderEnrollmentCard(enrollment)).join('');
    },

    /**
     * Render individual enrollment card markup.
     * @param {object} enrollment
     * @returns {string}
     */
    renderEnrollmentCard(enrollment) {
        const course = enrollment.course || {};
        const isCompleted = enrollment.status === 'COMPLETED';
        const progress = parseFloat(enrollment.progress_percentage) || 0;
        const trainerName = course.trainer_username || (course.trainer && course.trainer.username) || 'Staff Trainer';

        const levelClass = course.level === 'BEGINNER' ? 'cc-level-beginner' :
                          (course.level === 'INTERMEDIATE' ? 'cc-level-intermediate' : 'cc-level-advanced');

        return `
            <div class="col-md-6 col-xl-4">
                <div class="cc-course-card">
                    <div class="cc-course-card-body">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <span class="badge bg-secondary-subtle text-secondary px-2 py-1 small fw-semibold">
                                <i class="bi bi-tag-fill me-1"></i>${TraineeLearning.escapeHtml(course.category || 'General')}
                            </span>
                            <span class="badge ${isCompleted ? 'bg-success text-white' : 'bg-primary-subtle text-primary'} px-2 py-1 small fw-semibold">
                                <i class="bi ${isCompleted ? 'bi-check-circle-fill' : 'bi-play-circle-fill'} me-1"></i>
                                ${isCompleted ? 'Completed' : 'In Progress'}
                            </span>
                        </div>

                        <h5 class="fw-bold text-dark mb-2 text-truncate" title="${TraineeLearning.escapeHtml(course.title)}">
                            ${TraineeLearning.escapeHtml(course.title)}
                        </h5>

                        <div class="d-flex align-items-center text-muted small mb-3">
                            <span class="cc-course-badge-level ${levelClass} me-2">
                                ${TraineeLearning.escapeHtml(course.level || 'Beginner')}
                            </span>
                            <i class="bi bi-person me-1 text-primary"></i>
                            <span class="text-truncate">${TraineeLearning.escapeHtml(trainerName)}</span>
                        </div>

                        <!-- Progress Bar Section -->
                        <div class="mt-auto pt-3">
                            <div class="d-flex justify-content-between small text-muted mb-1">
                                <span>Progress</span>
                                <strong class="text-dark">${progress}%</strong>
                            </div>
                            <div class="cc-progress">
                                <div class="cc-progress-bar ${isCompleted ? 'completed' : ''}" style="width: ${progress}%;"></div>
                            </div>
                        </div>
                    </div>

                    <div class="cc-course-card-footer d-flex gap-2">
                        <a href="course-learn.html?enrollment_id=${enrollment.id}" class="btn btn-primary btn-sm flex-fill fw-semibold">
                            <i class="bi bi-play-circle-fill me-1"></i>${isCompleted ? 'Review Modules' : 'Continue Learning'}
                        </a>
                        <a href="course-details.html?id=${course.id}" class="btn btn-outline-secondary btn-sm" title="View Course Details">
                            <i class="bi bi-info-circle"></i>
                        </a>
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Render skeleton cards during loading.
     * @param {number} count
     * @returns {string}
     */
    renderSkeletons(count = 4) {
        let html = '';
        for (let i = 0; i < count; i++) {
            html += `
                <div class="col-md-6 col-xl-4">
                    <div class="cc-skeleton-card">
                        <div class="d-flex justify-content-between mb-3">
                            <div class="cc-skeleton" style="width: 80px; height: 20px;"></div>
                            <div class="cc-skeleton" style="width: 70px; height: 20px;"></div>
                        </div>
                        <div class="cc-skeleton cc-skeleton-title"></div>
                        <div class="cc-skeleton cc-skeleton-text" style="width: 60%;"></div>
                        <div class="cc-skeleton cc-skeleton-text mt-4" style="height: 10px;"></div>
                    </div>
                </div>
            `;
        }
        return html;
    }
};

window.MyCoursesController = MyCoursesController;
