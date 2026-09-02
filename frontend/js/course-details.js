/**
 * Capacity Connect — Course Details Controller (course-details.js)
 *
 * Handles fetching full course overview, curriculum syllabus, prerequisite requirements,
 * learning objectives, and trainee enrollment execution.
 */

'use strict';

const CourseDetailsController = {
    _courseId: null,
    _course: null,
    _existingEnrollment: null,

    /**
     * Initializes the course details page.
     */
    async init() {
        const urlParams = new URLSearchParams(window.location.search);
        this._courseId = urlParams.get('id');

        if (!this._courseId) {
            this.showError('Invalid course request. No course ID provided.');
            return;
        }

        await this.loadCourseData();

        // Check if direct enrollment was requested via query parameter
        if (urlParams.get('action') === 'enroll' && !this._existingEnrollment) {
            this.handleEnrollment();
        }
    },

    /**
     * Load course details and check user's enrollment status.
     */
    async loadCourseData() {
        const loadingContainer = document.getElementById('courseDetailsLoading');
        const contentContainer = document.getElementById('courseDetailsContent');
        const errorContainer = document.getElementById('courseDetailsError');

        if (loadingContainer) loadingContainer.classList.remove('d-none');
        if (contentContainer) contentContainer.classList.add('d-none');
        if (errorContainer) errorContainer.classList.add('d-none');

        try {
            const [course, enrollments] = await Promise.all([
                TraineeLearning.fetchCourseDetails(this._courseId),
                TraineeLearning.fetchMyEnrollments().catch(() => [])
            ]);

            this._course = course;
            
            // Check if user is already enrolled in this specific course
            const numericId = parseInt(this._courseId, 10);
            this._existingEnrollment = (Array.isArray(enrollments) ? enrollments : []).find(e => {
                const cId = (typeof e.course === 'object' ? e.course.id : e.course);
                return cId === numericId && e.status !== 'DROPPED';
            }) || null;

            this.renderCourse(course);

            if (loadingContainer) loadingContainer.classList.add('d-none');
            if (contentContainer) contentContainer.classList.remove('d-none');

        } catch (err) {
            console.error('[CourseDetails] Error loading course:', err);
            if (loadingContainer) loadingContainer.classList.add('d-none');
            this.showError(err.message || 'Course not found or currently unavailable.');
        }
    },

    /**
     * Display error state.
     */
    showError(message) {
        const errorContainer = document.getElementById('courseDetailsError');
        const contentContainer = document.getElementById('courseDetailsContent');
        if (contentContainer) contentContainer.classList.add('d-none');
        if (errorContainer) {
            errorContainer.classList.remove('d-none');
            const msgEl = errorContainer.querySelector('.error-message');
            if (msgEl) msgEl.textContent = message;
        }
    },

    /**
     * Render full course data into DOM elements.
     * @param {object} course
     */
    renderCourse(course) {
        // Document Title
        document.title = `${course.title || 'Course Details'} — Capacity Connect`;

        // Breadcrumb and Titles
        const titleElements = document.querySelectorAll('.cc-course-title');
        titleElements.forEach(el => el.textContent = course.title || 'Untitled Course');

        // Meta badges
        const categoryEl = document.getElementById('courseCategoryBadge');
        if (categoryEl) categoryEl.textContent = course.category || 'General';

        const levelEl = document.getElementById('courseLevelBadge');
        if (levelEl) {
            levelEl.textContent = course.level || 'Beginner';
            const levelClass = course.level === 'BEGINNER' ? 'cc-level-beginner' :
                              (course.level === 'INTERMEDIATE' ? 'cc-level-intermediate' : 'cc-level-advanced');
            levelEl.className = `badge cc-course-badge-level ${levelClass}`;
        }

        const durationEl = document.getElementById('courseDurationDisplay');
        if (durationEl) durationEl.textContent = `${course.duration_hours || 0} Hours`;

        const trainerEl = document.getElementById('courseTrainerDisplay');
        if (trainerEl) {
            const trainerName = (course.trainer && course.trainer.username) ? course.trainer.username : 'Staff Trainer';
            trainerEl.textContent = trainerName;
        }

        // Description
        const descEl = document.getElementById('courseDescriptionDisplay');
        if (descEl) descEl.textContent = course.description || 'No description provided.';

        // Learning Objectives
        const objSection = document.getElementById('courseObjectivesSection');
        const objEl = document.getElementById('courseObjectivesDisplay');
        if (course.learning_objectives && course.learning_objectives.trim()) {
            if (objEl) objEl.textContent = course.learning_objectives;
            if (objSection) objSection.classList.remove('d-none');
        } else if (objSection) {
            objSection.classList.add('d-none');
        }

        // Requirements
        const reqSection = document.getElementById('courseRequirementsSection');
        const reqEl = document.getElementById('courseRequirementsDisplay');
        if (course.requirements && course.requirements.trim()) {
            if (reqEl) reqEl.textContent = course.requirements;
            if (reqSection) reqSection.classList.remove('d-none');
        } else if (reqSection) {
            reqSection.classList.add('d-none');
        }

        // Syllabus / Subjects list
        this.renderCurriculum(course.subjects || []);

        // Enrollment Action Card
        this.renderEnrollmentActionCard();
    },

    /**
     * Render curriculum modules list.
     * @param {Array} subjects
     */
    renderCurriculum(subjects) {
        const list = document.getElementById('courseCurriculumList');
        const countEl = document.getElementById('courseSubjectCount');
        if (!list) return;

        if (countEl) countEl.textContent = `${subjects.length} ${subjects.length === 1 ? 'Module' : 'Modules'}`;

        if (!Array.isArray(subjects) || subjects.length === 0) {
            list.innerHTML = `
                <div class="p-4 text-center text-muted small bg-light rounded-3">
                    <i class="bi bi-journal-text fs-3 mb-2 d-block"></i>
                    No modules published for this course yet.
                </div>
            `;
            return;
        }

        // Sort by order ascending
        const sorted = [...subjects].sort((a, b) => (a.order || 0) - (b.order || 0));

        list.innerHTML = sorted.map((subj, idx) => `
            <div class="card border-0 bg-light rounded-3 mb-2">
                <div class="card-body p-3">
                    <div class="d-flex align-items-start">
                        <div class="badge bg-primary text-white rounded-circle p-2 me-3" style="width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-size: 0.75rem;">
                            ${subj.order || (idx + 1)}
                        </div>
                        <div class="flex-grow-1">
                            <h6 class="fw-bold text-dark mb-1">${TraineeLearning.escapeHtml(subj.title)}</h6>
                            ${subj.description ? `<p class="text-muted small mb-0">${TraineeLearning.escapeHtml(subj.description)}</p>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
    },

    /**
     * Render enrollment button state based on existing enrollment status.
     */
    renderEnrollmentActionCard() {
        const actionContainer = document.getElementById('enrollmentActionArea');
        if (!actionContainer) return;

        if (this._existingEnrollment) {
            const enrollmentId = this._existingEnrollment.id;
            const progress = parseFloat(this._existingEnrollment.progress_percentage) || 0;
            const isCompleted = this._existingEnrollment.status === 'COMPLETED';

            actionContainer.innerHTML = `
                <div class="alert ${isCompleted ? 'alert-success' : 'alert-primary'} mb-3 py-2 px-3 small">
                    <i class="bi ${isCompleted ? 'bi-check-circle-fill' : 'bi-info-circle-fill'} me-1"></i>
                    ${isCompleted ? 'You have completed this course!' : 'You are currently enrolled in this course.'}
                </div>

                <div class="mb-3">
                    <div class="d-flex justify-content-between small text-muted mb-1">
                        <span>Learning Progress</span>
                        <span class="fw-bold text-dark">${progress}%</span>
                    </div>
                    <div class="cc-progress">
                        <div class="cc-progress-bar ${isCompleted ? 'completed' : ''}" style="width: ${progress}%;"></div>
                    </div>
                </div>

                <a href="course-learn.html?enrollment_id=${enrollmentId}" class="btn btn-primary w-100 py-2 fw-semibold">
                    <i class="bi bi-play-circle-fill me-2"></i>Continue Learning
                </a>
            `;
        } else {
            actionContainer.innerHTML = `
                <div class="p-3 bg-light rounded-3 mb-3 text-center">
                    <div class="text-muted small mb-1">Course Access</div>
                    <div class="fw-bold text-success fs-5">Open for Enrollment</div>
                </div>

                <button class="btn btn-primary w-100 py-2 fw-semibold" id="enrollSubmitBtn" onclick="CourseDetailsController.handleEnrollment();">
                    <i class="bi bi-mortarboard-fill me-2"></i>Enroll in Course
                </button>

                <div id="enrollmentAlertContainer" class="mt-3"></div>
            `;
        }
    },

    /**
     * Executes course enrollment request.
     */
    async handleEnrollment() {
        const btn = document.getElementById('enrollSubmitBtn');
        const alertArea = document.getElementById('enrollmentAlertContainer');

        if (btn) {
            btn.disabled = true;
            btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Enrolling...`;
        }
        if (alertArea) alertArea.innerHTML = '';

        try {
            const enrollment = await TraineeLearning.enrollInCourse(this._courseId);
            this._existingEnrollment = enrollment;

            if (alertArea) {
                alertArea.innerHTML = `
                    <div class="alert alert-success small py-2 px-3 mb-2">
                        <i class="bi bi-check-circle-fill me-1"></i>Enrollment successful! Redirecting to course workspace...
                    </div>
                `;
            }

            // Redirect to course learn room after short delay
            setTimeout(() => {
                window.location.href = `course-learn.html?enrollment_id=${enrollment.id}`;
            }, 800);

        } catch (err) {
            console.error('[CourseDetails] Enrollment failed:', err);
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `<i class="bi bi-mortarboard-fill me-2"></i>Enroll in Course`;
            }
            if (alertArea) {
                alertArea.innerHTML = `
                    <div class="alert alert-danger small py-2 px-3 mb-0">
                        <i class="bi bi-exclamation-circle-fill me-1"></i>${TraineeLearning.escapeHtml(err.message || 'Enrollment failed. Please try again.')}
                    </div>
                `;
            }
        }
    }
};

window.CourseDetailsController = CourseDetailsController;
