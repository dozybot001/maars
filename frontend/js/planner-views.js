/**
 * MAARS planner views - execution tree (执行图), executor chips.
 * Planner has 2 sub-views: decomposition, execution.
 */
(function () {
    'use strict';
    const cfg = window.MAARS?.config;
    const api = window.MAARS?.api;
    if (!cfg || !api) return;

    const executionBtn = document.getElementById('executionBtn');
    const stopExecutionBtn = document.getElementById('stopExecutionBtn');

    window.MAARS.state = window.MAARS.state || {};
    const state = window.MAARS.state;
    state.executionLayout = state.executionLayout ?? null;
    state.chainCache = state.chainCache ?? [];
    state.previousTaskStates = state.previousTaskStates ?? new Map();

    function buildChainCacheFromLayout(layout) {
        const cache = [];
        if (!layout) return cache;
        const treeData = layout.treeData || [];
        treeData.forEach(task => {
            if (task && task.task_id) {
                cache.push({ task_id: task.task_id, dependencies: task.dependencies || [], status: task.status || 'undone' });
            }
        });
        return cache;
    }

    function renderExecutionDiagram() {
        const layout = state.executionLayout;
        const treeData = layout?.treeData || [];
        TaskTree.renderExecutionTree(treeData, layout?.layout);
    }

    function animateConnectionLines(taskId, color, direction) {
        const area = document.querySelector('.planner-execution-tree-area');
        const svg = area?.querySelector('.tree-connection-lines');
        if (!svg) return;
        const paths = Array.from(svg.querySelectorAll('path.connection-line'));
        const lines = direction === 'upstream'
            ? paths.filter(p => {
                const to = p.getAttribute('data-to-task');
                const toTasks = p.getAttribute('data-to-tasks');
                if (to === taskId) return true;
                if (toTasks) return toTasks.split(',').map(s => s.trim()).includes(taskId);
                return false;
            })
            : paths.filter(p => {
                const from = p.getAttribute('data-from-task');
                const fromTasks = p.getAttribute('data-from-tasks');
                if (from === taskId) return true;
                if (fromTasks) return fromTasks.split(',').map(s => s.trim()).includes(taskId);
                return false;
            });
        if (lines.length === 0) return;
        const animClass = color === 'yellow' ? 'animate-yellow-glow' : 'animate-red-glow';
        lines.forEach(line => line.classList.remove('animate-yellow-glow', 'animate-red-glow'));
        void svg.offsetHeight;
        const order = color === 'yellow' ? lines : [...lines].reverse();
        order.forEach((line, i) => {
            setTimeout(() => {
                line.classList.add(animClass);
                setTimeout(() => line.classList.remove(animClass), 1000);
            }, i * 50);
        });
    }

    function renderChips(containerId, items, stats, opts) {
        const { chipClass, chipIdAttr, getStatusClass, getTitle } = opts;
        const chipsEl = document.getElementById(containerId);
        const baseId = containerId.replace('Chips', '');
        const totalEl = document.getElementById(baseId + 'Total');
        const busyEl = document.getElementById(baseId + 'Busy');
        const validatingEl = document.getElementById(baseId + 'Validating');
        const idleEl = document.getElementById(baseId + 'Idle');
        if (!chipsEl || !totalEl || !busyEl || !idleEl) return;
        if (!items || items.length === 0) {
            chipsEl.innerHTML = '';
            totalEl.textContent = busyEl.textContent = idleEl.textContent = '0';
            if (validatingEl) validatingEl.textContent = '0';
            return;
        }
        totalEl.textContent = stats.total ?? items.length;
        busyEl.textContent = stats.busy ?? 0;
        if (validatingEl) validatingEl.textContent = stats.validating ?? 0;
        idleEl.textContent = stats.idle ?? 0;
        const existing = new Map();
        chipsEl.querySelectorAll(`.${chipClass}`).forEach((el) => {
            const id = el.getAttribute(chipIdAttr);
            if (id) existing.set(id, el);
        });
        items.forEach((item) => {
            const id = String(item.id);
            const statusClass = getStatusClass(item);
            const title = getTitle(item);
            let chip = existing.get(id);
            if (chip) {
                chip.className = `${chipClass} ${statusClass}`;
                chip.title = title;
                existing.delete(id);
            } else {
                chip = document.createElement('div');
                chip.className = `${chipClass} ${statusClass}`;
                chip.setAttribute(chipIdAttr, item.id);
                chip.title = title;
                chip.textContent = item.id;
                chipsEl.appendChild(chip);
            }
        });
        existing.forEach((el) => el.remove());
    }

    function renderExecutorStates(data) {
        if (!data) return;
        if (data.executors && data.stats) {
            renderChips('executorChips', data.executors, data.stats, {
                chipClass: 'executor-chip',
                chipIdAttr: 'data-executor-id',
                getStatusClass: (e) => {
                    if (e.status === 'busy') return 'executor-busy';
                    if (e.status === 'validating') return 'executor-validating';
                    if (e.status === 'failed') return 'executor-failed';
                    return 'executor-idle';
                },
                getTitle: (e) => {
                    if (e.status === 'validating') return `Executor ${e.id} validating output${e.taskId ? ': ' + e.taskId : ''}`;
                    if (e.status === 'busy') return `Executor ${e.id} executing${e.taskId ? ': ' + e.taskId : ''}`;
                    return `Executor ${e.id}${e.taskId ? ': ' + e.taskId : ''}`;
                },
            });
        }
    }

    async function runExecution() {
        const execution = await api.loadExecution();
        if (!execution) {
            alert('Please generate plan first.');
            return;
        }
        const btn = executionBtn;
        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Executing...';
        try {
            const socket = window.MAARS?.state?.socket;
            if (!socket || !socket.connected) {
                window.MAARS.ws?.init();
                await new Promise(resolve => setTimeout(resolve, 500));
            }
            const response = await fetch(`${cfg.API_BASE_URL}/execution/run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to start execution');
            }
            if (stopExecutionBtn) stopExecutionBtn.style.display = '';
        } catch (error) {
            console.error('Error in execution:', error);
            alert('Error: ' + error.message);
            btn.textContent = originalText;
            btn.disabled = false;
            if (stopExecutionBtn) stopExecutionBtn.style.display = 'none';
        }
    }

    function stopExecution() {
        fetch(`${cfg.API_BASE_URL}/execution/stop`, { method: 'POST' }).catch(() => {});
    }

    function resetExecutionButtons() {
        if (executionBtn) { executionBtn.disabled = false; executionBtn.textContent = 'Execution'; }
        if (stopExecutionBtn) stopExecutionBtn.style.display = 'none';
    }

    async function generateExecutionLayout() {
        try {
            const planId = await cfg.resolvePlanId();
            const genRes = await fetch(`${cfg.API_BASE_URL}/execution/generate-from-plan`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ planId })
            });
            const genData = await genRes.json();
            if (!genRes.ok) throw new Error(genData.error || 'Failed to generate execution from plan');
            const execution = genData.execution;
            if (!execution || !execution.tasks?.length) {
                alert('No atomic tasks in plan. Generate plan first.');
                return;
            }
            const response = await fetch(`${cfg.API_BASE_URL}/plan/layout`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ execution, planId })
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to generate layout');
            }
            const data = await response.json();
            state.executionLayout = data.layout;
            state.previousTaskStates.clear();
            state.chainCache = buildChainCacheFromLayout(state.executionLayout);
            renderExecutionDiagram();
            const socket = window.MAARS?.state?.socket;
            if (socket && socket.connected) socket.emit('execution-layout', { layout: state.executionLayout });
        } catch (error) {
            console.error('Error generating layout:', error);
            alert('Error: ' + error.message);
        }
    }

    function setExecutionLayout(data) {
        if (!data?.layout) return;
        state.executionLayout = data.layout;
        state.chainCache = buildChainCacheFromLayout(data.layout);
        renderExecutionDiagram();
    }

    function init() {
        if (executionBtn) executionBtn.addEventListener('click', runExecution);
        if (stopExecutionBtn) stopExecutionBtn.addEventListener('click', stopExecution);
    }

    window.MAARS.plannerViews = {
        init,
        state,
        setExecutionLayout,
        buildChainCacheFromLayout,
        renderExecutionDiagram,
        animateConnectionLines,
        renderExecutorStates,
        resetExecutionButtons,
        generateExecutionLayout,
    };
})();
