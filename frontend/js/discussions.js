/**
 * discussions.js
 * Frontend controller for Step 12: Course Discussion, Q&A & Announcements Engine.
 */

const DiscussionsController = {
    activeCourseId: null,
    activeSubjectId: null,
    activeTab: 'all', // 'all', 'subject', 'unresolved', 'announcements'
    activeThreadId: null,
    searchQuery: '',

    // =========================================================================
    // INITIALIZATION & NOTIFICATIONS
    // =========================================================================

    async initNotifications() {
        try {
            const data = await apiRequest('/discussions/notifications/');
            this.renderNotificationBadge(data.unread_count || 0);
            this.renderNotificationsList(data.notifications || []);
        } catch (err) {
            console.debug('[Discussions] Notification check skipped:', err.message);
        }
    },

    renderNotificationBadge(count) {
        const badge = document.getElementById('discussionNotificationBadge');
        if (!badge) return;

        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.classList.remove('d-none');
        } else {
            badge.classList.add('d-none');
        }
    },

    renderNotificationsList(notifications) {
        const container = document.getElementById('discussionNotificationsList');
        if (!container) return;

        if (!notifications || notifications.length === 0) {
            container.innerHTML = `
                <div class="p-3 text-center text-muted small">
                    <i class="bi bi-bell-slash fs-4 d-block mb-1"></i>
                    No new notifications
                </div>
            `;
            return;
        }

        container.innerHTML = notifications.map(n => {
            const icon = n.notification_type === 'NEW_ANNOUNCEMENT'
                ? '<i class="bi bi-megaphone-fill text-warning me-2"></i>'
                : '<i class="bi bi-chat-dots-fill text-primary me-2"></i>';
            const unreadClass = n.is_read ? '' : 'bg-light fw-semibold';

            return `
                <a href="#" class="dropdown-item py-2 border-bottom ${unreadClass}" onclick="DiscussionsController.handleNotificationClick(${n.id}, ${n.thread_id}, ${n.course_id}); return false;">
                    <div class="d-flex align-items-start">
                        <div class="mt-1">${icon}</div>
                        <div class="flex-grow-1 text-truncate">
                            <div class="small text-dark mb-0">${this.escapeHtml(n.title)}</div>
                            <div class="text-muted" style="font-size: 0.75rem;">${this.escapeHtml(n.message)}</div>
                            <div class="text-secondary" style="font-size: 0.7rem;">${new Date(n.created_at).toLocaleString()}</div>
                        </div>
                    </div>
                </a>
            `;
        }).join('');
    },

    async handleNotificationClick(notifId, threadId, courseId) {
        try {
            await apiRequest(`/discussions/notifications/${notifId}/read/`, { method: 'POST' });
            this.initNotifications();
            if (this.activeCourseId === courseId) {
                this.openThreadDetailModal(threadId);
            } else {
                window.location.href = `course-learn.html?id=${courseId}&thread=${threadId}`;
            }
        } catch (err) {
            console.error('[Discussions] Error reading notification:', err);
        }
    },

    async markAllNotificationsRead() {
        try {
            await apiRequest('/discussions/notifications/read-all/', { method: 'POST' });
            this.initNotifications();
        } catch (err) {
            console.error('[Discussions] Error marking all read:', err);
        }
    },

    // =========================================================================
    // COURSE LEARNING ROOM Q&A & DISCUSSIONS
    // =========================================================================

    initCourseDiscussions(courseId, subjectId) {
        this.activeCourseId = courseId;
        this.activeSubjectId = subjectId;
        this.loadThreads();
        this.initNotifications();

        // Check URL params for deep linked thread
        const params = new URLSearchParams(window.location.search);
        const threadParam = params.get('thread');
        if (threadParam) {
            this.openThreadDetailModal(parseInt(threadParam, 10));
        }
    },

    setActiveSubject(subjectId) {
        this.activeSubjectId = subjectId;
        if (this.activeTab === 'subject') {
            this.loadThreads();
        }
    },

    setFilterTab(tabName) {
        this.activeTab = tabName;
        document.querySelectorAll('.discussion-filter-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });
        this.loadThreads();
    },

    async loadThreads() {
        const container = document.getElementById('discussionsThreadList');
        if (!container) return;

        container.innerHTML = `
            <div class="text-center py-4">
                <div class="spinner-border spinner-border-sm text-primary"></div>
                <p class="text-muted small mt-2 mb-0">Loading community discussions...</p>
            </div>
        `;

        try {
            let url = `/discussions/courses/${this.activeCourseId}/?`;
            const params = [];

            if (this.activeTab === 'subject' && this.activeSubjectId) {
                params.push(`subject_id=${this.activeSubjectId}`);
            } else if (this.activeTab === 'announcements') {
                params.push('type=ANNOUNCEMENT');
            } else if (this.activeTab === 'unresolved') {
                params.push('type=QUESTION&resolved=false');
            }

            if (this.searchQuery) {
                params.push(`search=${encodeURIComponent(this.searchQuery)}`);
            }

            url += params.join('&');
            const threads = await apiRequest(url);

            if (!Array.isArray(threads) || threads.length === 0) {
                const emptyMsg = this.activeTab === 'announcements'
                    ? 'No announcements posted for this course yet.'
                    : 'No discussions found. Be the first to start a conversation!';
                container.innerHTML = `
                    <div class="p-4 text-center bg-light rounded-3">
                        <i class="bi bi-chat-square-text fs-2 text-muted mb-2 d-block"></i>
                        <h6 class="fw-bold text-dark">No Discussions Found</h6>
                        <p class="text-muted small mb-0">${emptyMsg}</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = threads.map(t => this.renderThreadCard(t)).join('');
        } catch (err) {
            console.error('[Discussions] Error loading threads:', err);
            container.innerHTML = `
                <div class="alert alert-danger small m-3">
                    Failed to load discussions: ${this.escapeHtml(err.message)}
                </div>
            `;
        }
    },

    renderThreadCard(t) {
        const typeBadge = {
            'ANNOUNCEMENT': '<span class="badge bg-warning text-dark"><i class="bi bi-megaphone-fill me-1"></i>Announcement</span>',
            'QUESTION': '<span class="badge bg-info-subtle text-info"><i class="bi bi-question-circle me-1"></i>Question</span>',
            'DISCUSSION': '<span class="badge bg-secondary-subtle text-secondary"><i class="bi bi-chat-left-text me-1"></i>Discussion</span>',
        }[t.thread_type] || '';

        const resolvedBadge = t.is_resolved
            ? '<span class="badge bg-success-subtle text-success ms-1"><i class="bi bi-check-circle-fill me-1"></i>Resolved</span>'
            : '';

        const pinnedBadge = t.is_pinned
            ? '<span class="badge bg-primary-subtle text-primary ms-1"><i class="bi bi-pin-angle-fill me-1"></i>Pinned</span>'
            : '';

        const moduleTag = t.subject_title
            ? `<span class="badge bg-light text-muted border me-2" style="font-size: 0.72rem;"><i class="bi bi-journal-text me-1"></i>${this.escapeHtml(t.subject_title)}</span>`
            : '';

        const authorBadge = t.is_course_trainer
            ? '<span class="badge bg-warning-subtle text-dark border border-warning ms-1" style="font-size:0.65rem;">Trainer</span>'
            : '';

        const instructorReplyBadge = t.has_instructor_reply
            ? '<span class="badge bg-success-subtle text-success ms-2" style="font-size:0.7rem;"><i class="bi bi-patch-check-fill me-1"></i>Trainer Replied</span>'
            : '';

        const upvoteActiveClass = t.has_upvoted ? 'btn-primary text-white' : 'btn-outline-secondary';

        return `
            <div class="card border mb-3 shadow-sm rounded-3 discussion-thread-card ${t.is_pinned ? 'border-primary' : ''}">
                <div class="card-body p-3">
                    <div class="d-flex align-items-start gap-3">
                        <!-- Upvote Column -->
                        <div class="text-center d-flex flex-column align-items-center">
                            <button class="btn btn-sm ${upvoteActiveClass} py-1 px-2 mb-1"
                                    onclick="DiscussionsController.toggleUpvote(${t.id}, event)"
                                    title="Upvote">
                                <i class="bi bi-caret-up-fill"></i>
                            </button>
                            <span class="small fw-bold text-secondary" id="upvote-count-${t.id}">${t.upvotes_count || 0}</span>
                        </div>

                        <!-- Thread Content Column -->
                        <div class="flex-grow-1" style="cursor: pointer;" onclick="DiscussionsController.openThreadDetailModal(${t.id});">
                            <div class="d-flex align-items-center flex-wrap gap-1 mb-1">
                                ${typeBadge}
                                ${pinnedBadge}
                                ${resolvedBadge}
                                ${instructorReplyBadge}
                            </div>
                            <h6 class="fw-bold text-dark mb-1 hover-primary">${this.escapeHtml(t.title)}</h6>
                            <div class="d-flex align-items-center text-muted small flex-wrap" style="font-size: 0.78rem;">
                                ${moduleTag}
                                <span class="me-2">Posted by <strong>${this.escapeHtml(t.author_username)}</strong>${authorBadge}</span>
                                <span class="me-2">&bull; ${new Date(t.created_at).toLocaleDateString()}</span>
                                <span class="ms-auto"><i class="bi bi-chat-dots me-1"></i>${t.replies_count || 0} replies</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    async toggleUpvote(threadId, event) {
        if (event) event.stopPropagation();
        try {
            const res = await apiRequest(`/discussions/${threadId}/upvote/`, { method: 'POST' });
            const countEl = document.getElementById(`upvote-count-${threadId}`);
            if (countEl) countEl.textContent = res.upvotes_count;

            const btn = event.currentTarget;
            if (btn) {
                if (res.upvoted) {
                    btn.classList.remove('btn-outline-secondary');
                    btn.classList.add('btn-primary', 'text-white');
                } else {
                    btn.classList.remove('btn-primary', 'text-white');
                    btn.classList.add('btn-outline-secondary');
                }
            }
        } catch (err) {
            alert(`Could not upvote: ${err.message}`);
        }
    },

    // =========================================================================
    // THREAD DETAILS & REPLIES
    // =========================================================================

    async openThreadDetailModal(threadId) {
        this.activeThreadId = threadId;
        const modalEl = document.getElementById('threadDetailModal');
        if (!modalEl) return;

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();

        const container = document.getElementById('threadDetailContent');
        container.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary"></div>
                <p class="text-muted small mt-2">Loading discussion details...</p>
            </div>
        `;

        try {
            const t = await apiRequest(`/discussions/${threadId}/`);
            this.renderThreadDetail(t);
        } catch (err) {
            container.innerHTML = `<div class="alert alert-danger">${this.escapeHtml(err.message)}</div>`;
        }
    },

    renderThreadDetail(t) {
        const container = document.getElementById('threadDetailContent');
        if (!container) return;

        const resolveBtn = t.can_resolve
            ? `<button class="btn btn-sm ${t.is_resolved ? 'btn-outline-secondary' : 'btn-success'} me-2" onclick="DiscussionsController.toggleResolve(${t.id})">
                 <i class="bi bi-check-circle me-1"></i>${t.is_resolved ? 'Reopen Question' : 'Mark Resolved'}
               </button>`
            : '';

        const pinBtn = t.can_pin
            ? `<button class="btn btn-sm btn-outline-primary me-2" onclick="DiscussionsController.togglePin(${t.id})">
                 <i class="bi bi-pin-angle me-1"></i>${t.is_pinned ? 'Unpin' : 'Pin to Top'}
               </button>`
            : '';

        const deleteBtn = t.can_delete
            ? `<button class="btn btn-sm btn-outline-danger" onclick="DiscussionsController.deleteThread(${t.id})">
                 <i class="bi bi-trash me-1"></i>Delete
               </button>`
            : '';

        const resolvedBadge = t.is_resolved
            ? '<span class="badge bg-success-subtle text-success me-2"><i class="bi bi-check-circle-fill me-1"></i>Resolved</span>'
            : '';

        const authorBadge = t.is_course_trainer
            ? '<span class="badge bg-warning text-dark ms-1">Trainer</span>'
            : '<span class="badge bg-info-subtle text-info ms-1">Trainee</span>';

        const repliesHtml = (t.replies || []).map(r => this.renderReplyCard(r, t)).join('');

        container.innerHTML = `
            <div class="p-3">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <div>
                        <span class="badge bg-secondary-subtle text-secondary me-2">${t.thread_type}</span>
                        ${resolvedBadge}
                        ${t.subject_title ? `<span class="badge bg-light text-muted border"><i class="bi bi-journal-text me-1"></i>${this.escapeHtml(t.subject_title)}</span>` : ''}
                    </div>
                    <div class="d-flex">
                        ${resolveBtn}
                        ${pinBtn}
                        ${deleteBtn}
                    </div>
                </div>

                <h4 class="fw-bold text-dark mb-2">${this.escapeHtml(t.title)}</h4>

                <div class="d-flex align-items-center text-muted small mb-3 pb-2 border-bottom">
                    <span class="me-2">Asked by <strong>${this.escapeHtml(t.author_username)}</strong>${authorBadge}</span>
                    <span>&bull; ${new Date(t.created_at).toLocaleString()}</span>
                </div>

                <div class="text-secondary mb-4 p-3 bg-light rounded-3" style="white-space: pre-line; line-height: 1.6;">
                    ${this.escapeHtml(t.content)}
                </div>

                <h6 class="fw-bold text-dark mb-3">
                    <i class="bi bi-chat-dots me-2 text-primary"></i>Replies (${t.replies ? t.replies.length : 0})
                </h6>

                <div class="replies-list mb-4" id="threadRepliesList">
                    ${repliesHtml || '<div class="text-muted small py-3 text-center bg-light rounded-3">No replies yet. Be the first to answer!</div>'}
                </div>

                <!-- Add Reply Form -->
                <div class="border-top pt-3">
                    <h6 class="fw-bold text-dark mb-2 small">Your Response</h6>
                    <textarea class="form-control mb-2 small" id="newReplyContent" rows="3" placeholder="Share your insights, code explanation, or answer..."></textarea>
                    <div class="text-end">
                        <button class="btn btn-primary btn-sm px-3 fw-semibold" onclick="DiscussionsController.submitReply(${t.id})">
                            <i class="bi bi-send me-1"></i>Post Reply
                        </button>
                    </div>
                </div>
            </div>
        `;
    },

    renderReplyCard(r, thread) {
        const endorsedClass = r.is_instructor_endorsed ? 'border-success bg-success-subtle bg-opacity-10' : 'border-light bg-light';
        const endorsedBadge = r.is_instructor_endorsed
            ? '<span class="badge bg-success text-white mb-2 d-inline-block"><i class="bi bi-patch-check-fill me-1"></i>Instructor Endorsed Solution</span>'
            : '';

        const authorBadge = r.is_course_trainer
            ? '<span class="badge bg-warning text-dark ms-1">Trainer</span>'
            : '';

        const endorseBtn = thread.can_endorse
            ? `<button class="btn btn-sm ${r.is_instructor_endorsed ? 'btn-outline-secondary' : 'btn-outline-success'} py-0 px-2 me-1" onclick="DiscussionsController.toggleEndorse(${r.id})">
                 <i class="bi bi-check-lg me-1"></i>${r.is_instructor_endorsed ? 'Remove Endorsement' : 'Endorse Answer'}
               </button>`
            : '';

        const deleteBtn = r.can_delete
            ? `<button class="btn btn-sm btn-outline-danger py-0 px-2" onclick="DiscussionsController.deleteReply(${r.id})">
                 <i class="bi bi-trash"></i>
               </button>`
            : '';

        return `
            <div class="card ${endorsedClass} mb-2 shadow-none rounded-3">
                <div class="card-body p-3">
                    ${endorsedBadge}
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div class="small">
                            <strong>${this.escapeHtml(r.author_username)}</strong>${authorBadge}
                            <span class="text-muted ms-2" style="font-size: 0.75rem;">${new Date(r.created_at).toLocaleString()}</span>
                        </div>
                        <div>
                            ${endorseBtn}
                            ${deleteBtn}
                        </div>
                    </div>
                    <div class="text-secondary small" style="white-space: pre-line; line-height: 1.5;">
                        ${this.escapeHtml(r.content)}
                    </div>
                </div>
            </div>
        `;
    },

    async submitReply(threadId) {
        const textarea = document.getElementById('newReplyContent');
        const content = textarea?.value?.trim();
        if (!content) {
            alert('Please enter a response.');
            return;
        }

        try {
            await apiRequest(`/discussions/${threadId}/replies/`, {
                method: 'POST',
                body: JSON.stringify({ content }),
            });
            this.openThreadDetailModal(threadId);
            this.loadThreads();
        } catch (err) {
            alert(`Failed to post reply: ${err.message}`);
        }
    },

    async toggleEndorse(replyId) {
        try {
            await apiRequest(`/discussions/replies/${replyId}/endorse/`, { method: 'POST' });
            if (this.activeThreadId) this.openThreadDetailModal(this.activeThreadId);
        } catch (err) {
            alert(`Failed to toggle endorsement: ${err.message}`);
        }
    },

    async deleteReply(replyId) {
        if (!confirm('Are you sure you want to delete this reply?')) return;
        try {
            await apiRequest(`/discussions/replies/${replyId}/`, { method: 'DELETE' });
            if (this.activeThreadId) this.openThreadDetailModal(this.activeThreadId);
            this.loadThreads();
        } catch (err) {
            alert(`Failed to delete reply: ${err.message}`);
        }
    },

    async toggleResolve(threadId) {
        try {
            await apiRequest(`/discussions/${threadId}/resolve/`, { method: 'POST' });
            this.openThreadDetailModal(threadId);
            this.loadThreads();
        } catch (err) {
            alert(`Failed to toggle resolution: ${err.message}`);
        }
    },

    async togglePin(threadId) {
        try {
            await apiRequest(`/discussions/${threadId}/pin/`, { method: 'POST' });
            this.openThreadDetailModal(threadId);
            this.loadThreads();
        } catch (err) {
            alert(`Failed to toggle pin: ${err.message}`);
        }
    },

    async deleteThread(threadId) {
        if (!confirm('Are you sure you want to delete this thread?')) return;
        try {
            await apiRequest(`/discussions/${threadId}/`, { method: 'DELETE' });
            const modalEl = document.getElementById('threadDetailModal');
            if (modalEl) {
                const modal = bootstrap.Modal.getInstance(modalEl);
                if (modal) modal.hide();
            }
            this.loadThreads();
        } catch (err) {
            alert(`Failed to delete thread: ${err.message}`);
        }
    },

    // =========================================================================
    // CREATE NEW THREAD MODAL
    // =========================================================================

    openCreateThreadModal() {
        const modalEl = document.getElementById('createThreadModal');
        if (!modalEl) return;

        // Pre-select current subject if available
        const subjectSelect = document.getElementById('threadSubjectSelect');
        if (subjectSelect && this.activeSubjectId) {
            subjectSelect.value = this.activeSubjectId;
        }

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
    },

    async submitNewThread() {
        const title = document.getElementById('threadTitleInput')?.value?.trim();
        const content = document.getElementById('threadContentInput')?.value?.trim();
        const threadType = document.getElementById('threadTypeSelect')?.value || 'QUESTION';
        const subjectId = document.getElementById('threadSubjectSelect')?.value || null;

        if (!title || title.length < 5) {
            alert('Please enter a title (at least 5 characters).');
            return;
        }
        if (!content || content.length < 10) {
            alert('Please enter your question details (at least 10 characters).');
            return;
        }

        const payload = {
            title,
            content,
            thread_type: threadType,
            subject_id: subjectId ? parseInt(subjectId, 10) : null,
        };

        try {
            const res = await apiRequest(`/discussions/courses/${this.activeCourseId}/`, {
                method: 'POST',
                body: JSON.stringify(payload),
            });

            // Close modal
            const modalEl = document.getElementById('createThreadModal');
            if (modalEl) {
                const modal = bootstrap.Modal.getInstance(modalEl);
                if (modal) modal.hide();
            }

            // Reset form
            document.getElementById('threadTitleInput').value = '';
            document.getElementById('threadContentInput').value = '';

            this.loadThreads();
            this.openThreadDetailModal(res.id);
        } catch (err) {
            alert(`Failed to create thread: ${err.message}`);
        }
    },

    // =========================================================================
    // TRAINER INBOX CONTROLLER
    // =========================================================================

    async loadTrainerInbox(resolvedFilter = 'false') {
        const container = document.getElementById('trainerInquiriesContainer');
        if (!container) return;

        container.innerHTML = `
            <div class="text-center py-4">
                <div class="spinner-border spinner-border-sm text-primary"></div>
                <p class="text-muted small mt-2 mb-0">Loading student inquiries...</p>
            </div>
        `;

        try {
            let url = '/discussions/trainer/inbox/';
            if (resolvedFilter !== 'all') {
                url += `?resolved=${resolvedFilter}`;
            }

            const inquiries = await apiRequest(url);
            if (!Array.isArray(inquiries) || inquiries.length === 0) {
                container.innerHTML = `
                    <div class="p-4 text-center bg-light rounded-3">
                        <i class="bi bi-inbox-fill fs-2 text-muted mb-2 d-block"></i>
                        <h6 class="fw-bold text-dark">No Inquiries Found</h6>
                        <p class="text-muted small mb-0">All student questions have been addressed!</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = `
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0 small">
                        <thead class="table-light text-secondary text-uppercase" style="font-size:0.75rem;">
                            <tr>
                                <th class="ps-3">Question</th>
                                <th>Course / Module</th>
                                <th>Student</th>
                                <th>Status</th>
                                <th>Date</th>
                                <th class="text-end pe-3">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${inquiries.map(item => `
                                <tr>
                                    <td class="ps-3">
                                        <div class="fw-bold text-dark">${this.escapeHtml(item.title)}</div>
                                        <div class="text-muted text-truncate" style="max-width:280px; font-size:0.75rem;">${this.escapeHtml(item.content)}</div>
                                    </td>
                                    <td>
                                        <div class="fw-semibold text-secondary">${this.escapeHtml(item.course_title)}</div>
                                        <div class="text-muted" style="font-size:0.72rem;">${this.escapeHtml(item.subject_title || 'General Course')}</div>
                                    </td>
                                    <td>${this.escapeHtml(item.author_username)}</td>
                                    <td>
                                        ${item.is_resolved ? '<span class="badge bg-success-subtle text-success">Resolved</span>' : '<span class="badge bg-warning-subtle text-warning">Open</span>'}
                                        ${item.has_instructor_reply ? '<span class="badge bg-info-subtle text-info ms-1">Replied</span>' : ''}
                                    </td>
                                    <td>${new Date(item.created_at).toLocaleDateString()}</td>
                                    <td class="text-end pe-3">
                                        <button class="btn btn-outline-primary btn-sm py-0 px-2" onclick="DiscussionsController.openThreadDetailModal(${item.id})">
                                            <i class="bi bi-reply-fill me-1"></i>View &amp; Reply
                                        </button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        } catch (err) {
            console.error('[Discussions] Error loading trainer inbox:', err);
            container.innerHTML = `<div class="alert alert-danger small m-3">${this.escapeHtml(err.message)}</div>`;
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
