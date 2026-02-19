/**
 * MAARS API - backend API calls.
 */
(function () {
    'use strict';
    const cfg = window.MAARS?.config;
    if (!cfg) return;

    async function loadExampleIdea() {
        const ideaInput = document.getElementById('ideaInput');
        try {
            const planId = await cfg.resolvePlanId();
            const response = await fetch(`${cfg.API_BASE_URL}/idea?planId=${encodeURIComponent(planId)}`);
            const data = await response.json();
            if (data.idea) {
                ideaInput.value = typeof data.idea === 'string' ? data.idea : JSON.stringify(data.idea);
            } else {
                ideaInput.value = 'Research and analyze the latest trends in AI technology';
            }
        } catch (error) {
            console.error('Error loading example idea:', error);
            ideaInput.value = 'Research and analyze the latest trends in AI technology';
        }
    }

    async function loadExecution() {
        try {
            const planId = await cfg.resolvePlanId();
            const response = await fetch(`${cfg.API_BASE_URL}/execution?planId=${encodeURIComponent(planId)}`);
            const data = await response.json();
            return data.execution || null;
        } catch (error) {
            console.error('Error loading execution:', error);
            return null;
        }
    }

    window.MAARS.api = { loadExampleIdea, loadExecution };
})();
