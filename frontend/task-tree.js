/**
 * Task tree rendering module.
 * Uses dagre for layout to minimize edge crossings.
 */
(function () {
    'use strict';

    const TRUNCATE_LEN = 60;
    const NODE_WIDTH = 110;
    const NODE_HEIGHT = 52;
    const DAGRE_PADDING = 20;

    const AREA = {
        planner: '.planner-tree-area',
        monitor: '.monitor-tasks-tree-area',
    };

    let plannerTreeData = [];
    const layoutCacheByArea = new Map();

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

    function computeDagreLayout(tasks) {
        if (typeof dagre === 'undefined') {
            console.warn('dagre not loaded, using fallback layout');
            return computeFallbackLayout(tasks);
        }
        const valid = (tasks || [])
            .filter(t => t?.task_id)
            .sort((a, b) => String(a.task_id || '').localeCompare(String(b.task_id || '')));
        if (valid.length === 0) return null;

        const ids = new Set(valid.map(t => t.task_id));
        const lines = buildConnectionLines(tasks);

        const g = new dagre.graphlib.Graph();
        g.setGraph({
            rankdir: 'TB',
            nodesep: 40,
            ranksep: 60,
            marginx: DAGRE_PADDING,
            marginy: DAGRE_PADDING,
        });
        g.setDefaultEdgeLabel(() => ({}));

        valid.forEach(t => {
            g.setNode(t.task_id, { width: NODE_WIDTH, height: NODE_HEIGHT });
        });
        lines.forEach(({ fromTaskId, toTaskId }) => {
            if (ids.has(fromTaskId) && ids.has(toTaskId)) {
                g.setEdge(fromTaskId, toTaskId);
            }
        });

        dagre.layout(g);

        const nodePositions = new Map();
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

        g.nodes().forEach(id => {
            const n = g.node(id);
            if (!n) return;
            const x = n.x - n.width / 2;
            const y = n.y - n.height / 2;
            nodePositions.set(id, { x, y, width: n.width, height: n.height, centerX: n.x, centerY: n.y });
            minX = Math.min(minX, x);
            minY = Math.min(minY, y);
            maxX = Math.max(maxX, x + n.width);
            maxY = Math.max(maxY, y + n.height);
        });

        const graphWidth = Math.max(maxX - minX + DAGRE_PADDING * 2, 200);
        const graphHeight = Math.max(maxY - minY + DAGRE_PADDING * 2, 150);

        return {
            nodePositions,
            lines,
            graphWidth,
            graphHeight,
            offsetX: minX - DAGRE_PADDING,
            offsetY: minY - DAGRE_PADDING,
        };
    }

    function computeFallbackLayout(tasks) {
        const valid = (tasks || [])
            .filter(t => t?.task_id)
            .sort((a, b) => String(a.task_id || '').localeCompare(String(b.task_id || '')));
        if (valid.length === 0) return null;

        const lines = buildConnectionLines(tasks);
        const ids = new Set(valid.map(t => t.task_id));

        const stages = [];
        const placed = new Set();
        let current = valid.filter(t => !(t.dependencies || []).some(d => ids.has(d)));
        while (current.length > 0) {
            stages.push(current);
            current.forEach(t => placed.add(t.task_id));
            const next = valid.filter(t => !placed.has(t.task_id) && (t.dependencies || []).every(d => placed.has(d)));
            current = next;
        }
        const orphan = valid.filter(t => !placed.has(t.task_id));
        if (orphan.length > 0) stages.push(orphan);

        const nodePositions = new Map();
        let y = DAGRE_PADDING;
        const ranksep = 60;
        const nodesep = 40;

        stages.forEach((rankTasks) => {
            let x = DAGRE_PADDING;
            rankTasks.forEach((t, i) => {
                const cx = x + NODE_WIDTH / 2;
                const cy = y + NODE_HEIGHT / 2;
                nodePositions.set(t.task_id, {
                    x: cx - NODE_WIDTH / 2,
                    y: cy - NODE_HEIGHT / 2,
                    width: NODE_WIDTH,
                    height: NODE_HEIGHT,
                    centerX: cx,
                    centerY: cy,
                });
                x += NODE_WIDTH + nodesep;
            });
            y += NODE_HEIGHT + ranksep;
        });

        const graphWidth = Math.max(200, stages.reduce((w, r) => Math.max(w, r.length * (NODE_WIDTH + nodesep) - nodesep), 0) + DAGRE_PADDING * 2);
        const graphHeight = y - ranksep + DAGRE_PADDING;

        return {
            nodePositions,
            lines,
            graphWidth,
            graphHeight,
            offsetX: 0,
            offsetY: 0,
        };
    }

    function drawConnectionLines(container, layout) {
        if (!layout?.lines?.length) return;
        const svg = container?.querySelector('.tree-connection-lines');
        if (!svg) return;

        const { nodePositions, lines, offsetX, offsetY } = layout;

        svg.innerHTML = '';
        lines.forEach(line => {
            const fromPos = nodePositions.get(line.fromTaskId);
            const toPos = nodePositions.get(line.toTaskId);
            if (!fromPos || !toPos) return;

            const fromX = fromPos.centerX - offsetX;
            const fromY = fromPos.y + fromPos.height - offsetY;
            const toX = toPos.centerX - offsetX;
            const toY = toPos.y - offsetY;
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

    function renderFull(treeData, areaSelector, options = {}) {
        const ctx = getTreeContainer(areaSelector);
        if (!ctx) return;

        const withStatusFn = typeof options.withStatus === 'function'
            ? options.withStatus
            : () => (options.withStatus !== false);
        const tasks = (treeData || []).filter(t => t?.task_id);

        if (areaSelector === AREA.planner) plannerTreeData = treeData || [];

        ctx.tree.innerHTML = '';
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('class', 'tree-connection-lines');

        if (tasks.length === 0) {
            layoutCacheByArea.delete(areaSelector);
            return;
        }

        const layout = computeDagreLayout(tasks);
        if (!layout) {
            return;
        }

        layoutCacheByArea.set(areaSelector, layout);

        ctx.tree.style.width = layout.graphWidth + 'px';
        ctx.tree.style.height = layout.graphHeight + 'px';
        ctx.tree.style.minHeight = layout.graphHeight + 'px';
        ctx.tree.appendChild(svg);

        svg.setAttribute('width', layout.graphWidth);
        svg.setAttribute('height', layout.graphHeight);
        svg.setAttribute('viewBox', `0 0 ${layout.graphWidth} ${layout.graphHeight}`);

        const nodesContainer = document.createElement('div');
        nodesContainer.className = 'tree-nodes-container';
        nodesContainer.style.cssText = `position:absolute;top:0;left:0;width:${layout.graphWidth}px;height:${layout.graphHeight}px;`;
        ctx.tree.appendChild(nodesContainer);

        const { nodePositions, offsetX, offsetY } = layout;
        const taskById = new Map(tasks.map(t => [t.task_id, t]));

        nodePositions.forEach((pos, taskId) => {
            const task = taskById.get(taskId);
            if (!task) return;

            const el = createTaskNodeEl(task, {
                withStatus: withStatusFn(task),
                isIdea: taskId === '0',
            });
            el.style.position = 'absolute';
            el.style.left = (pos.x - offsetX) + 'px';
            el.style.top = (pos.y - offsetY) + 'px';
            el.style.width = pos.width + 'px';
            el.style.minHeight = pos.height + 'px';
            nodesContainer.appendChild(el);
        });

        drawConnectionLines(ctx.area, layout);
    }

    function clear(areaSelector) {
        if (areaSelector === AREA.planner) plannerTreeData = [];
        layoutCacheByArea.delete(areaSelector);
        const ctx = getTreeContainer(areaSelector);
        if (!ctx) return;
        ctx.tree.innerHTML = '';
        ctx.tree.style.width = '';
        ctx.tree.style.height = '';
        ctx.tree.style.minHeight = '';
    }

    function renderPlannerTree(treeData) {
        if (!Array.isArray(treeData)) return;
        plannerTreeData = treeData;
        renderFull(plannerTreeData, AREA.planner, { withStatus: (task) => task.status != null });
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
        const outputDesc = hasInputOutput ? [out.artifact || out.description, out.format].filter(Boolean).join(' · ') || '-' : '-';
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

    window.TaskTree = {
        AREA,
        renderPlannerTree,
        renderMonitorTasksTree: (data) => renderFull(data, AREA.monitor, { withStatus: (task) => task.status != null }),
        clearPlannerTree: () => clear(AREA.planner),
        initClickHandlers,
        showTaskPopover,
        hideTaskPopover,
        buildTaskDataForPopover: (task) => getTaskDataForPopover(task),
        get plannerTreeData() { return plannerTreeData; },
    };
})();
