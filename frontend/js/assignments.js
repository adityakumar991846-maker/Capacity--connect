/**
 * assignments.js
 * Frontend controller for Step 13: Hands-On Assignments, Practical Projects & Grading Workbench.
 */

const AssignmentsController = {
    courseAssignments: [],
    activeSubmissionId: null,

    // =========================================================================
    // TRAINEE LEARNING ROOM INTEGRATION
    // =========================================================================

    async loadCourseAssignments(courseId) {
        try {
            const data = await apiRequest(`/assignments/courses/${courseId}/`);
            this.courseAssignments = Array.isArray(data) ? data : [];
            return this.courseAssignments;
        } catch (err) {
            console.debug('[Assignments] Could not load assignments:', err.message);
            this.courseAssignments = [];
            return [];
        }
    },

    renderModuleAssignment(subjectId, container) {
        if (!container) return;

        // Find assignment matching this subject, or capstone if subjectId is null
        const assignment = this.courseAssignments.find(a => 
            subjectId ? a.subject === subjectId : !a.subject
        );

        if (!assignment) {
            container.innerHTML = '';
            container.classList.add('d-none');
            return;
        }

        container.classList.remove('d-none');

        const mySub = assignment.my_submission;
        let statusBadge = '<span class="badge bg-secondary">Not Submitted</span>';
        let reviewCard = '';
        let submitBtnText = 'Submit Project Deliverable';

        if (mySub) {
            if (mySub.status === 'DRAFT') {
                statusBadge = '<span class="badge bg-warning-subtle text-warning">Draft Saved</span>';
                submitBtnText = 'Resume / Submit Deliverable';
            } else if (mySub.status === 'SUBMITTED' || mySub.status === 'UNDER_REVIEW') {
                statusBadge = '<span class="badge bg-info-subtle text-info"><i class="bi bi-hourglass-split me-1"></i>Awaiting Evaluation</span>';
                submitBtnText = 'Update Submission';
            } else if (mySub.status === 'GRADED') {
                if (mySub.review && mySub.review.passed) {
                    statusBadge = `<span class="badge bg-success"><i class="bi bi-check-circle-fill me-1"></i>Passed (${mySub.review.score}/${assignment.max_score})</span>`;
                    submitBtnText = 'View / Update Submission';
                } else {
                    statusBadge = `<span class="badge bg-danger">Not Passed (${mySub.review ? mySub.review.score : 0}/${assignment.max_score})</span>`;
                    submitBtnText = 'Resubmit Project';
                }
            } else if (mySub.status === 'RESUBMISSION_REQUESTED') {
                statusBadge = '<span class="badge bg-danger-subtle text-danger fw-bold"><i class="bi bi-exclamation-triangle-fill me-1"></i>Resubmission Requested</span>';
                submitBtnText = 'Revise &amp; Resubmit';
            }

            if (mySub.review) {
                const passedAlertClass = mySub.review.passed ? 'alert-success' : 'alert-danger';
                reviewCard = `
                    <div class="alert ${passedAlertClass} mt-3 mb-0 rounded-3 p-3 small">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="fw-bold"><i class="bi bi-patch-check-fill me-1"></i>Instructor Evaluation</span>
                            <span class="fw-bold fs-6">${mySub.review.score} / ${assignment.max_score}</span>
                        </div>
                        <div class="text-secondary" style="white-space: pre-line;">${this.escapeHtml(mySub.review.feedback)}</div>
                    </div>
                `;
            }
        }

        const typeIcon = {
            'LINK': '<i class="bi bi-link-45deg me-1"></i>Project Repository / Demo Link',
            'TEXT': '<i class="bi bi-code-square me-1"></i>Written Code / Analysis',
            'FILE': '<i class="bi bi-file-earmark-arrow-up me-1"></i>Document Attachment',
            'HYBRID': '<i class="bi bi-layers me-1"></i>Link &amp; Written Report',
        }[assignment.submission_type] || 'Deliverable';

        container.innerHTML = `
            <div class="card border-primary border-opacity-25 bg-primary bg-opacity-10 rounded-3 p-3 my-4 shadow-sm">
                <div class="d-flex flex-column flex-sm-row justify-content-between align-items-sm-start gap-2 mb-2">
                    <div>
                        <div class="d-flex align-items-center gap-2 mb-1 flex-wrap">
                            <span class="badge bg-primary text-white"><i class="bi bi-tools me-1"></i>Hands-On Project</span>
                            ${statusBadge}
                            ${assignment.is_mandatory ? '<span class="badge bg-danger-subtle text-danger" style="font-size:0.7rem;">Required for Certificate</span>' : ''}
                        </div>
                        <h5 class="fw-bold text-dark mb-1">${this.escapeHtml(assignment.title)}</h5>
                        <div class="text-muted small">
                            Passing: ${assignment.passing_score}/${assignment.max_score} pts &bull; Deliverable: ${typeIcon}
                        </div>
                    </div>
                    <button class="btn btn-primary btn-sm px-3 fw-semibold text-nowrap mt-2 mt-sm-0" onclick="AssignmentsController.openSubmitModal(${assignment.id});">
                        <i class="bi bi-cloud-arrow-up-fill me-1"></i>${submitBtnText}
                    </button>
                </div>

                <div class="text-secondary small mt-2 p-2 bg-white bg-opacity-75 rounded-2" style="white-space: pre-line; line-height: 1.5;">
                    ${this.escapeHtml(assignment.description)}
                </div>

                ${reviewCard}
            </div>
        `;
    },

    async openSubmitModal(assignmentId) {
        const assignment = this.courseAssignments.find(a => a.id === assignmentId);
        if (!assignment) return;

        const modalEl = document.getElementById('assignmentSubmitModal');
        if (!modalEl) return;

        document.getElementById('submitAssignmentTitle').textContent = assignment.title;
        document.getElementById('submitAssignmentGuidelines').textContent = assignment.description;
        document.getElementById('submitAssignmentMaxScore').textContent = `${assignment.passing_score} / ${assignment.max_score} pts required`;
        document.getElementById('submitAssignmentId').value = assignment.id;

        const linkInput = document.getElementById('assignmentLinkInput');
        const textInput = document.getElementById('assignmentTextInput');
        if (linkInput) linkInput.value = '';
        if (textInput) textInput.value = '';

        // Pre-fill existing submission if available
        try {
            const sub = await apiRequest(`/assignments/${assignmentId}/my-submission/`);
            if (sub) {
                if (linkInput && sub.submission_link) linkInput.value = sub.submission_link;
                if (textInput && sub.submission_text) textInput.value = sub.submission_text;
            }
        } catch (e) {
            // No prior submission, clean form
        }

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
    },

    async handleAssignmentSubmit(isDraft = false) {
        const assignmentId = document.getElementById('submitAssignmentId')?.value;
        const link = document.getElementById('assignmentLinkInput')?.value?.trim() || '';
        const text = document.getElementById('assignmentTextInput')?.value?.trim() || '';

        if (!isDraft && !link && !text) {
            alert('Please provide a project URL link or written deliverable before submitting.');
            return;
        }

        const payload = {
            submission_link: link,
            submission_text: text,
            status: isDraft ? 'DRAFT' : 'SUBMITTED',
        };

        try {
            await apiRequest(`/assignments/${assignmentId}/submit/`, {
                method: 'POST',
                body: JSON.stringify(payload),
            });

            const modalEl = document.getElementById('assignmentSubmitModal');
            if (modalEl) {
                const modal = bootstrap.Modal.getInstance(modalEl);
                if (modal) modal.hide();
            }

            alert(isDraft ? 'Draft saved successfully!' : 'Project deliverable submitted for evaluation!');

            // Reload course assignments and refresh view
            if (CourseLearnController && CourseLearnController._course) {
                await this.loadCourseAssignments(CourseLearnController._course.id);
                const currentSp = CourseLearnController._enrollment.subject_progresses[CourseLearnController._activeSubjectIndex];
                if (currentSp) {
                    const container = document.getElementById('moduleAssignmentContainer');
                    this.renderModuleAssignment(currentSp.subject_id, container);
                }
            }
        } catch (err) {
            alert(`Submission failed: ${err.message}`);
        }
    },

    // =========================================================================
    // TRAINER GRADING WORKBENCH
    // =========================================================================

    async loadTrainerPendingReviews(statusFilter = '') {
        const container = document.getElementById('trainerAssignmentsContainer');
        if (!container) return;

        container.innerHTML = `
            <div class="text-center py-4">
                <div class="spinner-border spinner-border-sm text-primary"></div>
                <p class="text-muted small mt-2 mb-0">Loading submissions awaiting review...</p>
            </div>
        `;

        try {
            let url = '/assignments/trainer/pending-reviews/';
            if (statusFilter) url += `?status=${statusFilter}`;

            const submissions = await apiRequest(url);
            const list = Array.isArray(submissions) ? submissions : [];

            // Update badge in workbench card
            const badge = document.getElementById('pendingSubmissionsBadge');
            if (badge) {
                badge.textContent = `${list.length} Pending`;
                badge.classList.toggle('d-none', list.length === 0);
            }

            if (list.length === 0) {
                container.innerHTML = `
                    <div class="p-4 text-center bg-light rounded-3">
                        <i class="bi bi-clipboard-check fs-2 text-success mb-2 d-block"></i>
                        <h6 class="fw-bold text-dark">All Submissions Graded</h6>
                        <p class="text-muted small mb-0">No trainee project submissions are currently pending evaluation.</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = `
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0 small">
                        <thead class="table-light text-secondary text-uppercase" style="font-size:0.75rem;">
                            <tr>
                                <th class="ps-3">Student</th>
                                <th>Assignment &amp; Course</th>
                                <th>Deliverable</th>
                                <th>Status</th>
                                <th>Submitted</th>
                                <th class="text-end pe-3">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${list.map(s => {
                                const deliverableLink = s.submission_link
                                    ? `<a href="${this.escapeHtml(s.submission_link)}" target="_blank" class="text-primary text-decoration-none fw-semibold"><i class="bi bi-box-arrow-up-right me-1"></i>Inspect Link</a>`
                                    : '<span class="text-muted">Written response</span>';

                                return `
                                    <tr>
                                        <td class="ps-3">
                                            <div class="fw-bold text-dark">${this.escapeHtml(s.trainee_username)}</div>
                                            <div class="text-muted" style="font-size:0.75rem;">${this.escapeHtml(s.trainee_email)}</div>
                                        </td>
                                        <td>
                                            <div class="fw-semibold text-dark">${this.escapeHtml(s.assignment_title)}</div>
                                            <div class="text-muted" style="font-size:0.72rem;">${this.escapeHtml(s.course_title)} &bull; Pass: ${s.passing_score}/${s.max_score}</div>
                                        </td>
                                        <td>${deliverableLink}</td>
                                        <td>
                                            <span class="badge bg-warning-subtle text-warning">${s.status}</span>
                                        </td>
                                        <td>${new Date(s.submitted_at).toLocaleDateString()}</td>
                                        <td class="text-end pe-3">
                                            <button class="btn btn-primary btn-sm py-0 px-3 fw-semibold" onclick="AssignmentsController.openGradingModal(${s.id}, ${JSON.stringify(s).replace(/"/g, '&quot;')})">
                                                <i class="bi bi-pencil-square me-1"></i>Grade
                                            </button>
                                        </td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        } catch (err) {
            console.error('[Assignments] Error loading trainer pending reviews:', err);
            container.innerHTML = `<div class="alert alert-danger small m-3">${this.escapeHtml(err.message)}</div>`;
        }
    },

    openGradingModal(submissionId, submissionData) {
        this.activeSubmissionId = submissionId;
        const modalEl = document.getElementById('gradingWorkbenchModal');
        if (!modalEl) return;

        document.getElementById('gradeModalStudent').textContent = submissionData.trainee_username;
        document.getElementById('gradeModalAssignment').textContent = submissionData.assignment_title;
        document.getElementById('gradeModalScoreHelp').textContent = `Passing threshold: ${submissionData.passing_score} / ${submissionData.max_score} pts.`;
        document.getElementById('gradeScoreInput').max = submissionData.max_score;
        document.getElementById('gradeScoreInput').value = submissionData.passing_score;
        document.getElementById('gradeFeedbackInput').value = '';

        const deliverableBox = document.getElementById('gradeModalDeliverable');
        if (deliverableBox) {
            let html = '';
            if (submissionData.submission_link) {
                html += `<div class="mb-2"><strong>Project URL:</strong> <a href="${this.escapeHtml(submissionData.submission_link)}" target="_blank" class="fw-bold text-primary"><i class="bi bi-box-arrow-up-right me-1"></i>${this.escapeHtml(submissionData.submission_link)}</a></div>`;
            }
            if (submissionData.submission_text) {
                html += `<div><strong>Written Analysis:</strong><div class="p-2 bg-light rounded mt-1 small" style="white-space:pre-line;">${this.escapeHtml(submissionData.submission_text)}</div></div>`;
            }
            deliverableBox.innerHTML = html || '<div class="text-muted small">No deliverable content.</div>';
        }

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
    },

    async submitEvaluation(requestResubmission = false) {
        const score = parseInt(document.getElementById('gradeScoreInput')?.value, 10);
        const feedback = document.getElementById('gradeFeedbackInput')?.value?.trim();

        if (isNaN(score) || score < 0) {
            alert('Please enter a valid numeric score.');
            return;
        }
        if (!feedback || feedback.length < 5) {
            alert('Please provide detailed instructor feedback (at least 5 characters).');
            return;
        }

        const payload = {
            score,
            feedback,
            request_resubmission: requestResubmission,
        };

        try {
            await apiRequest(`/assignments/submissions/${this.activeSubmissionId}/grade/`, {
                method: 'POST',
                body: JSON.stringify(payload),
            });

            const modalEl = document.getElementById('gradingWorkbenchModal');
            if (modalEl) {
                const modal = bootstrap.Modal.getInstance(modalEl);
                if (modal) modal.hide();
            }

            alert(requestResubmission ? 'Resubmission requested with feedback.' : 'Grade submitted successfully!');
            this.loadTrainerPendingReviews();
        } catch (err) {
            alert(`Failed to grade submission: ${err.message}`);
        }
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
