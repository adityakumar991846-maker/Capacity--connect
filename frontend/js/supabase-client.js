/**
 * Capacity Connect — Supabase Auth Client
 *
 * Uses the official @supabase/supabase-js library loaded via CDN.
 * Manages user authentication, token refresh, and session persistence securely.
 *
 * NOTE: The SUPABASE_ANON_KEY is designed to be public.
 * Never place the SUPABASE_SERVICE_ROLE_KEY in frontend code.
 */

'use strict';

const SUPABASE_CONFIG = {
    // Replace with your real Supabase Project URL and Public Anon Key in production / deployment
    URL: window.__SUPABASE_URL__ || 'https://placeholder-project.supabase.co',
    ANON_KEY: window.__SUPABASE_ANON_KEY__ || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.placeholder-anon-key',
};

let supabaseClient = null;

/**
 * Get or initialize the Supabase client.
 */
function getSupabase() {
    if (!supabaseClient) {
        if (typeof window.supabase === 'undefined' || !window.supabase.createClient) {
            console.error('[Supabase] Supabase JS library is not loaded. Ensure CDN script tag is included.');
            return null;
        }
        supabaseClient = window.supabase.createClient(SUPABASE_CONFIG.URL, SUPABASE_CONFIG.ANON_KEY, {
            auth: {
                autoRefreshToken: true,
                persistSession: true,
                detectSessionInUrl: true,
            },
        });
    }
    return supabaseClient;
}

/**
 * Sign up a new user with Supabase Auth.
 * Role is stored in user_metadata (strictly TRAINEE or TRAINER).
 *
 * @param {string} email
 * @param {string} password
 * @param {string} username
 * @param {string} role - 'TRAINEE' or 'TRAINER'
 */
async function supabaseSignUp(email, password, username, role) {
    const sb = getSupabase();
    if (!sb) throw new Error('Supabase client unavailable.');

    const cleanRole = (role === 'TRAINER') ? 'TRAINER' : 'TRAINEE';

    const { data, error } = await sb.auth.signUp({
        email,
        password,
        options: {
            data: {
                username: username.trim(),
                role: cleanRole,
            },
        },
    });

    if (error) throw error;
    return data;
}

/**
 * Sign in existing user with email and password.
 *
 * @param {string} email
 * @param {string} password
 */
async function supabaseSignIn(email, password) {
    const sb = getSupabase();
    if (!sb) throw new Error('Supabase client unavailable.');

    const { data, error } = await sb.auth.signInWithPassword({
        email,
        password,
    });

    if (error) throw error;
    return data;
}

/**
 * Sign out current user.
 */
async function supabaseSignOut() {
    const sb = getSupabase();
    if (!sb) return;
    const { error } = await sb.auth.signOut();
    if (error) throw error;
}

/**
 * Get current active session.
 */
async function supabaseGetSession() {
    const sb = getSupabase();
    if (!sb) return null;
    const { data: { session }, error } = await sb.auth.getSession();
    if (error) {
        console.warn('[Supabase] Error getting session:', error);
        return null;
    }
    return session;
}

/**
 * Get current authenticated user from session.
 */
async function supabaseGetUser() {
    const sb = getSupabase();
    if (!sb) return null;
    const { data: { user }, error } = await sb.auth.getUser();
    if (error) return null;
    return user;
}

/**
 * Listen to auth state changes (SIGNED_IN, SIGNED_OUT, TOKEN_REFRESHED).
 *
 * @param {function} callback - (event, session) => void
 */
function supabaseOnAuthStateChange(callback) {
    const sb = getSupabase();
    if (!sb) return { data: { subscription: { unsubscribe: () => {} } } };
    return sb.auth.onAuthStateChange(callback);
}

// Attach to window object for global availability
window.SupabaseAuth = {
    getSupabase,
    signUp: supabaseSignUp,
    signIn: supabaseSignIn,
    signOut: supabaseSignOut,
    getSession: supabaseGetSession,
    getUser: supabaseGetUser,
    onAuthStateChange: supabaseOnAuthStateChange,
};
