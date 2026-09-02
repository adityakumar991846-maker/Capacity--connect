/**
 * Capacity Connect — Main Application JavaScript & API Client
 *
 * Provides a unified API client that automatically includes Supabase Auth
 * access tokens in the `Authorization: Bearer <token>` header.
 */

'use strict';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const APP_CONFIG = {
    API_BASE_URL: window.__API_BASE_URL__ || 'http://127.0.0.1:8000/api',
    APP_NAME: 'Capacity Connect',
};

// ---------------------------------------------------------------------------
// Utility: API Helper
// ---------------------------------------------------------------------------

/**
 * Make an authenticated fetch request to the Django REST API.
 * Automatically attaches Supabase Bearer token if session is active.
 *
 * @param {string} endpoint - API endpoint path (e.g. '/auth/me/', '/courses/')
 * @param {object} options  - Fetch options (method, headers, body, etc.)
 * @returns {Promise<object>} Parsed JSON response
 */
async function apiRequest(endpoint, options = {}) {
    const url = `${APP_CONFIG.API_BASE_URL}${endpoint}`;

    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };

    // Retrieve active Supabase session token if available
    try {
        if (window.SupabaseAuth && window.SupabaseAuth.getSession) {
            const session = await window.SupabaseAuth.getSession();
            if (session && session.access_token) {
                headers['Authorization'] = `Bearer ${session.access_token}`;
            }
        }
    } catch (err) {
        console.warn('[API] Could not retrieve Supabase session token:', err);
    }

    const config = {
        ...options,
        headers,
    };

    try {
        const response = await fetch(url, config);

        if (!response.ok) {
            let errorMessage = `HTTP ${response.status}`;
            try {
                const errorData = await response.json();
                if (typeof errorData === 'object') {
                    if (errorData.detail) {
                        errorMessage = errorData.detail;
                    } else if (errorData.error) {
                        errorMessage = errorData.error;
                    } else {
                        // Aggregate DRF field errors e.g. { "title": ["This field is required."] }
                        const messages = Object.entries(errorData)
                            .map(([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(', ') : msgs}`)
                            .join(' | ');
                        errorMessage = messages || errorMessage;
                    }
                }
            } catch (jsonErr) {
                // Response body is not JSON
            }
            const error = new Error(errorMessage);
            error.status = response.status;
            throw error;
        }

        // Handle 204 No Content
        if (response.status === 204) {
            return null;
        }

        return await response.json();
    } catch (error) {
        console.error(`[API] ${options.method || 'GET'} ${endpoint} failed:`, error.message);
        throw error;
    }
}

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    console.log(`${APP_CONFIG.APP_NAME} initialized.`);
});
