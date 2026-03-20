/**
 * MAARS Settings sync helpers.
 * Handles UI syncing and form-to-state reading for settings modal.
 */
(function () {
    'use strict';

    function syncThemeCardsActive() {
        const current = document.documentElement.getAttribute('data-theme') || 'light';
        document.querySelectorAll('.settings-theme-card').forEach((el) => {
            el.classList.toggle('active', el.dataset.pick === current);
        });
    }

    function syncMatrixActive(agentMode) {
        const am = agentMode || {};
        document.querySelectorAll('#settingsModeMatrix .settings-mode-cell').forEach((el) => {
            el.classList.toggle('active', am[el.dataset.row] === el.dataset.col);
        });
    }

    function syncLiteratureSourceUI(agentMode) {
        const select = document.getElementById('ideaLiteratureSource');
        if (!select) return;
        const value = String((agentMode || {}).literatureSource || 'openalex').trim().toLowerCase();
        select.value = value === 'arxiv' ? 'arxiv' : 'openalex';
    }

    function readLiteratureSourceFromUI(agentMode, defaults) {
        const select = document.getElementById('ideaLiteratureSource');
        const merged = { ...(defaults || {}), ...(agentMode || {}) };
        const value = String(select?.value || 'openalex').trim().toLowerCase();
        merged.literatureSource = (value === 'arxiv') ? 'arxiv' : 'openalex';
        return merged;
    }

    window.MAARS = window.MAARS || {};
    window.MAARS.settingsSyncHelpers = {
        syncThemeCardsActive,
        syncMatrixActive,
        syncLiteratureSourceUI,
        readLiteratureSourceFromUI,
    };
})();
