/**
 * Capacity Connect — Main Application JavaScript
 *
 * This file provides the foundation for client-side functionality.
 * Feature-specific scripts will be added in separate files as modules are built.
 */

'use strict';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const APP_CONFIG = {
    API_BASE_URL: 'http://127.0.0.1:8000/api',
    APP_NAME: 'Capacity Connect',
};

// ---------------------------------------------------------------------------
// Utility: API Helper
// ---------------------------------------------------------------------------

/**
 * Make a fetch request to the backend API.
 *
 * @param {string} endpoint - API endpoint path (e.g. '/courses/')
 * @param {object} options  - Fetch options (method, headers, body, etc.)
 * @returns {Promise<object>} Parsed JSON response
 */
async function apiRequest(endpoint, options = {}) {
    const url = `${APP_CONFIG.API_BASE_URL}${endpoint}`;

    const defaultHeaders = {
        'Content-Type': 'application/json',
    };

    const config = {
        ...options,
        headers: {
            ...defaultHeaders,
            ...options.headers,
        },
    };

    try {
        const response = await fetch(url, config);

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        // Handle 204 No Content
        if (response.status === 204) {
            return null;
        }

        return await response.json();
    } catch (error) {
        console.error(`[API] ${options.method || 'GET'} ${endpoint} failed:`, error);
        throw error;
    }
}

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    console.log(`${APP_CONFIG.APP_NAME} frontend loaded.`);
});
