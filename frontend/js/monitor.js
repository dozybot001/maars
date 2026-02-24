/**
 * MAARS monitor - timetable diagram, execution map, executors/validators.
 */
(function () {
    'use strict';
    const cfg = window.MAARS?.config;
    const api = window.MAARS?.api;
    if (!cfg || !api) return;

    const diagramArea = document.getElementById('diagramArea');
    const generateTimetableBtn = document.getElementById('generateTimetableBtn');
    const executionBtn = document.getElementById('executionBtn');
    const stopExecutionBtn = document.getElementById('stopExecutionBtn');

    window.MAARS.state = window.MAARS.state || {};
    const state = window.MAARS.state;
    state.timetableLayout = state.timetableLayout ?? null;
    state.chainCache = state.chainCache ?? [];
    state.previousTaskStates = state.previousTaskStates ?? new Map();

    function escapeHtmlAttr(str) {
        if (str == null) return '';
        return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
    function escapeHtml(str) {
        if (str == null) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function buildChainCacheFromLayout(layout) {
        const cache = [];
        if (!layout) return cache;
        const { grid, isolatedTasks } = layout;
        if (grid) {
            grid.forEach(row => {
                row.forEach(cell => {
                    if (cell && cell.task_id) {
                        cache.push({ task_id: cell.task_id, dependencies: cell.dependencies || [], status: cell.status || 'undone' });
                    }
                });
            });
        }
        if (isolatedTasks) {
            isolatedTasks.forEach(task => {
                if (task && task.task_id) {
                    cache.push({ task_id: task.task_id, dependencies: task.dependencies || [], status: task.status || 'undone' });
                }
            });
        }
        return cache;
    }

    function buildTimetableCellHtml(task) {
        if (!task || !task.task_id) {
            return '<div class="timetable-cell timetable-cell-empty"></div>';
        }
        const status = task.status || 'undone';
        const statusClass = (status && status !== 'undone') ? ` task-status-${status}` : '';
        const desc = task.description || task.objective || task.task_id;
        const safeTooltip = (desc || '').replace(/"/g, '&quot;');
        const popoverData = typeof TaskTree !== 'undefined' && TaskTree.buildTaskDataForPopover
            ? TaskTree.buildTaskDataForPopover(task) : { task_id: task.task_id, description: task.description, dependencies: task.dependencies, status: task.status, input: task.input, output: task.output, validation: task.validation };
        return `<div class="timetable-cell${statusClass}" data-task-id="${task.task_id}" data-task-data="${escapeHtmlAttr(JSON.stringify(popoverData))}" title="${safeTooltip}"><span class="timetable-cell-id">${escapeHtml(task.task_id)}</span></div>`;
    }

    function buildTimetableGridHtml(leftCols, leftRows, rightCols, rightRows, getLeftTask, getRightTask) {
        let html = '<div class="timetable-container"><div class="timetable-wrapper">';
        html += '<div class="timetable-left"><div class="timetable-left-scroll">';
        html += '<div class="timetable-left-header timetable-header-row">';
        for (let col = 0; col < leftCols; col++) html += `<div class="timetable-header-cell">Stage ${col + 1}</div>`;
        html += '</div><div class="timetable-left-grid timetable-grid">';
        for (let row = 0; row < leftRows; row++) {
            for (let col = 0; col < leftCols; col++) html += buildTimetableCellHtml(getLeftTask(row, col));
        }
        html += '</div></div></div>';
        html += '<div class="timetable-right"><div class="timetable-right-scroll">';
        html += '<div class="timetable-right-header timetable-header-row">';
        html += '<div class="timetable-header-cell" style="grid-column: 1 / -1;">Isolated Tasks</div>';
        html += '</div><div class="timetable-right-grid timetable-grid">';
        for (let row = 0; row < rightRows; row++) {
            for (let col = 0; col < rightCols; col++) html += buildTimetableCellHtml(getRightTask(row, col));
        }
        html += '</div></div></div></div></div>';
        return html;
    }

    function applyTimetableGridStyles(diagramContent, leftCols, leftRows, rightCols, rightRows, fixedCellSize, rightAreaWidth) {
        const gap = 1;
        const rightArea = diagramContent.querySelector('.timetable-right');
        if (rightArea) rightArea.style.width = rightArea.style.minWidth = rightArea.style.maxWidth = `${rightAreaWidth}px`;
        const leftHeader = diagramContent.querySelector('.timetable-left-header');
        const leftGrid = diagramContent.querySelector('.timetable-left-grid');
        const rightHeader = diagramContent.querySelector('.timetable-right-header');
        const rightGrid = diagramContent.querySelector('.timetable-right-grid');
        if (leftHeader && leftGrid) {
            const w = leftCols * fixedCellSize + gap * (leftCols - 1);
            const h = leftRows * fixedCellSize + gap * (leftRows - 1);
            leftHeader.setAttribute('data-cols', leftCols);
            leftGrid.setAttribute('data-cols', leftCols);
            leftGrid.setAttribute('data-rows', leftRows);
            leftHeader.style.gridTemplateColumns = leftGrid.style.gridTemplateColumns = `repeat(${leftCols}, ${fixedCellSize}px)`;
            leftGrid.style.gridTemplateRows = `repeat(${leftRows}, ${fixedCellSize}px)`;
            leftGrid.style.width = leftGrid.style.minWidth = leftHeader.style.width = leftHeader.style.minWidth = `${w}px`;
            leftGrid.style.height = leftGrid.style.minHeight = `${h}px`;
        }
        if (rightHeader && rightGrid) {
            const w = rightCols * fixedCellSize + gap * (rightCols - 1);
            const h = rightRows * fixedCellSize + gap * (rightRows - 1);
            rightHeader.setAttribute('data-cols', rightCols);
            rightGrid.setAttribute('data-cols', rightCols);
            rightGrid.setAttribute('data-rows', rightRows);
            rightHeader.style.gridTemplateColumns = rightGrid.style.gridTemplateColumns = `repeat(${rightCols}, ${fixedCellSize}px)`;
            rightGrid.style.gridTemplateRows = `repeat(${rightRows}, ${fixedCellSize}px)`;
            rightGrid.style.width = rightGrid.style.minWidth = rightHeader.style.width = rightHeader.style.minWidth = `${w}px`;
            rightGrid.style.height = rightGrid.style.minHeight = `${h}px`;
        }
    }

    function calculateFixedCellSize(container) {
        if (!container) return { cellSize: 48, rightAreaWidth: 160 };
        const containerWidth = container.clientWidth || container.offsetWidth || container.getBoundingClientRect().width;
        const computedStyle = window.getComputedStyle(container);
        const paddingLeft = parseFloat(computedStyle.paddingLeft) || 0;
        const paddingRight = parseFloat(computedStyle.paddingRight) || 0;
        const borderLeft = parseFloat(computedStyle.borderLeftWidth) || 0;
        const borderRight = parseFloat(computedStyle.borderRightWidth) || 0;
        const availableWidth = containerWidth - (paddingLeft + paddingRight + borderLeft + borderRight);
        const gap = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--gap')) || 20;
        const cellSize = Math.floor((availableWidth - gap) / 13);
        const rightAreaWidth = 3 * cellSize + gap;
        return { cellSize, rightAreaWidth };
    }

    function renderTimetableDiagram() {
        const layout = state.timetableLayout;
        const displayCols = 10;
        const displayRows = 4;
        const rightCols = 3;
        const rightRows = 4;
        const hasLayout = layout && layout.grid;
        const grid = hasLayout ? layout.grid : [];
        const isolatedTasks = (hasLayout && layout.isolatedTasks) ? layout.isolatedTasks : [];

        const actualCols = hasLayout ? Math.max(layout.maxCols || displayCols, displayCols) : displayCols;
        const actualRows = hasLayout ? Math.max(layout.maxRows || 0, displayRows) : displayRows;
        const isolatedTaskCount = isolatedTasks.length;
        const actualRightRows = Math.max(Math.ceil(isolatedTaskCount / rightCols), rightRows);

        const taskPositionMap = new Map();
        if (isolatedTaskCount > 0) {
            const totalCells = actualRightRows * rightCols;
            isolatedTasks.forEach((task, i) => {
                if (task && task.task_id) {
                    const pos = totalCells - 1 - i;
                    taskPositionMap.set(`${Math.floor(pos / rightCols)}-${pos % rightCols}`, task);
                }
            });
        }

        const getLeftTask = (row, col) => (grid && row < grid.length && col < (grid[row]?.length || 0)) ? grid[row][col] : null;
        const getRightTask = (row, col) => taskPositionMap.get(`${row}-${col}`) || null;

        const html = '<div class="execution-map">' + buildTimetableGridHtml(actualCols, actualRows, rightCols, actualRightRows, getLeftTask, getRightTask) + '</div>';
        diagramArea.innerHTML = html;

        const treeData = layout?.treeData || [];
        TaskTree.renderMonitorTasksTree(treeData, layout?.layout);

        setTimeout(() => {
            const timetableWrapper = diagramArea.querySelector('.timetable-wrapper');
            if (!timetableWrapper) return;
            const { cellSize: fixedCellSize, rightAreaWidth } = calculateFixedCellSize(timetableWrapper);
            applyTimetableGridStyles(diagramArea, actualCols, actualRows, rightCols, actualRightRows, fixedCellSize, rightAreaWidth);
        }, 0);
    }

    function renderNodeDiagramFromCache() {
        renderTimetableDiagram();
    }

    function animateConnectionLines(taskId, color, direction) {
        const area = document.querySelector('.monitor-tasks-tree-area') || document.querySelector('.tasks-tree-section');
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

    function renderExecutors(executors, stats) {
        const executorChips = document.getElementById('executorChips');
        const executorTotal = document.getElementById('executorTotal');
        const executorBusy = document.getElementById('executorBusy');
        const executorIdle = document.getElementById('executorIdle');
        if (!executorChips || !executorTotal || !executorBusy || !executorIdle) return;
        if (!executors || executors.length === 0) {
            executorChips.innerHTML = '';
            executorTotal.textContent = executorBusy.textContent = executorIdle.textContent = '0';
            return;
        }
        executorTotal.textContent = stats.total || executors.length;
        executorBusy.textContent = stats.busy || 0;
        executorIdle.textContent = stats.idle || 0;
        let html = '';
        executors.forEach(executor => {
            const statusClass = executor.status === 'busy' ? 'executor-busy' : executor.status === 'failed' ? 'executor-failed' : 'executor-idle';
            html += `<div class="executor-chip ${statusClass}" data-executor-id="${executor.id}" title="Executor ${executor.id}${executor.taskId ? ': ' + executor.taskId : ''}">${executor.id}</div>`;
        });
        executorChips.innerHTML = html;
    }

    function renderValidators(validators, stats) {
        const validatorGrid = document.getElementById('validatorGrid');
        const validatorTotal = document.getElementById('validatorTotal');
        const validatorBusy = document.getElementById('validatorBusy');
        const validatorIdle = document.getElementById('validatorIdle');
        if (!validatorGrid || !validatorTotal || !validatorBusy || !validatorIdle) return;
        if (!validators || validators.length === 0) {
            validatorGrid.innerHTML = '';
            validatorTotal.textContent = validatorBusy.textContent = validatorIdle.textContent = '0';
            return;
        }
        validatorTotal.textContent = stats.total || validators.length;
        validatorBusy.textContent = stats.busy || 0;
        validatorIdle.textContent = stats.idle || 0;
        let html = '';
        validators.forEach(v => {
            const statusClass = v.status === 'busy' ? 'validator-busy' : v.status === 'failed' ? 'validator-failed' : 'validator-idle';
            const taskText = v.taskId ? `Task: ${v.taskId}` : '';
            html += `<div class="validator-item ${statusClass}"><div class="validator-id">Validator ${v.id}</div><div class="validator-status status-${v.status}">${v.status.toUpperCase()}</div><div class="validator-task">${taskText}</div></div>`;
        });
        validatorGrid.innerHTML = html;
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

    async function generateTimetable() {
        const btn = generateTimetableBtn;
        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Generating...';
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
                btn.textContent = originalText;
                btn.disabled = false;
                return;
            }
            const response = await fetch(`${cfg.API_BASE_URL}/monitor/timetable`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ execution, planId })
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to generate timetable');
            }
            const data = await response.json();
            state.timetableLayout = data.layout;
            state.previousTaskStates.clear();
            state.chainCache = buildChainCacheFromLayout(state.timetableLayout);
            renderTimetableDiagram();
            if (state.timetableLayout?.treeData?.length) TaskTree.renderMonitorTasksTree(state.timetableLayout.treeData, state.timetableLayout?.layout);
            const socket = window.MAARS?.state?.socket;
            if (socket && socket.connected) socket.emit('timetable-layout', { layout: state.timetableLayout });
            btn.textContent = 'Loaded!';
            setTimeout(() => { btn.textContent = 'Generate Map'; }, 2000);
        } catch (error) {
            console.error('Error generating timetable:', error);
            alert('Error: ' + error.message);
            btn.textContent = originalText;
        } finally {
            btn.disabled = false;
        }
    }

    function init() {
        if (generateTimetableBtn) generateTimetableBtn.addEventListener('click', generateTimetable);
        if (executionBtn) executionBtn.addEventListener('click', runExecution);
        if (stopExecutionBtn) stopExecutionBtn.addEventListener('click', stopExecution);
    }

    window.MAARS.monitor = {
        init,
        state,
        buildChainCacheFromLayout,
        renderTimetableDiagram,
        renderNodeDiagramFromCache,
        animateConnectionLines,
        renderExecutors,
        renderValidators,
        calculateFixedCellSize,
        resetExecutionButtons,
    };
})();
