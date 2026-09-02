/**
 * Capacity Connect — Dashboard Layout Controller (dashboard.js)
 *
 * Provides shared client-side functionality for role dashboards:
 * - Session verification & authoritative Django /api/auth/me/ sync
 * - Role-based route guard enforcement
 * - Mobile sidebar drawer toggle & backdrop behavior
 * - User profile info population across sidebar and topbar
 * - Search shortcuts and global sign-out
 *
 * NOTE: Frontend role controls UI rendering only. Backend Django UserProfile.role
 * remains the authoritative security enforcement for all protected operations.
 */

'use strict';

const Dashboard = {
    _currentUser: null,

    /**
     * Initializes the dashboard for a specific required role.
     * Enforces authentication and server-side role validation.
     *
     * @param {string} requiredRole - Expected role ('TRAINEE', 'TRAINER', 'ADMIN')
     */
    async init(requiredRole) {
        try {
            // Fetch authoritative profile from Django MySQL via Supabase token
            const profile = await Auth.fetchDjangoProfile();

            if (!profile) {
                console.warn('[Dashboard] Unauthenticated access attempt. Redirecting to login.');
                window.location.href = `/pages/login.html?redirect=${encodeURIComponent(window.location.pathname)}`;
                return;
            }

            this._currentUser = profile;

            // Enforce role consistency: if user role doesn't match requiredRole, route to user's dashboard
            if (requiredRole && profile.role !== requiredRole) {
                console.warn(`[Dashboard] Role mismatch: user is ${profile.role}, page requires ${requiredRole}. Redirecting.`);
                this.redirectToRoleDashboard(profile.role);
                return;
            }

            // Populate user information in the DOM
            this.renderUserProfile(profile);

            // Setup mobile sidebar drawer and interactive controls
            this.setupSidebarDrawer();
            this.setupKeyboardShortcuts();

        } catch (err) {
            console.error('[Dashboard] Initialization error:', err);
            window.location.href = '/pages/login.html';
        }
    },

    /**
     * Redirects the user to their designated role dashboard.
     * @param {string} role - 'TRAINEE' | 'TRAINER' | 'ADMIN'
     */
    redirectToRoleDashboard(role) {
        switch (role) {
            case 'ADMIN':
                window.location.href = '/pages/admin-dashboard.html';
                break;
            case 'TRAINER':
                window.location.href = '/pages/trainer-dashboard.html';
                break;
            case 'TRAINEE':
            default:
                window.location.href = '/pages/trainee-dashboard.html';
                break;
        }
    },

    /**
     * Populates all user profile placeholder elements in the layout.
     * @param {object} profile - { id, username, email, role, supabase_uid }
     */
    renderUserProfile(profile) {
        const username = profile.username || 'User';
        const email = profile.email || '';
        const role = profile.role || 'TRAINEE';
        const initial = username.charAt(0).toUpperCase();

        // Populate text content safely (XSS prevention)
        document.querySelectorAll('.cc-username-display').forEach(el => {
            el.textContent = username;
        });

        document.querySelectorAll('.cc-email-display').forEach(el => {
            el.textContent = email;
        });

        document.querySelectorAll('.cc-role-badge').forEach(el => {
            el.textContent = role;
            el.className = 'badge cc-role-badge ' + this.getRoleBadgeClass(role);
        });

        document.querySelectorAll('.cc-avatar-initial').forEach(el => {
            el.textContent = initial;
        });
    },

    /**
     * Returns appropriate Bootstrap badge class for each role.
     */
    getRoleBadgeClass(role) {
        switch (role) {
            case 'ADMIN':
                return 'bg-danger text-white';
            case 'TRAINER':
                return 'bg-warning text-dark';
            case 'TRAINEE':
            default:
                return 'bg-info text-dark';
        }
    },

    /**
     * Sets up the mobile sidebar toggle button, drawer transition, and backdrop.
     */
    setupSidebarDrawer() {
        const toggleBtn = document.getElementById('sidebarToggleBtn');
        const sidebar = document.getElementById('cc-sidebar');
        const backdrop = document.getElementById('cc-sidebar-backdrop');

        if (!toggleBtn || !sidebar) return;

        const toggleSidebar = () => {
            sidebar.classList.toggle('show');
            if (backdrop) {
                backdrop.classList.toggle('show');
            }
        };

        const closeSidebar = () => {
            sidebar.classList.remove('show');
            if (backdrop) {
                backdrop.classList.remove('show');
            }
        };

        toggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            toggleSidebar();
        });

        if (backdrop) {
            backdrop.addEventListener('click', closeSidebar);
        }

        // Close drawer when pressing Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && sidebar.classList.contains('show')) {
                closeSidebar();
            }
        });
    },

    /**
     * Binds keyboard shortcut (Ctrl+K / Cmd+K) to focus search bar.
     */
    setupKeyboardShortcuts() {
        const searchInput = document.getElementById('topbarSearchInput');
        if (!searchInput) return;

        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                searchInput.focus();
            }
        });
    }
};

// Global export
window.Dashboard = Dashboard;
