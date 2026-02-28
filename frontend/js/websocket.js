/**
 * MAARS WebSocket - Socket.io connection and event handlers.
 * Delegates rendering to planner-thinking, plannerViews, TaskTree.
 */
(function () {
    'use strict';
    const cfg = window.MAARS?.config;
    const planner = window.MAARS?.planner;
    const plannerViews = window.MAARS?.plannerViews;
    const plannerThinking = window.MAARS?.plannerThinking;
    const executorThinking = window.MAARS?.executorThinking;
    if (!cfg || !planner || !plannerViews) return;

    const state = window.MAARS.state || {};
    state.socket = null;
    window.MAARS.state = state;

    const executionBtn = document.getElementById('executionBtn');
    const stopExecutionBtn = document.getElementById('stopExecutionBtn');

    function init() {
        if (state.socket && state.socket.connected) return;
        state.socket = io(cfg.WS_URL, { reconnection: true, reconnectionAttempts: 10, reconnectionDelay: 1000 });

        state.socket.on('connect', () => console.log('WebSocket connected'));
        state.socket.on('disconnect', () => console.log('WebSocket disconnected'));

        state.socket.on('plan-start', () => {
            if (plannerThinking) plannerThinking.clear();
            TaskTree.clearPlannerTree();
        });

        state.socket.on('plan-thinking', (data) => {
            if (!plannerThinking) return;
            plannerThinking.appendChunk(data.chunk || '', data.taskId, data.operation, data.scheduleInfo);
        });

        state.socket.on('plan-tree-update', (data) => {
            if (data.treeData) TaskTree.renderPlannerTree(data.treeData, data.layout);
        });

        state.socket.on('plan-complete', (data) => {
            if (data.treeData) TaskTree.renderPlannerTree(data.treeData, data.layout);
            if (data.planId) cfg.setCurrentPlanId(data.planId);
            TaskTree.updatePlannerQualityBadge(data.qualityScore, data.qualityComment);
            planner.resetPlanUI();
            if (plannerThinking) plannerThinking.applyHighlight();
            if (plannerViews?.generateExecutionLayout) plannerViews.generateExecutionLayout();
        });

        state.socket.on('plan-error', () => planner.resetPlanUI());

        state.socket.on('execution-layout', (data) => { plannerViews.setExecutionLayout(data); });

        state.socket.on('task-states-update', (data) => {
            if (data.tasks && Array.isArray(data.tasks)) {
                data.tasks.forEach(taskState => {
                    const cacheNode = plannerViews.state.chainCache.find(node => node.task_id === taskState.task_id);
                    const previousStatus = plannerViews.state.previousTaskStates.get(taskState.task_id);
                    if (cacheNode) cacheNode.status = taskState.status;
                    if (previousStatus !== undefined && previousStatus !== taskState.status) {
                        if (taskState.status === 'doing' && (previousStatus === 'undone' || previousStatus === 'validating')) {
                            setTimeout(() => plannerViews.animateConnectionLines(taskState.task_id, 'yellow', 'upstream'), 50);
                        } else if (taskState.status === 'undone' && previousStatus === 'done') {
                            setTimeout(() => plannerViews.animateConnectionLines(taskState.task_id, 'red', 'downstream'), 50);
                        }
                    }
                    plannerViews.state.previousTaskStates.set(taskState.task_id, taskState.status);
                });
                data.tasks.forEach(taskState => {
                    const areas = document.querySelectorAll('.planner-tree-area, .planner-execution-tree-area');
                    areas.forEach((treeArea) => {
                    if (treeArea) {
                        const byId = treeArea.querySelectorAll(`[data-task-id="${taskState.task_id}"]`);
                        const byIds = treeArea.querySelectorAll('[data-task-ids]');
                        const cells = Array.from(byId);
                        byIds.forEach(cell => {
                            const ids = (cell.getAttribute('data-task-ids') || '').split(',').map(s => s.trim());
                            if (ids.includes(taskState.task_id)) cells.push(cell);
                        });
                        cells.forEach(cell => {
                            cell.classList.remove('task-status-undone', 'task-status-doing', 'task-status-validating', 'task-status-done', 'task-status-validation-failed', 'task-status-execution-failed');
                            const dataAttr = cell.getAttribute('data-task-data');
                            if (dataAttr) {
                                try {
                                    const d = JSON.parse(dataAttr);
                                    const arr = Array.isArray(d) ? d : [d];
                                    const updated = arr.map(t => t.task_id === taskState.task_id ? { ...t, status: taskState.status } : t);
                                    cell.setAttribute('data-task-data', JSON.stringify(Array.isArray(d) ? updated : updated[0]));
                                    const status = arr.length === 1 ? taskState.status : (typeof TaskTree !== 'undefined' && TaskTree.aggregateStatus ? TaskTree.aggregateStatus(updated) : taskState.status);
                                    if (status && status !== 'undone') cell.classList.add(`task-status-${status}`);
                                } catch (_) {
                                    if (taskState.status && taskState.status !== 'undone') cell.classList.add(`task-status-${taskState.status}`);
                                }
                            } else {
                                if (taskState.status && taskState.status !== 'undone') cell.classList.add(`task-status-${taskState.status}`);
                            }
                            document.querySelectorAll(`.task-detail-tab[data-tab-task-id="${taskState.task_id}"]`).forEach(tab => {
                                tab.classList.remove('task-status-undone', 'task-status-doing', 'task-status-validating', 'task-status-done', 'task-status-validation-failed', 'task-status-execution-failed');
                                if (taskState.status && taskState.status !== 'undone') tab.classList.add(`task-status-${taskState.status}`);
                            });
                        });
                    }
                    });
                });
            }
        });

        state.socket.on('task-thinking', (data) => {
            if (!executorThinking) return;
            executorThinking.appendChunk(data.chunk || '', data.taskId, data.operation, data.scheduleInfo);
        });

        state.socket.on('task-output', (data) => {
            if (!executorThinking || !data.taskId) return;
            executorThinking.setTaskOutput(data.taskId, data.output);
        });

        state.socket.on('worker-states-update', (data) => {
            plannerViews.renderWorkerStates(data);
        });

        state.socket.on('execution-error', (data) => {
            const isStoppedByUser = (data.error || '').includes('stopped by user');
            if (!isStoppedByUser) {
                console.error('Execution error:', data.error);
                alert('Execution error: ' + data.error);
            }
            plannerViews.resetExecutionButtons();
        });

        state.socket.on('execution-complete', (data) => {
            console.log(`Execution complete: ${data.completed}/${data.total} tasks completed`);
            if (plannerThinking) plannerThinking.applyHighlight();
            if (executorThinking) executorThinking.applyOutputHighlight();
            if (stopExecutionBtn) stopExecutionBtn.style.display = 'none';
            if (executionBtn) {
                executionBtn.disabled = false;
                executionBtn.textContent = 'Execution Complete!';
                setTimeout(() => { executionBtn.textContent = 'Execution'; }, 2000);
            }
        });
    }

    window.MAARS.ws = { init };
})();
