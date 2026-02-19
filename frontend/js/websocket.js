/**
 * MAARS WebSocket - Socket.io connection and event handlers.
 */
(function () {
    'use strict';
    const cfg = window.MAARS?.config;
    const planner = window.MAARS?.planner;
    const monitor = window.MAARS?.monitor;
    if (!cfg || !planner || !monitor) return;

    const state = window.MAARS.state || {};
    state.socket = null;
    state.plannerThinkingBlocks = [];
    window.MAARS.state = state;

    const generatePlanBtn = document.getElementById('generatePlanBtn');
    const decomposeBtn = document.getElementById('decomposeBtn');
    const stopPlanBtn = document.getElementById('stopPlanBtn');
    const executionBtn = document.getElementById('executionBtn');

    function init() {
        if (state.socket && state.socket.connected) return;
        state.socket = io(cfg.WS_URL);

        state.socket.on('connect', () => console.log('WebSocket connected'));
        state.socket.on('disconnect', () => console.log('WebSocket disconnected'));

        state.socket.on('plan-start', () => {
            state.plannerThinkingBlocks.forEach(b => { if (b._typeTimer) clearTimeout(b._typeTimer); });
            state.plannerThinkingBlocks = [];
            const el = document.getElementById('plannerThinkingContent');
            const area = document.getElementById('plannerThinkingArea');
            if (el) el.innerHTML = '';
            if (area) area.classList.remove('has-content');
            TaskTree.clearPlannerTree();
        });

        function renderPlannerThinking() {
            const el = document.getElementById('plannerThinkingContent');
            const area = document.getElementById('plannerThinkingArea');
            if (!el) return;
            const OP_ORDER = { Atomicity: 1, Decompose: 2, Format: 3 };
            const treeData = (typeof TaskTree !== 'undefined' && TaskTree.plannerTreeData) ? TaskTree.plannerTreeData : [];
            const sorted = [...state.plannerThinkingBlocks].sort((a, b) => {
                const stageA = treeData.find(t => t.task_id === a.taskId)?.stage ?? 999;
                const stageB = treeData.find(t => t.task_id === b.taskId)?.stage ?? 999;
                if (stageA !== stageB) return stageA - stageB;
                const opA = OP_ORDER[a.operation] ?? 99;
                const opB = OP_ORDER[b.operation] ?? 99;
                if (opA !== opB) return opA - opB;
                return String(a.taskId || '').localeCompare(String(b.taskId || ''));
            });
            let html = '';
            for (const block of sorted) {
                const header = block.taskId != null ? `---\n\n**Task ${block.taskId}** | ${block.operation || ''}\n\n` : '';
                const raw = header + (block.displayContent != null ? block.displayContent : block.content);
                let blockHtml = raw ? (typeof marked !== 'undefined' ? marked.parse(raw) : raw) : '';
                if (blockHtml && typeof DOMPurify !== 'undefined') blockHtml = DOMPurify.sanitize(blockHtml);
                html += blockHtml + '\n\n';
            }
            try {
                el.innerHTML = html || '';
                if (typeof hljs !== 'undefined') el.querySelectorAll('pre code').forEach((block) => hljs.highlightElement(block));
            } catch (_) {
                el.textContent = sorted.map(b => (b.displayContent != null ? b.displayContent : b.content)).join('\n\n');
            }
            el.scrollTop = el.scrollHeight;
            if (area && state.plannerThinkingBlocks.length) area.classList.add('has-content');
        }

        function typeOutBlock(block, fullContent, speedMs = 12) {
            if (block.displayContent === fullContent) return;
            block.displayContent = block.displayContent != null ? block.displayContent : '';
            let i = block.displayContent.length;
            const step = () => {
                if (i < fullContent.length) {
                    const chunk = fullContent.slice(i, Math.min(i + 2, fullContent.length));
                    block.displayContent += chunk;
                    i += chunk.length;
                    renderPlannerThinking();
                    block._typeTimer = setTimeout(step, speedMs);
                }
            };
            if (block._typeTimer) clearTimeout(block._typeTimer);
            step();
        }

        state.socket.on('plan-thinking', (data) => {
            const el = document.getElementById('plannerThinkingContent');
            if (!el || !data.chunk) return;
            const { chunk, taskId, operation } = data;
            const key = (taskId != null && operation != null) ? `${String(taskId)}::${String(operation)}` : '_default';
            let block = state.plannerThinkingBlocks.find(b => b.key === key);
            if (!block) {
                block = { key, taskId, operation, content: '', displayContent: '' };
                state.plannerThinkingBlocks.push(block);
            }
            block.content += chunk;
            typeOutBlock(block, block.content);
        });

        state.socket.on('plan-tree-update', (data) => {
            if (data.treeData) TaskTree.renderPlannerTree(data.treeData);
        });

        state.socket.on('plan-complete', (data) => {
            if (data.treeData) TaskTree.renderPlannerTree(data.treeData);
            if (data.planId) cfg.setCurrentPlanId(data.planId);
            TaskTree.updatePlannerQualityBadge(data.qualityScore, data.qualityComment);
            planner.resetPlanButtons();
        });

        state.socket.on('plan-error', () => planner.resetPlanButtons());

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
            console.error('Execution error:', data.error);
            alert('Execution error: ' + data.error);
            if (executionBtn) { executionBtn.disabled = false; executionBtn.textContent = 'Execution'; }
        });

        state.socket.on('execution-complete', (data) => {
            console.log(`Execution complete: ${data.completed}/${data.total} tasks completed`);
            if (executionBtn) {
                executionBtn.disabled = false;
                executionBtn.textContent = 'Execution Complete!';
                setTimeout(() => { executionBtn.textContent = 'Execution'; }, 2000);
            }
        });
    }

    window.MAARS.ws = { init };
})();
