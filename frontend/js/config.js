/**
 * MAARS config - API URLs, storage keys, and config helpers.
 */
(function () {
    'use strict';
    window.MAARS = window.MAARS || {};

    const _base = (typeof window !== 'undefined' && window.location && /^https?:/.test(window.location.origin))
        ? '' : 'http://localhost:3001';
    const API_BASE_URL = _base + '/api';
    const WS_URL = (typeof window !== 'undefined' && window.location) ? window.location.origin : 'http://localhost:3001';
    const PLAN_ID_KEY = 'maars-plan-id';
    const THEME_STORAGE_KEY = 'maars-theme';
    const THEMES = ['light', 'dark', 'black'];

    function getCurrentPlanId() {
        try {
            return localStorage.getItem(PLAN_ID_KEY) || 'test';
        } catch (_) { return 'test'; }
    }

    async function resolvePlanId() {
        const stored = getCurrentPlanId();
        if (stored && stored.startsWith('plan_')) return stored;
        try {
            const res = await fetch(`${API_BASE_URL}/plans`);
            const data = await res.json();
            const ids = data.planIds || [];
            if (ids.length > 0) {
                setCurrentPlanId(ids[0]);
                return ids[0];
            }
        } catch (_) {}
        return stored || 'test';
    }

    function setCurrentPlanId(id) {
        try { localStorage.setItem(PLAN_ID_KEY, id); } catch (_) {}
    }

    async function fetchApiConfig() {
        const res = await fetch(`${API_BASE_URL}/config`, { cache: 'no-store' });
        if (!res.ok) throw new Error(`Config ${res.status}`);
        const data = await res.json();
        return data.config != null ? data.config : {};
    }

    async function saveApiConfig(cfg) {
        const res = await fetch(`${API_BASE_URL}/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cfg || {})
        });
        if (!res.ok) throw new Error('Save failed');
        return await res.json();
    }

    window.MAARS.config = {
        API_BASE_URL,
        WS_URL,
        PLAN_ID_KEY,
        THEME_STORAGE_KEY,
        THEMES,
        getCurrentPlanId,
        setCurrentPlanId,
        resolvePlanId,
        fetchApiConfig,
        saveApiConfig,
    };
})();
