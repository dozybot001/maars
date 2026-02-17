/**
 * Task tree rendering module.
 * Renders tasks by stage; backend provides treeData (tasks with stage).
 */
(function () {
    'use strict';

    const TRUNCATE_LEN = 60;
    const TASK_NODE_SELECTOR = '.tree-task, [data-task-id]';

    // Area selectors
    const AREA = {
        planner: '.planner-tree-area',
        monitor: '.monitor-tasks-tree-area',
    };

    let plannerTreeData = [];

    function getTreeContainer(areaSelector) {
        const area = document.querySelector(areaSelector);
        const tree = area?.querySelector('.tasks-tree');
        return area && tree ? { area, tree } : null;
    }

    function buildConnectionLines(tasks) {
        const ids = new Set((tasks || []).map(t => t.task_id).filter(Boolean));
        const lines = [];
        (tasks || []).forEach(task => {
            const tid = task.task_id;
            if (!tid) return;
            (task.dependencies || []).forEach(depId => {
                if (ids.has(depId)) lines.push({ fromTaskId: depId, toTaskId: tid });
            });
        });
        return lines;
    }

    function formatTaskDisplay(task) {
        const tid = task.task_id;
        const text = (task.description || task.objective || '').trim() || tid || 'Task';
        const truncated = text.length > TRUNCATE_LEN ? text.slice(0, TRUNCATE_LEN - 3) + '...' : text;
        return { displayText: text, truncated, label: tid };
    }

    function getTaskDataForPopover(task) {
        return {
            task_id: task.task_id,
            description: task.description,
            objective: task.objective,
            dependencies: task.dependencies,
            status: task.status,
            input: task.input,
            output: task.output,
            task_type: task.task_type,
            inputs: task.inputs,
            outputs: task.outputs,
            target: task.target,
            timeout_seconds: task.timeout_seconds,
        };
    }

    function createTaskNodeEl(task, options = {}) {
        const { withStatus = false, isIdea = false } = options;
        const tid = task.task_id;
        const { displayText, truncated, label } = formatTaskDisplay(task);
        const deps = (task.dependencies || []).join(',');
        const status = task.status || 'undone';

        const el = document.createElement('div');
        el.className = ['tree-task', withStatus ? `task-status-${status}` : '', isIdea ? 'tree-task-idea' : ''].filter(Boolean).join(' ');
        el.setAttribute('data-task-id', tid);
        el.setAttribute('data-dependencies', deps);
        el.setAttribute('data-task-data', JSON.stringify(getTaskDataForPopover(task)));
        el.setAttribute('title', displayText);

        const numSpan = document.createElement('span');
        numSpan.className = 'task-number';
        numSpan.textContent = label;

        const descSpan = document.createElement('span');
        descSpan.className = 'task-description';
        descSpan.textContent = truncated;

        el.appendChild(numSpan);
        el.appendChild(descSpan);
        return el;
    }

    const scrollHandlerStateByArea = new Map();

    function attachScrollRedraw(areaSelector, container, lines) {
        const tree = container?.querySelector('.tasks-tree');
        const scrollEl = tree?.parentElement;
        if (!scrollEl || !lines?.length) return;
        const prev = scrollHandlerStateByArea.get(areaSelector);
        if (prev) {
            prev.el.removeEventListener('scroll', prev.handler);
            scrollHandlerStateByArea.delete(areaSelector);
        }
        const handler = () => requestAnimationFrame(() => drawConnectionLines(container, lines));
        scrollEl.addEventListener('scroll', handler);
        scrollHandlerStateByArea.set(areaSelector, { el: scrollEl, handler });
    }

    function drawConnectionLines(container, lines) {
        if (!lines?.length) return;
        const svg = container?.querySelector('.tree-connection-lines');
        const tree = container?.querySelector('.tasks-tree') || container;
        if (!svg || !tree) return;

        svg.setAttribute('width', tree.scrollWidth);
        svg.setAttribute('height', tree.scrollHeight);
        svg.setAttribute('viewBox', `0 0 ${tree.scrollWidth} ${tree.scrollHeight}`);
        svg.innerHTML = '';

        const elMap = new Map();
        container.querySelectorAll(TASK_NODE_SELECTOR).forEach(el => {
            const id = el.getAttribute('data-task-id');
            if (id) elMap.set(id, el);
        });

        const treeRect = tree.getBoundingClientRect();
        lines.forEach(line => {
            const fromEl = elMap.get(line.fromTaskId);
            const toEl = elMap.get(line.toTaskId);
            if (!fromEl || !toEl) return;

            const fromR = fromEl.getBoundingClientRect();
            const toR = toEl.getBoundingClientRect();
            const fromX = fromR.left + fromR.width / 2 - treeRect.left + tree.scrollLeft;
            const fromY = fromR.top + fromR.height - treeRect.top + tree.scrollTop;
            const toX = toR.left + toR.width / 2 - treeRect.left + tree.scrollLeft;
            const toY = toR.top - treeRect.top + tree.scrollTop;
            const midY = (fromY + toY) / 2;

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', `M ${fromX} ${fromY} L ${fromX} ${midY} L ${toX} ${midY} L ${toX} ${toY}`);
            path.setAttribute('stroke-width', '1');
            path.setAttribute('fill', 'none');
            path.setAttribute('data-from-task', line.fromTaskId);
            path.setAttribute('data-to-task', line.toTaskId);
            path.setAttribute('class', 'connection-line');
            svg.appendChild(path);
        });
    }

    function refreshConnections(areaSelector, tasks) {
        const ctx = getTreeContainer(areaSelector);
        if (!ctx) return;
        const lines = buildConnectionLines(tasks);
        requestAnimationFrame(() => {
            drawConnectionLines(ctx.area, lines);
            attachScrollRedraw(areaSelector, ctx.area, lines);
        });
    }

    function getOrCreateStageDiv(tree, stageNum) {
        let stageDiv = tree.querySelector(`.tree-stage[data-stage="${stageNum}"]`);
        if (!stageDiv) {
            stageDiv = document.createElement('div');
            stageDiv.className = 'tree-stage';
            stageDiv.setAttribute('data-stage', String(stageNum));
            const tasksDiv = document.createElement('div');
            tasksDiv.className = 'tree-stage-tasks';
            stageDiv.appendChild(tasksDiv);
            const existing = tree.querySelectorAll('.tree-stage');
            const insertBefore = Array.from(existing).find(s => parseInt(s.dataset.stage, 10) > stageNum);
            tree.insertBefore(stageDiv, insertBefore || null);
        }
        return stageDiv.querySelector('.tree-stage-tasks');
    }

    function groupTasksByStage(tasks) {
        const valid = (tasks || []).filter(t => t?.task_id && t.stage != null);
        const map = new Map();
        valid.forEach(t => {
            const idx = t.stage - 1;
            if (!map.has(idx)) map.set(idx, []);
            map.get(idx).push(t);
        });
        return map;
    }

    function renderFull(treeData, areaSelector, options = {}) {
        const ctx = getTreeContainer(areaSelector);
        if (!ctx) return;

        const withStatusFn = typeof options.withStatus === 'function'
            ? options.withStatus
            : () => (options.withStatus !== false);
        const tasks = (treeData || []).filter(t => t?.task_id && t.stage != null);

        if (areaSelector === AREA.planner) plannerTreeData = treeData || [];

        ctx.tree.querySelectorAll('.tree-stage').forEach(el => el.remove());
        const svg = ctx.tree.querySelector('.tree-connection-lines');
        if (svg) svg.innerHTML = '';

        if (tasks.length === 0) {
            const prev = scrollHandlerStateByArea.get(areaSelector);
            if (prev) {
                prev.el.removeEventListener('scroll', prev.handler);
                scrollHandlerStateByArea.delete(areaSelector);
            }
            return;
        }

        const stages = groupTasksByStage(tasks);
        [...stages.keys()].sort((a, b) => a - b).forEach(stageIdx => {
            const tasksDiv = getOrCreateStageDiv(ctx.tree, stageIdx + 1);
            stages.get(stageIdx).forEach(task => {
                const withStatus = withStatusFn(task);
                tasksDiv.appendChild(createTaskNodeEl(task, { withStatus, isIdea: task.task_id === '0' }));
            });
        });

        refreshConnections(areaSelector, tasks);
    }

    function clear(areaSelector) {
        if (areaSelector === AREA.planner) plannerTreeData = [];
        const prev = scrollHandlerStateByArea.get(areaSelector);
        if (prev) {
            prev.el.removeEventListener('scroll', prev.handler);
            scrollHandlerStateByArea.delete(areaSelector);
        }
        const ctx = getTreeContainer(areaSelector);
        if (!ctx) return;
        ctx.tree.querySelectorAll('.tree-stage').forEach(el => el.remove());
        const svg = ctx.tree.querySelector('.tree-connection-lines');
        if (svg) svg.innerHTML = '';
    }

    function renderPlannerTree(treeData) {
        if (!Array.isArray(treeData)) return;
        plannerTreeData = treeData;
        renderFull(plannerTreeData, AREA.planner, { withStatus: (task) => task.status != null });
    }

    function redrawConnections(areaSelector) {
        const tasks = areaSelector === AREA.planner ? plannerTreeData : null;
        if (!tasks || tasks.length < 2) return;
        const lines = buildConnectionLines(tasks);
        if (lines.length === 0) return;
        const ctx = getTreeContainer(areaSelector);
        if (ctx) requestAnimationFrame(() => drawConnectionLines(ctx.area, lines));
    }

    // Popover
    let popoverEl = null;
    let popoverAnchor = null;
    let popoverOutsideClickHandler = null;
    let popoverKeydownHandler = null;

    function escapeHtml(str) {
        if (str == null) return '';
        const div = document.createElement('div');
        div.textContent = String(str);
        return div.innerHTML;
    }

    function showTaskPopover(task, anchorEl) {
        if (popoverEl && popoverAnchor === anchorEl) {
            hideTaskPopover();
            return;
        }
        hideTaskPopover();

        const desc = (task.description || task.objective || '').trim() || '-';
        const deps = (task.dependencies || []).length > 0 ? (task.dependencies || []).join(', ') : 'None';
        const hasStatus = task.status != null;
        const statusRow = hasStatus ? `<div class="task-detail-row"><span class="task-detail-label">Status:</span><span class="task-detail-value task-status-${task.status}">${escapeHtml(task.status)}</span></div>` : '';
        const hasInputOutput = task.input && task.output;
        const inputRow = hasInputOutput ? `<div class="task-detail-row"><span class="task-detail-label">Input:</span><span class="task-detail-value">${escapeHtml(task.input.description || '-')}</span></div>` : '';
        const out = task.output || {};
        const outputDesc = hasInputOutput ? [out.artifact || out.description, out.format].filter(Boolean).join(' · ') || '-' : '';
        const outputRow = hasInputOutput ? `<div class="task-detail-row"><span class="task-detail-label">Output:</span><span class="task-detail-value">${escapeHtml(outputDesc)}</span></div>` : '';

        popoverEl = document.createElement('div');
        popoverEl.className = 'task-detail-popover';
        popoverEl.setAttribute('role', 'dialog');
        popoverEl.setAttribute('aria-label', 'Task details');
        popoverEl.innerHTML = `
            <div class="task-detail-popover-header">
                <span class="task-detail-popover-title">${escapeHtml(task.task_id)}</span>
                <button class="task-detail-popover-close" aria-label="Close">&times;</button>
            </div>
            <div class="task-detail-popover-body">
                <div class="task-detail-row"><span class="task-detail-label">Description:</span><span class="task-detail-value">${escapeHtml(desc)}</span></div>
                <div class="task-detail-row"><span class="task-detail-label">Dependencies:</span><span class="task-detail-value">${escapeHtml(deps)}</span></div>
                ${statusRow}
                ${inputRow}
                ${outputRow}
            </div>
        `;

        document.body.appendChild(popoverEl);
        popoverAnchor = anchorEl;

        const rect = anchorEl.getBoundingClientRect();
        const gap = 8;
        let left = rect.right + gap;
        let top = rect.top + rect.height / 2 - popoverEl.offsetHeight / 2;
        if (left + popoverEl.offsetWidth > window.innerWidth - 12) left = rect.left - popoverEl.offsetWidth - gap;
        if (left < 12) left = 12;
        if (top < 12) top = 12;
        if (top + popoverEl.offsetHeight > window.innerHeight - 12) top = window.innerHeight - popoverEl.offsetHeight - 12;

        popoverEl.style.left = left + 'px';
        popoverEl.style.top = top + 'px';

        popoverEl.querySelector('.task-detail-popover-close').addEventListener('click', hideTaskPopover);
        popoverOutsideClickHandler = (e) => {
            if (popoverEl && !popoverEl.contains(e.target) && !e.target.closest('.tree-task')) hideTaskPopover();
        };
        popoverKeydownHandler = (e) => { if (e.key === 'Escape') hideTaskPopover(); };
        document.addEventListener('click', popoverOutsideClickHandler);
        document.addEventListener('keydown', popoverKeydownHandler);
    }

    function hideTaskPopover() {
        if (popoverOutsideClickHandler) {
            document.removeEventListener('click', popoverOutsideClickHandler);
            popoverOutsideClickHandler = null;
        }
        if (popoverKeydownHandler) {
            document.removeEventListener('keydown', popoverKeydownHandler);
            popoverKeydownHandler = null;
        }
        if (popoverEl) {
            popoverEl.remove();
            popoverEl = null;
            popoverAnchor = null;
        }
    }

    function initClickHandlers() {
        document.addEventListener('click', (e) => {
            const node = e.target.closest('.tree-task, .timetable-cell:not(.timetable-cell-empty)');
            if (!node) return;
            const data = node.getAttribute('data-task-data');
            if (!data) return;
            try {
                showTaskPopover(JSON.parse(data), node);
                e.stopPropagation();
            } catch (_) {}
        });
    }

    // Public API
    window.TaskTree = {
        AREA,
        renderPlannerTree,
        renderMonitorTasksTree: (data) => renderFull(data, AREA.monitor, { withStatus: (task) => task.status != null }),
        clearPlannerTree: () => clear(AREA.planner),
        redrawPlannerConnectionLines: () => redrawConnections(AREA.planner),
        initClickHandlers,
        showTaskPopover,
        hideTaskPopover,
        buildTaskDataForPopover: (task) => getTaskDataForPopover(task),
        get plannerTreeData() { return plannerTreeData; },
    };
})();
