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
    _assessments: [],
    _certificate: null,

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

            // Fetch published assessments for this course
            try {
                const assessments = await apiRequest(`/assessments/trainee/courses/${courseId}/`);
                this._assessments = Array.isArray(assessments) ? assessments : [];
            } catch (e) {
                console.warn('[CourseLearn] Could not fetch assessments:', e);
                this._assessments = [];
            }

            // Fetch certificate status if completed
            if (this._enrollment && (this._enrollment.status === 'COMPLETED' || parseFloat(this._enrollment.progress_percentage) === 100)) {
                try {
                    const certs = await apiRequest('/certificates/my-certificates/');
                    const currentCert = Array.isArray(certs) ? certs.find(c => c.course_id === courseId) : null;
                    if (currentCert) {
                        this._certificate = await apiRequest(`/certificates/${currentCert.id}/`);
                    } else {
                        this._certificate = null;
                    }
                } catch (e) {
                    console.warn('[CourseLearn] Could not fetch certificate:', e);
                    this._certificate = null;
                }
            } else {
                this._certificate = null;
            }

            // Merge subject descriptions into subject_progresses
            this.mergeSubjectData();

            // Set initial active subject: find first incomplete subject, or default to first
            const firstIncompleteIdx = this._enrollment.subject_progresses.findIndex(sp => !sp.completed);
            this._activeSubjectIndex = firstIncompleteIdx >= 0 ? firstIncompleteIdx : 0;

            this.renderHeader();
            this.renderSyllabusDrawer();
            this.renderActiveSubject();

            // Initialize Step 12 Discussions
            const currentSp = this._enrollment.subject_progresses[this._activeSubjectIndex];
            const activeSubjId = currentSp ? currentSp.subject_id : null;
            if (typeof DiscussionsController !== 'undefined') {
                DiscussionsController.initCourseDiscussions(courseId, activeSubjId);
            }
            this.populateDiscussionSubjects();

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

        // Check for module assessment
        let assessmentHtml = '';
        const moduleAssessment = (this._assessments || []).find(a => a.subject === currentSp.subject_id);
        const courseFinalAssessment = (this._assessments || []).find(a => !a.subject);
        const activeAssess = moduleAssessment || (this._activeSubjectIndex === progresses.length - 1 ? courseFinalAssessment : null);

        if (activeAssess) {
            const hasAttempted = activeAssess.has_attempted;
            const passed = activeAssess.passed;
            const statusBadge = hasAttempted
                ? (passed
                    ? '<span class="badge bg-success-subtle text-success fw-bold"><i class="bi bi-check-circle me-1"></i>Passed (' + activeAssess.best_percentage + '%)</span>'
                    : '<span class="badge bg-danger-subtle text-danger fw-bold"><i class="bi bi-x-circle me-1"></i>Failed (' + activeAssess.best_percentage + '%)</span>')
                : '<span class="badge bg-warning-subtle text-warning fw-semibold">Not Attempted</span>';

            assessmentHtml = `
                <div class="card border-primary border-opacity-25 bg-primary bg-opacity-10 rounded-3 p-3 my-3">
                    <div class="d-flex flex-column flex-sm-row justify-content-between align-items-sm-center gap-2">
                        <div>
                            <div class="d-flex align-items-center gap-2 mb-1">
                                <i class="bi bi-patch-question-fill text-primary fs-5"></i>
                                <h6 class="fw-bold text-dark mb-0">${this.escapeHtml(activeAssess.title)}</h6>
                                ${statusBadge}
                            </div>
                            <p class="text-muted small mb-0">
                                Pass: ${activeAssess.passing_percentage}% &bull; ${activeAssess.duration_minutes} mins &bull; ${activeAssess.question_count} Questions (${activeAssess.total_marks} Marks)
                            </p>
                        </div>
                        <button class="btn btn-primary btn-sm px-3 fw-semibold text-nowrap" onclick="CourseLearnController.openQuizModal(${activeAssess.id});">
                            <i class="bi bi-play-circle me-1"></i>${hasAttempted ? 'Retake Quiz' : 'Take Quiz'}
                        </button>
                    </div>
                </div>
            `;
        }

        // Insert or update assessment container in viewer
        let assessContainer = document.getElementById('subjectAssessmentContainer');
        if (!assessContainer) {
            assessContainer = document.createElement('div');
            assessContainer.id = 'subjectAssessmentContainer';
            if (descEl && descEl.parentNode) {
                descEl.parentNode.insertBefore(assessContainer, descEl.nextSibling);
            }
        }
        assessContainer.innerHTML = assessmentHtml;

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

        // Certificate banner
        const certNotice = document.getElementById('certificateEarnedNotice');
        const btnCertText = document.getElementById('btnCertText');
        const certBannerSub = document.getElementById('certBannerSubtitle');

        if (this._enrollment.status === 'COMPLETED' || parseFloat(this._enrollment.progress_percentage) === 100) {
            if (certNotice) certNotice.classList.remove('d-none');
            if (this._certificate) {
                if (btnCertText) btnCertText.textContent = 'View Certificate';
                if (certBannerSub) certBannerSub.textContent = `Certificate issued with grade ${this._certificate.final_grade_percentage}%.`;
            } else {
                if (btnCertText) btnCertText.textContent = 'Claim Certificate';
                if (certBannerSub) certBannerSub.textContent = 'You have completed all curriculum requirements. Claim your official credential!';
            }
        } else {
            if (certNotice) certNotice.classList.add('d-none');
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

            const currentSp = progresses[index];
            if (currentSp && typeof DiscussionsController !== 'undefined') {
                DiscussionsController.setActiveSubject(currentSp.subject_id);
            }
        }
    },

    /**
     * Switch learning viewer tab (Lesson Content vs Q&A vs Announcements).
     */
    switchViewerTab(tab) {
        const contentPane = document.getElementById('viewerContentPane');
        const discPane = document.getElementById('viewerDiscussionPane');
        const tabContentBtn = document.getElementById('tabContentBtn');
        const tabDiscussionBtn = document.getElementById('tabDiscussionBtn');
        const tabAnnouncementsBtn = document.getElementById('tabAnnouncementsBtn');

        if (!contentPane || !discPane) return;

        if (tab === 'content') {
            contentPane.classList.remove('d-none');
            discPane.classList.add('d-none');
            if (tabContentBtn) tabContentBtn.classList.add('active');
            if (tabDiscussionBtn) tabDiscussionBtn.classList.remove('active');
            if (tabAnnouncementsBtn) tabAnnouncementsBtn.classList.remove('active');
        } else if (tab === 'discussion') {
            contentPane.classList.add('d-none');
            discPane.classList.remove('d-none');
            if (tabContentBtn) tabContentBtn.classList.remove('active');
            if (tabDiscussionBtn) tabDiscussionBtn.classList.add('active');
            if (tabAnnouncementsBtn) tabAnnouncementsBtn.classList.remove('active');
            if (typeof DiscussionsController !== 'undefined') {
                DiscussionsController.setFilterTab('all');
            }
        } else if (tab === 'announcements') {
            contentPane.classList.add('d-none');
            discPane.classList.remove('d-none');
            if (tabContentBtn) tabContentBtn.classList.remove('active');
            if (tabDiscussionBtn) tabDiscussionBtn.classList.remove('active');
            if (tabAnnouncementsBtn) tabAnnouncementsBtn.classList.add('active');
            if (typeof DiscussionsController !== 'undefined') {
                DiscussionsController.setFilterTab('announcements');
            }
        }
    },

    /**
     * Populate discussion subject select dropdown with modules.
     */
    populateDiscussionSubjects() {
        const select = document.getElementById('threadSubjectSelect');
        if (!select || !this._course || !Array.isArray(this._course.subjects)) return;

        const options = ['<option value="">General Course Discussion (No Specific Module)</option>'];
        this._course.subjects.forEach(s => {
            options.push(`<option value="${s.id}">Module ${s.order}: ${TraineeLearning.escapeHtml(s.title)}</option>`);
        });
        select.innerHTML = options.join('');
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
    },

    // =========================================================================
    // QUIZ TAKING & GRADING CONTROLLER
    // =========================================================================

    _activeQuizAssessment: null,

    /**
     * Opens the interactive Quiz Taking modal.
     */
    async openQuizModal(assessmentId) {
        this._activeQuizAssessment = null;

        const activeBody = document.getElementById('quizActiveBody');
        const resultBody = document.getElementById('quizResultBody');
        const resultFooter = document.getElementById('quizResultFooter');
        const qContainer = document.getElementById('quizQuestionsContainer');

        if (activeBody) activeBody.classList.remove('d-none');
        if (resultBody) resultBody.classList.add('d-none');
        if (resultFooter) resultFooter.classList.add('d-none');

        if (qContainer) {
            qContainer.innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border spinner-border-sm text-primary mb-2"></div>
                    <p class="text-muted small mb-0">Loading quiz questions...</p>
                </div>
            `;
        }

        const modalEl = document.getElementById('traineeQuizModal');
        if (modalEl) {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        }

        try {
            const assessment = await apiRequest(`/assessments/trainee/${assessmentId}/take/`);
            this._activeQuizAssessment = assessment;

            const titleEl = document.getElementById('traineeQuizModalTitle');
            if (titleEl) titleEl.textContent = assessment.title || 'Interactive Quiz';

            const durEl = document.getElementById('quizDurationText');
            if (durEl) durEl.textContent = `${assessment.duration_minutes || 30} mins`;

            const passEl = document.getElementById('quizPassingText');
            if (passEl) passEl.textContent = `${assessment.passing_percentage || 70}%`;

            const countBadge = document.getElementById('quizQuestionCountBadge');
            if (countBadge) countBadge.textContent = `${(assessment.questions || []).length} Questions`;

            this.renderQuizQuestions(assessment.questions || []);

            // Bind submit event
            const qForm = document.getElementById('quizQuestionsForm');
            if (qForm) {
                qForm.onsubmit = (e) => this.handleQuizSubmit(e, assessment.id);
            }

        } catch (err) {
            console.error('[CourseLearn] Error loading quiz:', err);
            if (qContainer) {
                qContainer.innerHTML = `
                    <div class="alert alert-danger small mb-0">
                        <i class="bi bi-exclamation-triangle-fill me-2"></i>Failed to load assessment: ${this.escapeHtml(err.message)}
                    </div>
                `;
            }
        }
    },

    /**
     * Renders MCQ questions with styled option radio cards.
     */
    renderQuizQuestions(questions) {
        const container = document.getElementById('quizQuestionsContainer');
        if (!container) return;

        if (questions.length === 0) {
            container.innerHTML = `<div class="alert alert-info small">This assessment has no questions configured yet.</div>`;
            return;
        }

        const questionsHtml = questions.map((q, idx) => {
            return `
                <div class="card border rounded-3 shadow-sm p-3">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="badge bg-light text-primary border fw-semibold">Question ${q.order || (idx + 1)}</span>
                        <span class="text-muted small">${q.marks} Mark${q.marks > 1 ? 's' : ''}</span>
                    </div>
                    <h6 class="fw-bold text-dark mb-3">${this.escapeHtml(q.question_text)}</h6>

                    <div class="d-flex flex-column gap-2">
                        <label class="form-check border rounded p-2 d-flex align-items-center gap-2 cursor-pointer hover-bg-light mb-0">
                            <input class="form-check-input ms-1" type="radio" name="q_${q.id}" value="A" required>
                            <span class="small text-dark"><strong>A:</strong> ${this.escapeHtml(q.option_a)}</span>
                        </label>
                        <label class="form-check border rounded p-2 d-flex align-items-center gap-2 cursor-pointer hover-bg-light mb-0">
                            <input class="form-check-input ms-1" type="radio" name="q_${q.id}" value="B" required>
                            <span class="small text-dark"><strong>B:</strong> ${this.escapeHtml(q.option_b)}</span>
                        </label>
                        <label class="form-check border rounded p-2 d-flex align-items-center gap-2 cursor-pointer hover-bg-light mb-0">
                            <input class="form-check-input ms-1" type="radio" name="q_${q.id}" value="C" required>
                            <span class="small text-dark"><strong>C:</strong> ${this.escapeHtml(q.option_c)}</span>
                        </label>
                        <label class="form-check border rounded p-2 d-flex align-items-center gap-2 cursor-pointer hover-bg-light mb-0">
                            <input class="form-check-input ms-1" type="radio" name="q_${q.id}" value="D" required>
                            <span class="small text-dark"><strong>D:</strong> ${this.escapeHtml(q.option_d)}</span>
                        </label>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = questionsHtml;
    },

    /**
     * Handles quiz answer submission and auto-grading.
     */
    async handleQuizSubmit(e, assessmentId) {
        e.preventDefault();
        if (!this._activeQuizAssessment) return;

        const questions = this._activeQuizAssessment.questions || [];
        const answers = [];

        for (const q of questions) {
            const selectedRadio = document.querySelector(`input[name="q_${q.id}"]:checked`);
            if (!selectedRadio) {
                alert(`Please answer Question ${q.order} before submitting.`);
                return;
            }
            answers.push({
                question_id: q.id,
                selected_option: selectedRadio.value,
            });
        }

        const btn = document.getElementById('btnSubmitQuiz');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Grading...`;
        }

        try {
            const result = await apiRequest(`/assessments/trainee/${assessmentId}/submit/`, {
                method: 'POST',
                body: JSON.stringify({ answers }),
            });

            this.renderQuizResult(result);
        } catch (err) {
            console.error('[CourseLearn] Quiz submission error:', err);
            alert(`Failed to submit quiz: ${err.message}`);
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `<i class="bi bi-send-check me-2"></i>Submit Assessment`;
            }
        }
    },

    /**
     * Renders the auto-graded result screen with answer review.
     */
    renderQuizResult(attempt) {
        const activeBody = document.getElementById('quizActiveBody');
        const resultBody = document.getElementById('quizResultBody');
        const resultFooter = document.getElementById('quizResultFooter');

        if (activeBody) activeBody.classList.add('d-none');
        if (resultBody) resultBody.classList.remove('d-none');
        if (resultFooter) resultFooter.classList.remove('d-none');

        const passBadge = attempt.passed
            ? '<span class="badge bg-success fs-6 px-3 py-2"><i class="bi bi-check-circle-fill me-2"></i>PASSED</span>'
            : '<span class="badge bg-danger fs-6 px-3 py-2"><i class="bi bi-x-circle-fill me-2"></i>FAILED</span>';

        const reviewHtml = (attempt.answers || []).map((ans, idx) => {
            const isCorrect = ans.is_correct;
            const badgeClass = isCorrect ? 'bg-success-subtle text-success' : 'bg-danger-subtle text-danger';
            const icon = isCorrect ? 'bi-check-circle-fill text-success' : 'bi-x-circle-fill text-danger';

            return `
                <div class="card border mb-3 rounded-3 shadow-sm">
                    <div class="card-body p-3">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="badge bg-light text-dark border">Q${ans.order || (idx + 1)}</span>
                            <span class="badge ${badgeClass}"><i class="bi ${icon} me-1"></i>${ans.marks_obtained} / ${ans.max_marks} Marks</span>
                        </div>
                        <p class="fw-bold text-dark mb-2">${this.escapeHtml(ans.question_text)}</p>

                        <div class="small mb-1">
                            Your Answer: <strong>Option ${ans.selected_option}</strong> &bull;
                            Correct Answer: <strong class="text-success">Option ${ans.correct_answer}</strong>
                        </div>
                        ${ans.explanation ? `<div class="text-muted small fst-italic mt-1 bg-light p-2 rounded">Explanation: ${this.escapeHtml(ans.explanation)}</div>` : ''}
                    </div>
                </div>
            `;
        }).join('');

        if (resultBody) {
            resultBody.innerHTML = `
                <div class="text-center py-3 mb-4 border-bottom">
                    <div class="mb-2">${passBadge}</div>
                    <h3 class="fw-bold text-dark mb-1">${attempt.percentage}%</h3>
                    <p class="text-muted small mb-0">
                        Score: <strong>${attempt.score}</strong> / ${attempt.total_marks} Marks &bull; Required to Pass: <strong>${attempt.passing_percentage}%</strong>
                    </p>
                </div>

                <h6 class="fw-bold text-dark mb-3"><i class="bi bi-card-checklist me-2 text-primary"></i>Question Breakdown & Explanations</h6>
                <div class="d-flex flex-column gap-2">
                    ${reviewHtml}
                </div>
            `;
        }
    },

    /**
     * Handle Claim / View Certificate Action.
     */
    async handleCertificateAction() {
        if (this._certificate) {
            this.showCertificateModal(this._certificate);
            return;
        }

        const btn = document.getElementById('btnClaimOrViewCert');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Claiming...';
        }

        try {
            const cert = await apiRequest(`/certificates/claim/${this._enrollmentId}/`, 'POST');
            this._certificate = cert;
            this.showCertificateModal(cert);
            await this.loadLearningData();
        } catch (err) {
            alert(err.message || 'Unable to claim certificate. Please ensure all assessments are passed.');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `<i class="bi bi-award me-1"></i><span id="btnCertText">${this._certificate ? 'View Certificate' : 'Claim Certificate'}</span>`;
            }
        }
    },

    /**
     * Populate and show the trainee certificate modal.
     */
    showCertificateModal(cert) {
        if (!cert) return;
        const nameEl = document.getElementById('modalCertTraineeName');
        const courseEl = document.getElementById('modalCertCourseTitle');
        const catEl = document.getElementById('modalCertCategory');
        const gradeEl = document.getElementById('modalCertGrade');
        const dateEl = document.getElementById('modalCertDate');
        const instEl = document.getElementById('modalCertInstructor');
        const codeEl = document.getElementById('modalCertCode');
        const statusEl = document.getElementById('modalCertStatus');
        const verifyLinkEl = document.getElementById('modalCertVerifyLink');

        if (nameEl) nameEl.textContent = cert.trainee_name || cert.trainee_username || 'Trainee';
        if (courseEl) courseEl.textContent = cert.course_title || (this._course ? this._course.title : 'Course');
        if (catEl) catEl.textContent = cert.course_category || (this._course ? this._course.category : 'General');
        if (gradeEl) gradeEl.textContent = `${cert.final_grade_percentage || 100.0}%`;
        if (dateEl) {
            const d = cert.issued_at ? new Date(cert.issued_at) : new Date();
            dateEl.textContent = d.toLocaleDateString();
        }
        if (instEl) instEl.textContent = cert.trainer_name || 'Capacity Connect Instructor';
        if (codeEl) codeEl.textContent = cert.certificate_code || '';
        if (statusEl) {
            statusEl.textContent = cert.is_revoked ? 'REVOKED' : 'VALID';
            statusEl.className = cert.is_revoked ? 'badge bg-danger' : 'badge bg-success';
        }
        if (verifyLinkEl) {
            verifyLinkEl.href = `verify-certificate.html?code=${encodeURIComponent(cert.certificate_code || '')}`;
        }

        const modalEl = document.getElementById('traineeCertificateModal');
        if (modalEl) {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        }
    },

    /**
     * XSS sanitizer.
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

window.CourseLearnController = CourseLearnController;
