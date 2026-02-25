/**
 * MAARS API - backend API calls.
 */
(function () {
    'use strict';
    const cfg = window.MAARS?.config;
    if (!cfg) return;

    function loadExampleIdea() {
        const ideaInput = document.getElementById('ideaInput');
        if (ideaInput) ideaInput.value = 'Compare Python vs JavaScript for backend development and summarize pros/cons.';
    }

    async function loadExecution() {
        try {
            const planId = await cfg.resolvePlanId();
            const response = await fetch(`${cfg.API_BASE_URL}/execution?planId=${encodeURIComponent(planId)}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to load execution');
            return data.execution || null;
        } catch (error) {
            console.error('Error loading execution:', error);
            return null;
        }
    }

    async function clearDb() {
        const res = await fetch(`${cfg.API_BASE_URL}/db/clear`, { method: 'POST' });
        if (!res.ok) throw new Error('Failed to clear DB');
        return await res.json();
    }

    window.MAARS.api = { loadExampleIdea, loadExecution, clearDb };
})();
