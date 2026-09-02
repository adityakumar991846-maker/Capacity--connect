/**
 * Capacity Connect — Browse Courses Controller (browse-courses.js)
 *
 * Handles catalog display, client-side search, filtering by level and category,
 * enrollment status detection, and direct navigation to course details.
 */

'use strict';

const BrowseCoursesController = {
    _courses: [],
    _enrolledCourseIds: new Set(),
    _activeSearch: '',
    _activeCategory: 'ALL',
    _activeLevel: 'ALL',

    /**
     * Initializes the browse courses page.
     */
    async init() {
        await this.loadData();
        this.setupFilters();
    },

    /**
     * Fetch published courses and trainee enrollments in parallel.
     */
    async loadData() {
        const grid = document.getElementById('coursesGrid');
        const emptyState = document.getElementById('coursesEmptyState');
        const errorState = document.getElementById('coursesErrorState');

        if (errorState) errorState.classList.add('d-none');
        if (emptyState) emptyState.classList.add('d-none');
        if (grid) {
            grid.innerHTML = this.renderSkeletons(6);
            grid.classList.remove('d-none');
        }

        try {
            const [courses, enrollments] = await Promise.all([
                TraineeLearning.fetchPublishedCourses(),
                TraineeLearning.fetchMyEnrollments().catch(() => [])
            ]);

            this._courses = Array.isArray(courses) ? courses : [];
            this._enrolledCourseIds = new Set(
                (Array.isArray(enrollments) ? enrollments : [])
                    .filter(e => e.status !== 'DROPPED')
                    .map(e => (typeof e.course === 'object' ? e.course.id : e.course))
            );

            this.populateCategoriesDropdown();
            this.applyFiltersAndRender();

            // Update sidebar enrollments count if available
            const myCoursesCountBadge = document.getElementById('sidebarMyCoursesCount');
            if (myCoursesCountBadge) {
                myCoursesCountBadge.textContent = this._enrolledCourseIds.size;
            }
        } catch (err) {
            console.error('[BrowseCourses] Error fetching courses:', err);
            if (grid) grid.classList.add('d-none');
            if (errorState) {
                errorState.classList.remove('d-none');
                const msgEl = errorState.querySelector('.error-message');
                if (msgEl) msgEl.textContent = err.message || 'Unable to connect to course services.';
            }
        }
    },

    /**
     * Dynamically populate category filter dropdown based on available course categories.
     */
    populateCategoriesDropdown() {
        const select = document.getElementById('categoryFilter');
        if (!select) return;

        const categories = Array.from(new Set(this._courses.map(c => c.category).filter(Boolean))).sort();
        
        // Preserve "All Categories" option
        select.innerHTML = '<option value="ALL">All Categories</option>';
        categories.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat;
            opt.textContent = cat;
            select.appendChild(opt);
        });
    },

    /**
     * Setup search and filter change event listeners.
     */
    setupFilters() {
        const searchInput = document.getElementById('courseSearchInput');
        const categoryFilter = document.getElementById('categoryFilter');
        const levelFilter = document.getElementById('levelFilter');
        const resetBtn = document.getElementById('resetFiltersBtn');

        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this._activeSearch = e.target.value.trim().toLowerCase();
                this.applyFiltersAndRender();
            });
        }

        if (categoryFilter) {
            categoryFilter.addEventListener('change', (e) => {
                this._activeCategory = e.target.value;
                this.applyFiltersAndRender();
            });
        }

        if (levelFilter) {
            levelFilter.addEventListener('change', (e) => {
                this._activeLevel = e.target.value;
                this.applyFiltersAndRender();
            });
        }

        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                if (searchInput) searchInput.value = '';
                if (categoryFilter) categoryFilter.value = 'ALL';
                if (levelFilter) levelFilter.value = 'ALL';
                this._activeSearch = '';
                this._activeCategory = 'ALL';
                this._activeLevel = 'ALL';
                this.applyFiltersAndRender();
            });
        }
    },

    /**
     * Apply active search and filter constraints, then render grid.
     */
    applyFiltersAndRender() {
        const grid = document.getElementById('coursesGrid');
        const emptyState = document.getElementById('coursesEmptyState');
        const countDisplay = document.getElementById('resultsCountDisplay');
        if (!grid) return;

        const filtered = this._courses.filter(course => {
            // Level Filter
            if (this._activeLevel !== 'ALL' && course.level !== this._activeLevel) {
                return false;
            }

            // Category Filter
            if (this._activeCategory !== 'ALL' && course.category !== this._activeCategory) {
                return false;
            }

            // Text Search
            if (this._activeSearch) {
                const title = (course.title || '').toLowerCase();
                const category = (course.category || '').toLowerCase();
                const trainer = (course.trainer && course.trainer.username || '').toLowerCase();
                const matches = title.includes(this._activeSearch) ||
                                category.includes(this._activeSearch) ||
                                trainer.includes(this._activeSearch);
                if (!matches) return false;
            }

            return true;
        });

        if (countDisplay) {
            countDisplay.textContent = `Showing ${filtered.length} of ${this._courses.length} courses`;
        }

        if (filtered.length === 0) {
            grid.innerHTML = '';
            grid.classList.add('d-none');
            if (emptyState) emptyState.classList.remove('d-none');
            return;
        }

        if (emptyState) emptyState.classList.add('d-none');
        grid.classList.remove('d-none');
        grid.innerHTML = filtered.map(course => this.renderCourseCard(course)).join('');
    },

    /**
     * Render HTML markup for an individual course card.
     * @param {object} course
     * @returns {string} HTML markup
     */
    renderCourseCard(course) {
        const isEnrolled = this._enrolledCourseIds.has(course.id);
        const levelClass = course.level === 'BEGINNER' ? 'cc-level-beginner' :
                          (course.level === 'INTERMEDIATE' ? 'cc-level-intermediate' : 'cc-level-advanced');
        
        const trainerName = (course.trainer && course.trainer.username) ? course.trainer.username : 'Staff Trainer';
        const durationHours = course.duration_hours || 0;

        return `
            <div class="col-md-6 col-xl-4">
                <div class="cc-course-card">
                    <div class="cc-course-card-body">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <span class="badge bg-secondary-subtle text-secondary px-2 py-1 small fw-semibold">
                                <i class="bi bi-tag-fill me-1"></i>${TraineeLearning.escapeHtml(course.category || 'General')}
                            </span>
                            <span class="cc-course-badge-level ${levelClass}">
                                ${TraineeLearning.escapeHtml(course.level)}
                            </span>
                        </div>

                        <h5 class="fw-bold text-dark mb-2 text-truncate" title="${TraineeLearning.escapeHtml(course.title)}">
                            ${TraineeLearning.escapeHtml(course.title)}
                        </h5>

                        <div class="d-flex align-items-center text-muted small mb-3">
                            <i class="bi bi-clock me-1 text-primary"></i>
                            <span class="me-3">${durationHours} hrs</span>
                            <i class="bi bi-person me-1 text-primary"></i>
                            <span class="text-truncate">${TraineeLearning.escapeHtml(trainerName)}</span>
                        </div>

                        <div class="mt-auto pt-2">
                            ${isEnrolled ? `
                                <div class="badge bg-success-subtle text-success py-2 px-3 w-100 text-center fw-semibold mb-2">
                                    <i class="bi bi-check-circle-fill me-1"></i>Enrolled in Course
                                </div>
                            ` : ''}
                        </div>
                    </div>

                    <div class="cc-course-card-footer d-flex gap-2">
                        <a href="course-details.html?id=${course.id}" class="btn btn-outline-primary btn-sm flex-fill fw-semibold">
                            <i class="bi bi-info-circle me-1"></i>Details
                        </a>
                        ${isEnrolled ? `
                            <a href="my-courses.html" class="btn btn-primary btn-sm flex-fill fw-semibold">
                                <i class="bi bi-play-circle me-1"></i>Go to Course
                            </a>
                        ` : `
                            <a href="course-details.html?id=${course.id}&action=enroll" class="btn btn-primary btn-sm flex-fill fw-semibold">
                                <i class="bi bi-box-arrow-in-right me-1"></i>Enroll
                            </a>
                        `}
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Render skeleton loading cards while fetching data.
     * @param {number} count
     * @returns {string}
     */
    renderSkeletons(count = 6) {
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
                        <div class="cc-skeleton cc-skeleton-text" style="width: 50%;"></div>
                        <div class="cc-skeleton cc-skeleton-text mt-4" style="height: 36px;"></div>
                    </div>
                </div>
            `;
        }
        return html;
    }
};

window.BrowseCoursesController = BrowseCoursesController;
