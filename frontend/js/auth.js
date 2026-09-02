/**
 * Capacity Connect — Authentication UI & State Controller
 *
 * Orchestrates Supabase Auth client operations with Django application identity.
 * Authoritative user roles are always fetched from Django (/api/auth/me/).
 */

'use strict';

const Auth = {
    _currentUser: null,

    /**
     * Fetch authoritative user profile from Django MySQL backend.
     * @returns {Promise<object|null>} Django user object { id, username, email, role, supabase_uid }
     */
    async fetchDjangoProfile() {
        try {
            const user = await apiRequest('/auth/me/');
            this._currentUser = user;
            return user;
        } catch (err) {
            this._currentUser = null;
            return null;
        }
    },

    /**
     * Get cached current user object (or null if unauthenticated).
     */
    getUser() {
        return this._currentUser;
    },

    /**
     * Check if user is currently authenticated with active Supabase session.
     */
    async isAuthenticated() {
        if (!window.SupabaseAuth) return false;
        const session = await window.SupabaseAuth.getSession();
        return !!(session && session.access_token);
    },

    /**
     * Sign in with Supabase Auth and fetch authoritative Django profile.
     */
    async login(email, password) {
        if (!window.SupabaseAuth) throw new Error('Supabase Auth client not initialized.');
        const result = await window.SupabaseAuth.signIn(email, password);
        const profile = await this.fetchDjangoProfile();
        return { session: result.session, profile };
    },

    /**
     * Register new Trainee or Trainer with Supabase Auth.
     */
    async register(email, password, username, role) {
        if (!window.SupabaseAuth) throw new Error('Supabase Auth client not initialized.');
        const cleanRole = (role === 'TRAINER') ? 'TRAINER' : 'TRAINEE';
        return await window.SupabaseAuth.signUp(email, password, username, cleanRole);
    },

    /**
     * Sign out and refresh UI state.
     */
    async logout() {
        if (window.SupabaseAuth) {
            await window.SupabaseAuth.signOut();
        }
        this._currentUser = null;
        this.updateNavbar(null);
        window.location.href = '/index.html';
    },

    /**
     * Initialize navbar and dynamic elements across any page.
     */
    async initNavbar() {
        const navContainer = document.getElementById('navbarNav') || document.querySelector('.navbar-nav');
        if (!navContainer) return;

        const isAuth = await this.isAuthenticated();
        if (isAuth) {
            const profile = await this.fetchDjangoProfile();
            this.updateNavbar(profile);
        } else {
            this.updateNavbar(null);
        }

        // Listen to Supabase auth state changes
        if (window.SupabaseAuth) {
            window.SupabaseAuth.onAuthStateChange(async (event, session) => {
                if (event === 'SIGNED_IN' || event === 'TOKEN_REFRESHED') {
                    const profile = await this.fetchDjangoProfile();
                    this.updateNavbar(profile);
                } else if (event === 'SIGNED_OUT') {
                    this._currentUser = null;
                    this.updateNavbar(null);
                }
            });
        }
    },

    /**
     * Dynamically render navigation items based on authentication state and role.
     */
    updateNavbar(user) {
        const navList = document.getElementById('navbarLinks');
        if (!navList) return;

        if (user) {
            const roleBadgeClass = user.role === 'ADMIN' ? 'bg-danger text-white' : (user.role === 'TRAINER' ? 'bg-warning text-dark' : 'bg-info text-dark');
            navList.innerHTML = `
                <li class="nav-item">
                    <a class="nav-link" href="/index.html"><i class="bi bi-house-door me-1"></i>Home</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link fw-semibold" href="/pages/dashboard.html"><i class="bi bi-speedometer2 me-1"></i>Dashboard</a>
                </li>
                <li class="nav-item dropdown ms-lg-3">
                    <a class="nav-link dropdown-toggle d-flex align-items-center" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                        <i class="bi bi-person-circle fs-5 me-2"></i>
                        <span>${user.username}</span>
                        <span class="badge ${roleBadgeClass} ms-2">${user.role}</span>
                    </a>
                    <ul class="dropdown-menu dropdown-menu-end shadow-sm">
                        <li><h6 class="dropdown-header">${user.email}</h6></li>
                        <li>
                            <a class="dropdown-item" href="/pages/dashboard.html">
                                <i class="bi bi-speedometer2 me-2"></i>My Dashboard
                            </a>
                        </li>
                        <li><hr class="dropdown-divider"></li>
                        <li>
                            <a class="dropdown-item text-danger" href="#" id="logoutBtn" onclick="Auth.logout(); return false;">
                                <i class="bi bi-box-arrow-right me-2"></i>Sign Out
                            </a>
                        </li>
                    </ul>
                </li>
            `;
        } else {
            navList.innerHTML = `
                <li class="nav-item">
                    <a class="nav-link" href="/index.html"><i class="bi bi-house-door me-1"></i>Home</a>
                </li>
                <li class="nav-item ms-lg-2">
                    <a class="nav-link btn btn-outline-light px-3 py-1 me-2" href="/pages/login.html">
                        <i class="bi bi-box-arrow-in-right me-1"></i>Log In
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link btn btn-light text-primary px-3 py-1 fw-semibold" href="/pages/register.html">
                        <i class="bi bi-person-plus me-1"></i>Register
                    </a>
                </li>
            `;
        }
    },

    /**
     * Route guard: redirect to login if not authenticated.
     */
    async requireAuth(allowedRoles = []) {
        const isAuth = await this.isAuthenticated();
        if (!isAuth) {
            window.location.href = `/pages/login.html?redirect=${encodeURIComponent(window.location.pathname)}`;
            return false;
        }

        const profile = await this.fetchDjangoProfile();
        if (!profile) {
            window.location.href = '/pages/login.html';
            return false;
        }

        if (allowedRoles.length > 0 && !allowedRoles.includes(profile.role)) {
            alert(`Access denied. This page requires one of the following roles: ${allowedRoles.join(', ')}`);
            window.location.href = '/pages/dashboard.html';
            return false;
        }

        return true;
    },

    /**
     * Redirect authenticated users away from Login and Register pages.
     */
    async redirectIfAuthenticated() {
        const isAuth = await this.isAuthenticated();
        if (isAuth) {
            const profile = await this.fetchDjangoProfile();
            if (profile) {
                window.location.href = '/pages/dashboard.html';
            }
        }
    }
};

// Global export
window.Auth = Auth;

// Auto-initialize navbar on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    Auth.initNavbar();
});
