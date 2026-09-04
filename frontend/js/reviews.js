/**
 * reviews.js
 * Frontend controller for Step 14: Course Reviews, Ratings & Social Proof Engine.
 */

const ReviewsController = {
    activeCourseId: null,
    courseReviewsData: null,
    myReview: null,

    /**
     * Load reviews and rating distribution for a given course.
     * @param {number} courseId
     */
    async loadCourseReviews(courseId) {
        this.activeCourseId = courseId;
        const container = document.getElementById('courseReviewsList');
        const summaryContainer = document.getElementById('courseRatingSummary');

        if (!container) return;

        try {
            const data = await apiRequest(`/courses/${courseId}/reviews/`);
            this.courseReviewsData = data;

            this.renderRatingSummary(data, summaryContainer);
            this.renderReviewsList(data.reviews || [], container);

            // Fetch my review if authenticated
            if (typeof Auth !== 'undefined' && Auth.getUser()) {
                await this.loadMyReview(courseId);
            }
        } catch (err) {
            console.debug('[Reviews] Error loading course reviews:', err.message);
            if (container) {
                container.innerHTML = `<div class="text-muted small py-3">Could not load student reviews at this time.</div>`;
            }
        }
    },

    /**
     * Render the overall score and 5-star distribution breakdown.
     */
    renderRatingSummary(data, container) {
        if (!container) return;

        const avg = parseFloat(data.average_rating) || 0;
        const total = data.review_count || 0;
        const dist = data.rating_distribution || { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };

        const starsHtml = this.generateStarsHtml(avg, 'fs-4 text-warning');

        // Distribution bars
        const barsHtml = [5, 4, 3, 2, 1].map(stars => {
            const count = dist[stars] || dist[String(stars)] || 0;
            const pct = total > 0 ? Math.round((count / total) * 100) : 0;

            return `
                <div class="d-flex align-items-center mb-1 small">
                    <span class="text-muted me-2" style="width: 45px;">${stars} <i class="bi bi-star-fill text-warning" style="font-size:0.75rem;"></i></span>
                    <div class="progress flex-grow-1" style="height: 8px;">
                        <div class="progress-bar bg-warning" role="progressbar" style="width: ${pct}%;" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                    <span class="text-muted ms-2 text-end" style="width: 35px;">${count}</span>
                </div>
            `;
        }).join('');

        container.innerHTML = `
            <div class="row align-items-center g-3">
                <div class="col-sm-5 text-center text-sm-start border-end-sm">
                    <div class="display-5 fw-bold text-dark mb-0">${avg.toFixed(1)}</div>
                    <div class="mb-1">${starsHtml}</div>
                    <div class="text-muted small">Course Rating &bull; ${total} ${total === 1 ? 'review' : 'reviews'}</div>
                </div>
                <div class="col-sm-7">
                    ${barsHtml}
                </div>
            </div>
        `;
    },

    /**
     * Render the individual verified student review cards.
     */
    renderReviewsList(reviews, container) {
        if (!container) return;

        if (!reviews || reviews.length === 0) {
            container.innerHTML = `
                <div class="text-center py-4 text-muted">
                    <i class="bi bi-chat-square-heart fs-2 text-muted mb-2 d-block"></i>
                    <h6 class="fw-bold text-dark">No Student Reviews Yet</h6>
                    <p class="small mb-0">Be the first enrolled trainee to share your feedback and experience.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = reviews.map(r => {
            const dateStr = r.created_at ? new Date(r.created_at).toLocaleDateString() : '';
            const stars = this.generateStarsHtml(r.rating, 'text-warning');
            const initial = (r.trainee_username || 'U')[0].toUpperCase();

            return `
                <div class="border-bottom py-3">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div class="d-flex align-items-center">
                            <div class="bg-primary-subtle text-primary rounded-circle d-flex align-items-center justify-content-center me-2 fw-bold small" style="width: 36px; height: 36px;">
                                ${initial}
                            </div>
                            <div>
                                <div class="fw-semibold text-dark small">${this.escapeHtml(r.trainee_username)} <span class="badge bg-light text-secondary ms-1" style="font-size:0.68rem;"><i class="bi bi-patch-check-fill text-success me-1"></i>Verified Student</span></div>
                                <div class="text-muted" style="font-size:0.75rem;">${dateStr}</div>
                            </div>
                        </div>
                        <div>${stars}</div>
                    </div>
                    ${r.title ? `<h6 class="fw-bold text-dark small mb-1">${this.escapeHtml(r.title)}</h6>` : ''}
                    <p class="text-secondary small mb-0" style="white-space: pre-line; line-height: 1.5;">${this.escapeHtml(r.comment)}</p>
                </div>
            `;
        }).join('');
    },

    /**
     * Fetch existing review authored by currently logged in trainee.
     */
    async loadMyReview(courseId) {
        try {
            const review = await apiRequest(`/courses/${courseId}/reviews/my-review/`);
            this.myReview = review;

            const reviewBtn = document.getElementById('btnWriteCourseReview');
            if (reviewBtn) {
                if (review) {
                    reviewBtn.innerHTML = `<i class="bi bi-pencil me-1"></i>Edit Your Review (${review.rating}★)`;
                    reviewBtn.classList.remove('btn-outline-primary');
                    reviewBtn.classList.add('btn-outline-secondary');
                } else {
                    reviewBtn.innerHTML = `<i class="bi bi-star me-1"></i>Write a Review`;
                    reviewBtn.classList.remove('btn-outline-secondary');
                    reviewBtn.classList.add('btn-outline-primary');
                }
            }
        } catch (e) {
            console.debug('[Reviews] No my-review found or unauthenticated:', e.message);
        }
    },

    /**
     * Open the Review Submission Modal.
     */
    openReviewModal(courseId, courseTitle = '') {
        const modalEl = document.getElementById('courseReviewModal');
        if (!modalEl) return;

        document.getElementById('reviewCourseTitle').textContent = courseTitle || 'Course';
        document.getElementById('reviewCourseId').value = courseId;

        // Reset inputs
        document.getElementById('reviewTitleInput').value = '';
        document.getElementById('reviewCommentInput').value = '';
        this.setRatingInput(5);

        // Pre-fill if editing existing review
        if (this.myReview) {
            document.getElementById('reviewTitleInput').value = this.myReview.title || '';
            document.getElementById('reviewCommentInput').value = this.myReview.comment || '';
            this.setRatingInput(this.myReview.rating || 5);
        }

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
    },

    setRatingInput(score) {
        document.getElementById('reviewRatingScore').value = score;
        const stars = document.querySelectorAll('.review-star-btn');
        stars.forEach((star, idx) => {
            const val = idx + 1;
            if (val <= score) {
                star.classList.remove('bi-star', 'text-muted');
                star.classList.add('bi-star-fill', 'text-warning');
            } else {
                star.classList.remove('bi-star-fill', 'text-warning');
                star.classList.add('bi-star', 'text-muted');
            }
        });
    },

    /**
     * Submit review (create or update).
     */
    async handleReviewSubmit() {
        const courseId = document.getElementById('reviewCourseId')?.value || this.activeCourseId;
        const rating = parseInt(document.getElementById('reviewRatingScore')?.value, 10) || 5;
        const title = document.getElementById('reviewTitleInput')?.value?.trim() || '';
        const comment = document.getElementById('reviewCommentInput')?.value?.trim() || '';

        if (!comment || comment.length < 5) {
            alert('Please share your feedback (minimum 5 characters).');
            return;
        }

        const payload = { rating, title, comment };

        try {
            await apiRequest(`/courses/${courseId}/reviews/`, {
                method: 'POST',
                body: JSON.stringify(payload),
            });

            const modalEl = document.getElementById('courseReviewModal');
            if (modalEl) {
                const modal = bootstrap.Modal.getInstance(modalEl);
                if (modal) modal.hide();
            }

            alert('Thank you! Your course review and rating have been posted.');
            await this.loadCourseReviews(courseId);
        } catch (err) {
            alert(`Failed to submit review: ${err.message}`);
        }
    },

    /**
     * Helper to render Star icons from rating value.
     */
    generateStarsHtml(rating, extraClass = '') {
        const fullStars = Math.floor(rating);
        const hasHalf = (rating - fullStars) >= 0.5;
        let html = `<span class="${extraClass}">`;

        for (let i = 1; i <= 5; i++) {
            if (i <= fullStars) {
                html += '<i class="bi bi-star-fill"></i>';
            } else if (i === fullStars + 1 && hasHalf) {
                html += '<i class="bi bi-star-half"></i>';
            } else {
                html += '<i class="bi bi-star text-secondary text-opacity-50"></i>';
            }
        }
        html += '</span>';
        return html;
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
