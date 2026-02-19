/**
 * MAARS planner - generate plan, decompose, stop.
 */
(function () {
    'use strict';
    const cfg = window.MAARS?.config;
    const api = window.MAARS?.api;
    if (!cfg || !api) return;

    const ideaInput = document.getElementById('ideaInput');
    const generatePlanBtn = document.getElementById('generatePlanBtn');
    const decomposeBtn = document.getElementById('decomposeBtn');
    const stopPlanBtn = document.getElementById('stopPlanBtn');
    const loadExampleIdeaBtn = document.getElementById('loadExampleIdeaBtn');

    let planRunAbortController = null;

    async function buildPlanRunBody(extra = {}) {
        const planId = await cfg.resolvePlanId();
        return { planId, ...extra };
    }

    async function generatePlan() {
        const idea = (ideaInput?.value || '').trim();
        if (!idea) {
            alert('Please enter an idea first.');
            return;
        }
        const socket = window.MAARS?.state?.socket;
        if (!socket || !socket.connected) {
            alert('WebSocket not connected. Please wait and try again.');
            return;
        }

        try {
            generatePlanBtn.disabled = true;
            decomposeBtn.disabled = true;
            if (stopPlanBtn) stopPlanBtn.style.display = '';
            planRunAbortController = new AbortController();

            TaskTree.clearPlannerTree();
            const response = await fetch(`${cfg.API_BASE_URL}/plan/run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(await buildPlanRunBody({ idea })),
                signal: planRunAbortController.signal
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to generate plan');
            if (data.planId) cfg.setCurrentPlanId(data.planId);
        } catch (error) {
            if (error.name === 'AbortError') return;
            console.error('Error generating plan:', error);
            alert('Error: ' + (error.message || 'Failed to generate plan'));
        } finally {
            generatePlanBtn.disabled = false;
            generatePlanBtn.textContent = 'Generate Plan';
            decomposeBtn.disabled = false;
            if (stopPlanBtn) stopPlanBtn.style.display = 'none';
            planRunAbortController = null;
        }
    }

    async function decomposeTask() {
        if (!decomposeBtn || decomposeBtn.disabled) return;
        try {
            decomposeBtn.disabled = true;
            decomposeBtn.textContent = 'Decomposing...';
            if (stopPlanBtn) stopPlanBtn.style.display = '';
            planRunAbortController = new AbortController();

            const response = await fetch(`${cfg.API_BASE_URL}/plan/run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(await buildPlanRunBody()),
                signal: planRunAbortController.signal
            });
            const res = await response.json();
            if (!response.ok) throw new Error(res.error || 'Failed to decompose');
        } catch (error) {
            if (error.name === 'AbortError') return;
            console.error('Error decomposing:', error);
            alert('Error: ' + (error.message || 'Failed to decompose'));
        } finally {
            decomposeBtn.disabled = false;
            decomposeBtn.textContent = 'Decompose';
            if (stopPlanBtn) stopPlanBtn.style.display = 'none';
            planRunAbortController = null;
        }
    }

    function stopPlanRun() {
        if (planRunAbortController) planRunAbortController.abort();
        fetch(`${cfg.API_BASE_URL}/plan/stop`, { method: 'POST' }).catch(() => {});
    }

    function resetPlanButtons() {
        if (generatePlanBtn) { generatePlanBtn.disabled = false; generatePlanBtn.textContent = 'Generate Plan'; }
        if (decomposeBtn) { decomposeBtn.disabled = false; decomposeBtn.textContent = 'Decompose'; }
        if (stopPlanBtn) stopPlanBtn.style.display = 'none';
    }

    function init() {
        if (generatePlanBtn) generatePlanBtn.addEventListener('click', generatePlan);
        if (decomposeBtn) decomposeBtn.addEventListener('click', decomposeTask);
        if (stopPlanBtn) stopPlanBtn.addEventListener('click', stopPlanRun);
        if (loadExampleIdeaBtn) loadExampleIdeaBtn.addEventListener('click', api.loadExampleIdea);
    }

    window.MAARS.planner = { init, generatePlan, decomposeTask, stopPlanRun, resetPlanButtons };
})();
