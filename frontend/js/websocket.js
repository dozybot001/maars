/**
 * MAARS WebSocket - Socket.io connection and event handlers.
 * Delegates rendering to planner-thinking, monitor, TaskTree.
 */
(function () {
    'use strict';
    const cfg = window.MAARS?.config;
    const planner = window.MAARS?.planner;
    const monitor = window.MAARS?.monitor;
    const plannerThinking = window.MAARS?.plannerThinking;
    if (!cfg || !planner || !monitor) return;

    const state = window.MAARS.state || {};
    state.socket = null;
    window.MAARS.state = state;

    const executionBtn = document.getElementById('executionBtn');
    const stopExecutionBtn = document.getElementById('stopExecutionBtn');

    function init() {
        if (state.socket && state.socket.connected) return;
        state.socket = io(cfg.WS_URL);

        state.socket.on('connect', () => console.log('WebSocket connected'));
        state.socket.on('disconnect', () => console.log('WebSocket disconnected'));

        state.socket.on('plan-start', () => {
            if (plannerThinking) plannerThinking.clear();
            TaskTree.clearPlannerTree();
        });

        state.socket.on('plan-thinking', (data) => {
            if (!data.chunk || !plannerThinking) return;
            plannerThinking.appendChunk(data.chunk, data.taskId, data.operation);
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
        });

        state.socket.on('plan-error', () => planner.resetPlanUI());

        state.socket.on('timetable-layout', (data) => {
            monitor.state.timetableLayout = data.layout;
            monitor.state.chainCache = monitor.buildChainCacheFromLayout(data.layout);
            monitor.renderNodeDiagramFromCache();
        });

        state.socket.on('task-states-update', (data) => {
            if (data.tasks && Array.isArray(data.tasks)) {
                data.tasks.forEach(taskState => {
                    const cacheNode = monitor.state.chainCache.find(node => node.task_id === taskState.task_id);
                    const previousStatus = monitor.state.previousTaskStates.get(taskState.task_id);
                    if (cacheNode) cacheNode.status = taskState.status;
                    if (previousStatus !== undefined && previousStatus !== taskState.status) {
                        if (taskState.status === 'doing' && (previousStatus === 'undone' || previousStatus === 'validating')) {
                            setTimeout(() => monitor.animateConnectionLines(taskState.task_id, 'yellow', 'upstream'), 50);
                        } else if (taskState.status === 'undone' && previousStatus === 'done') {
                            setTimeout(() => monitor.animateConnectionLines(taskState.task_id, 'red', 'downstream'), 50);
                        }
                    }
                    monitor.state.previousTaskStates.set(taskState.task_id, taskState.status);
                });
                data.tasks.forEach(taskState => {
                    const monitorSection = document.querySelector('.monitor-section');
                    if (monitorSection) {
                        const cells = monitorSection.querySelectorAll(`[data-task-id="${taskState.task_id}"]`);
                        cells.forEach(cell => {
                            cell.classList.remove('task-status-undone', 'task-status-doing', 'task-status-validating', 'task-status-done', 'task-status-validation-failed', 'task-status-execution-failed');
                            cell.classList.add(`task-status-${taskState.status}`);
                            const dataAttr = cell.getAttribute('data-task-data');
                            if (dataAttr) {
                                try {
                                    const d = JSON.parse(dataAttr);
                                    d.status = taskState.status;
                                    cell.setAttribute('data-task-data', JSON.stringify(d));
                                } catch (_) {}
                                }
                        });
                    }
                });
            }
        });

        state.socket.on('executor-states-update', (data) => {
            if (data.executors && data.stats) monitor.renderExecutors(data.executors, data.stats);
        });

        state.socket.on('validator-states-update', (data) => {
            if (data.validators && data.stats) monitor.renderValidators(data.validators, data.stats);
        });

        state.socket.on('execution-error', (data) => {
            const isStoppedByUser = (data.error || '').includes('stopped by user');
            if (!isStoppedByUser) {
                console.error('Execution error:', data.error);
                alert('Execution error: ' + data.error);
            }
            monitor.resetExecutionButtons();
        });

        state.socket.on('execution-complete', (data) => {
            console.log(`Execution complete: ${data.completed}/${data.total} tasks completed`);
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
