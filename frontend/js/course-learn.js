/**
 * Capacity Connect — Course Learning Controller (course-learn.js)
 *
 * Manages the trainee learning room:
 * - Ordered subject navigation drawer
 * - Real-time subject completion toggle via backend API
 * - Synchronized progress percentage recalculation
 * - Professional course completion status
 */

'use strict';

const CourseLearnController = {
    _enrollmentId: null,
    _enrollment: null,
    _course: null,
    _activeSubjectIndex: 0,
    _isToggling: false,

    /**
     * Initializes the learning room.
     */
    async init() {
        const urlParams = new URLSearchParams(window.location.search);
        this._enrollmentId = urlParams.get('enrollment_id');

        if (!this._enrollmentId) {
            this.showError('Invalid learning session. No enrollment ID provided.');
            return;
        }

        await this.loadLearningData();
    },

    /**
     * Fetch enrollment and course syllabus.
     */
    async loadLearningData() {
        const loadingContainer = document.getElementById('learnLoadingState');
        const contentContainer = document.getElementById('learnContentState');
        const errorContainer = document.getElementById('learnErrorState');

        if (loadingContainer) loadingContainer.classList.remove('d-none');
        if (contentContainer) contentContainer.classList.add('d-none');
        if (errorContainer) errorContainer.classList.add('d-none');

        try {
            const enrollment = await TraineeLearning.fetchEnrollmentDetails(this._enrollmentId);
            this._enrollment = enrollment;

            // Fetch course details for subject descriptions
            const courseId = (typeof enrollment.course === 'object' ? enrollment.course.id : enrollment.course);
            this._course = await TraineeLearning.fetchCourseDetails(courseId);

            // Merge subject descriptions into subject_progresses
            this.mergeSubjectData();

            // Set initial active subject: find first incomplete subject, or default to first
            const firstIncompleteIdx = this._enrollment.subject_progresses.findIndex(sp => !sp.completed);
            this._activeSubjectIndex = firstIncompleteIdx >= 0 ? firstIncompleteIdx : 0;

            this.renderHeader();
            this.renderSyllabusDrawer();
            this.renderActiveSubject();

            if (loadingContainer) loadingContainer.classList.add('d-none');
            if (contentContainer) contentContainer.classList.remove('d-none');

        } catch (err) {
            console.error('[CourseLearn] Error loading learning session:', err);
            if (loadingContainer) loadingContainer.classList.add('d-none');
            this.showError(err.message || 'Unable to load course learning session.');
        }
    },

    /**
     * Merge subject descriptions from Course detail into SubjectProgress records.
     */
    mergeSubjectData() {
        if (!this._enrollment || !Array.isArray(this._enrollment.subject_progresses)) return;

        const courseSubjectsMap = new Map();
        if (this._course && Array.isArray(this._course.subjects)) {
            this._course.subjects.forEach(s => courseSubjectsMap.set(s.id, s));
        }

        this._enrollment.subject_progresses.forEach(sp => {
            const courseSubj = courseSubjectsMap.get(sp.subject_id);
            if (courseSubj) {
                sp.description = courseSubj.description || '';
                sp.order = courseSubj.order || sp.subject_order || 0;
            }
        });

        // Ensure sorted by order
        this._enrollment.subject_progresses.sort((a, b) => (a.subject_order || 0) - (b.subject_order || 0));
    },

    /**
     * Display error state.
     */
    showError(message) {
        const errorContainer = document.getElementById('learnErrorState');
        const contentContainer = document.getElementById('learnContentState');
        if (contentContainer) contentContainer.classList.add('d-none');
        if (errorContainer) {
            errorContainer.classList.remove('d-none');
            const msgEl = errorContainer.querySelector('.error-message');
            if (msgEl) msgEl.textContent = message;
        }
    },

    /**
     * Render header bar with Course Title, Level, and Progress percentage.
     */
    renderHeader() {
        const course = this._course || this._enrollment.course || {};
        const isCompleted = this._enrollment.status === 'COMPLETED';
        const progress = parseFloat(this._enrollment.progress_percentage) || 0;

        document.title = `${course.title || 'Learning'} — Capacity Connect`;

        const titleEl = document.getElementById('learnCourseTitle');
        if (titleEl) titleEl.textContent = course.title || 'Course';

        const categoryEl = document.getElementById('learnCourseCategory');
        if (categoryEl) categoryEl.textContent = course.category || 'General';

        const progressValEl = document.getElementById('learnProgressValue');
        if (progressValEl) progressValEl.textContent = `${progress}%`;

        const progressBarEl = document.getElementById('learnProgressBar');
        if (progressBarEl) {
            progressBarEl.style.width = `${progress}%`;
            if (isCompleted) {
                progressBarEl.classList.add('completed');
            } else {
                progressBarEl.classList.remove('completed');
            }
        }

        const statusBadge = document.getElementById('learnStatusBadge');
        if (statusBadge) {
            statusBadge.className = `badge ${isCompleted ? 'bg-success text-white' : 'bg-primary-subtle text-primary'} px-2 py-1`;
            statusBadge.textContent = isCompleted ? 'Completed' : 'In Progress';
        }
    },

    /**
     * Render the left sidebar / syllabus drawer list.
     */
    renderSyllabusDrawer() {
        const list = document.getElementById('learnSyllabusList');
        const countBadge = document.getElementById('learnSyllabusCount');
        if (!list) return;

        const progresses = this._enrollment.subject_progresses || [];
        if (countBadge) countBadge.textContent = `${progresses.length} Modules`;

        if (progresses.length === 0) {
            list.innerHTML = `<li class="p-3 text-muted small text-center">No modules configured.</li>`;
            return;
        }

        list.innerHTML = progresses.map((sp, idx) => {
            const isActive = idx === this._activeSubjectIndex;
            const isCompleted = sp.completed;

            return `
                <li class="cc-syllabus-item ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}"
                    onclick="CourseLearnController.selectSubject(${idx});">
                    <span class="cc-subject-status-icon">
                        <i class="bi ${isCompleted ? 'bi-check-circle-fill text-success' : 'bi-circle text-muted'}"></i>
                    </span>
                    <div class="overflow-hidden flex-grow-1">
                        <div class="small fw-semibold text-truncate">${idx + 1}. ${TraineeLearning.escapeHtml(sp.subject_title)}</div>
                        <div class="text-muted" style="font-size: 0.7rem;">
                            ${isCompleted ? 'Completed' : 'Pending'}
                        </div>
                    </div>
                </li>
            `;
        }).join('');
    },

    /**
     * Render the main subject content viewer.
     */
    renderActiveSubject() {
        const progresses = this._enrollment.subject_progresses || [];
        if (progresses.length === 0) return;

        const currentSp = progresses[this._activeSubjectIndex];
        if (!currentSp) return;

        const titleEl = document.getElementById('activeSubjectTitle');
        const orderEl = document.getElementById('activeSubjectOrder');
        const descEl = document.getElementById('activeSubjectDescription');
        const toggleBtn = document.getElementById('toggleCompleteBtn');
        const prevBtn = document.getElementById('prevSubjectBtn');
        const nextBtn = document.getElementById('nextSubjectBtn');
        const completionNotice = document.getElementById('subjectCompletionNotice');

        if (titleEl) titleEl.textContent = currentSp.subject_title || 'Module';
        if (orderEl) orderEl.textContent = `Module ${this._activeSubjectIndex + 1} of ${progresses.length}`;

        if (descEl) {
            descEl.textContent = currentSp.description || 'Review the module syllabus and learning objectives. When finished, mark the subject complete below.';
        }

        if (toggleBtn) {
            if (currentSp.completed) {
                toggleBtn.className = 'btn btn-outline-success fw-semibold';
                toggleBtn.innerHTML = `<i class="bi bi-check-circle-fill me-2"></i>Completed (Click to Reopen)`;
            } else {
                toggleBtn.className = 'btn btn-primary fw-semibold';
                toggleBtn.innerHTML = `<i class="bi bi-check2-circle me-2"></i>Mark as Complete`;
            }
        }

        if (completionNotice) {
            if (this._enrollment.status === 'COMPLETED') {
                completionNotice.classList.remove('d-none');
            } else {
                completionNotice.classList.add('d-none');
            }
        }

        // Navigation controls
        if (prevBtn) {
            prevBtn.disabled = (this._activeSubjectIndex === 0);
        }
        if (nextBtn) {
            nextBtn.disabled = (this._activeSubjectIndex === progresses.length - 1);
        }
    },

    /**
     * Switch currently viewed subject.
     * @param {number} index
     */
    selectSubject(index) {
        const progresses = this._enrollment.subject_progresses || [];
        if (index >= 0 && index < progresses.length) {
            this._activeSubjectIndex = index;
            this.renderSyllabusDrawer();
            this.renderActiveSubject();
        }
    },

    /**
     * Navigate to previous subject.
     */
    prevSubject() {
        if (this._activeSubjectIndex > 0) {
            this.selectSubject(this._activeSubjectIndex - 1);
        }
    },

    /**
     * Navigate to next subject.
     */
    nextSubject() {
        const progresses = this._enrollment.subject_progresses || [];
        if (this._activeSubjectIndex < progresses.length - 1) {
            this.selectSubject(this._activeSubjectIndex + 1);
        }
    },

    /**
     * Toggle completion state of the current subject.
     */
    async handleToggleComplete() {
        if (this._isToggling) return;

        const progresses = this._enrollment.subject_progresses || [];
        const currentSp = progresses[this._activeSubjectIndex];
        if (!currentSp) return;

        const toggleBtn = document.getElementById('toggleCompleteBtn');
        const targetCompleted = !currentSp.completed;

        this._isToggling = true;
        if (toggleBtn) {
            toggleBtn.disabled = true;
            toggleBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Updating...`;
        }

        try {
            const updatedEnrollment = await TraineeLearning.toggleSubjectComplete(
                this._enrollmentId,
                currentSp.subject_id,
                targetCompleted
            );

            this._enrollment = updatedEnrollment;
            this.mergeSubjectData();

            this.renderHeader();
            this.renderSyllabusDrawer();
            this.renderActiveSubject();

            // If trainee completed this subject and there is a next incomplete subject, prompt / auto-advance
            if (targetCompleted && this._activeSubjectIndex < progresses.length - 1) {
                const nextIncomplete = progresses.findIndex((sp, idx) => idx > this._activeSubjectIndex && !sp.completed);
                if (nextIncomplete > this._activeSubjectIndex) {
                    this.selectSubject(nextIncomplete);
                }
            }

        } catch (err) {
            console.error('[CourseLearn] Toggle failed:', err);
            alert(`Unable to update progress: ${err.message || 'Please try again.'}`);
            this.renderActiveSubject();
        } finally {
            this._isToggling = false;
            if (toggleBtn) toggleBtn.disabled = false;
        }
    }
};

window.CourseLearnController = CourseLearnController;
