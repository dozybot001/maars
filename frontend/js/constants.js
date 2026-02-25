/**
 * MAARS constants - centralized magic numbers for tuning.
 * Load after config.js; used by thinking-area and other modules.
 */
(function () {
    'use strict';
    window.MAARS = window.MAARS || {};

    window.MAARS.constants = {
        /** Throttle (ms) for thinking area render when content is small */
        RENDER_THROTTLE_MS: 120,
        /** Throttle (ms) for thinking area render when content is large */
        RENDER_THROTTLE_LARGE_MS: 250,
        /** Char count above which RENDER_THROTTLE_LARGE_MS is used */
        LARGE_CONTENT_CHARS: 6000,
        /** Debounce (ms) for timetable resize handler */
        RESIZE_DEBOUNCE_MS: 150,
    };
})();
