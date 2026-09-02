/**
 * Capacity Connect — Trainee Learning Service Module (trainee-learning.js)
 *
 * Provides reusable API service methods for Trainee operations:
 * - Fetching published courses
 * - Fetching course details
 * - Enrolling in courses
 * - Fetching trainee enrollments
 * - Fetching enrollment details
 * - Completing / toggling subjects
 * - Computing reliable dashboard KPIs
 *
 * Relies on apiRequest() from app.js and Auth from auth.js.
 */

'use strict';

const TraineeLearning = {
    /**
     * Fetch all published courses available for enrollment.
     * Endpoint: GET /api/courses/
     * @returns {Promise<Array>} List of Course objects
     */
    async fetchPublishedCourses() {
        return await apiRequest('/courses/');
    },

    /**
     * Fetch details of a single published course including subjects.
     * Endpoint: GET /api/courses/<courseId>/
     * @param {number|string} courseId
     * @returns {Promise<object>} CourseDetail object
     */
    async fetchCourseDetails(courseId) {
        return await apiRequest(`/courses/${courseId}/`);
    },

    /**
     * Fetch all enrollments for the currently authenticated trainee.
     * Endpoint: GET /api/enrollments/
     * @returns {Promise<Array>} List of Enrollment objects
     */
    async fetchMyEnrollments() {
        return await apiRequest('/enrollments/');
    },

    /**
     * Fetch detailed enrollment record including subject_progresses.
     * Endpoint: GET /api/enrollments/<enrollmentId>/
     * @param {number|string} enrollmentId
     * @returns {Promise<object>} EnrollmentDetail object
     */
    async fetchEnrollmentDetails(enrollmentId) {
        return await apiRequest(`/enrollments/${enrollmentId}/`);
    },

    /**
     * Enroll current trainee in a published course.
     * Endpoint: POST /api/enrollments/
     * @param {number|string} courseId
     * @returns {Promise<object>} Created EnrollmentDetail object
     */
    async enrollInCourse(courseId) {
        return await apiRequest('/enrollments/', {
            method: 'POST',
            body: JSON.stringify({ course_id: parseInt(courseId, 10) }),
        });
    },

    /**
     * Mark a subject complete or incomplete within an enrollment.
     * Endpoint: POST /api/enrollments/<enrollmentId>/subjects/<subjectId>/complete/
     * @param {number|string} enrollmentId
     * @param {number|string} subjectId
     * @param {boolean} [completed] - Optional explicit boolean state
     * @returns {Promise<object>} Updated EnrollmentDetail object
     */
    async toggleSubjectComplete(enrollmentId, subjectId, completed) {
        const options = {
            method: 'POST',
        };
        if (typeof completed === 'boolean') {
            options.body = JSON.stringify({ completed });
        }
        return await apiRequest(
            `/enrollments/${enrollmentId}/subjects/${subjectId}/complete/`,
            options
        );
    },

    /**
     * Compute authoritative dashboard statistics from active trainee enrollments.
     * @param {Array} enrollments - List of EnrollmentList objects from GET /api/enrollments/
     * @returns {object} { totalEnrolled, completedCount, inProgressCount, averageProgress }
     */
    computeDashboardStats(enrollments) {
        if (!Array.isArray(enrollments) || enrollments.length === 0) {
            return {
                totalEnrolled: 0,
                completedCount: 0,
                inProgressCount: 0,
                averageProgress: 0,
            };
        }

        const validEnrollments = enrollments.filter(e => e.status !== 'DROPPED');
        const totalEnrolled = validEnrollments.length;
        const completedCount = validEnrollments.filter(e => e.status === 'COMPLETED').length;
        const inProgressCount = validEnrollments.filter(e => e.status === 'ENROLLED').length;

        const totalProgressSum = validEnrollments.reduce((sum, e) => {
            const val = parseFloat(e.progress_percentage) || 0;
            return sum + val;
        }, 0);

        const averageProgress = totalEnrolled > 0
            ? Math.round((totalProgressSum / totalEnrolled) * 10) / 10
            : 0;

        return {
            totalEnrolled,
            completedCount,
            inProgressCount,
            averageProgress,
        };
    },

    /**
     * Identifies the primary active course for the "Continue Learning" section.
     * Prioritizes in-progress enrollments (status == 'ENROLLED') with recent activity.
     * @param {Array} enrollments
     * @returns {object|null} The most relevant Enrollment object or null
     */
    getContinueLearningCourse(enrollments) {
        if (!Array.isArray(enrollments) || enrollments.length === 0) {
            return null;
        }

        // Find active in-progress courses first
        const inProgress = enrollments.filter(e => e.status === 'ENROLLED');
        if (inProgress.length > 0) {
            return inProgress[0]; // Most recent enrollment based on default backend ordering
        }

        return null;
    },

    /**
     * Helper to safely escape HTML strings for DOM rendering.
     * @param {string} str
     * @returns {string}
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

window.TraineeLearning = TraineeLearning;
