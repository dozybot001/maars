/**
 * Task tree rendering module.
 * Uses pre-computed layout from backend (Sugiyama algorithm).
 */
(function () {
    'use strict';

    const AREA = {
        planner: '.planner-tree-area',
        monitor: '.monitor-tasks-tree-area',
    };

    let plannerTreeData = [];
    let plannerLayout = null;

    function getTreeContainer(areaSelector) {
        const area = document.querySelector(areaSelector);
        const tree = area?.querySelector('.tasks-tree');
        return area && tree ? { area, tree } : null;
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
            validation: task.validation,
            task_type: task.task_type,
            inputs: task.inputs,
            outputs: task.outputs,
            target: task.target,
            timeout_seconds: task.timeout_seconds,
        };
    }

    function createTaskNodeEl(task) {
        const tid = task.task_id;
        const desc = (task.description || task.objective || '').trim() || tid || 'Task';

        const el = document.createElement('div');
        el.className = 'tree-task';
        el.setAttribute('data-task-id', tid);
        el.setAttribute('data-task-data', JSON.stringify(getTaskDataForPopover(task)));
        el.setAttribute('title', desc);

        return el;
    }

    function buildSmoothPath(pts) {
        if (pts.length === 2) {
            const [x1, y1] = pts[0];
            const [x2, y2] = pts[1];
            const my = (y1 + y2) / 2;
            return `M ${x1} ${y1} C ${x1} ${my}, ${x2} ${my}, ${x2} ${y2}`;
        }
        let d = `M ${pts[0][0]} ${pts[0][1]}`;
        for (let i = 0; i < pts.length - 1; i++) {
            const [x1, y1] = pts[i];
            const [x2, y2] = pts[i + 1];
            const my = (y1 + y2) / 2;
            d += ` C ${x1} ${my}, ${x2} ${my}, ${x2} ${y2}`;
        }
        return d;
    }

    function renderFull(treeData, layout, areaSelector) {
        const ctx = getTreeContainer(areaSelector);
        if (!ctx) return;

        const tasks = (treeData || []).filter(t => t?.task_id);

        if (areaSelector === AREA.planner) {
            plannerTreeData = treeData || [];
            plannerLayout = layout || null;
        }

        ctx.tree.innerHTML = '';

        if (tasks.length === 0 || !layout) return;

        const { nodes, edges, width, height } = layout;
        if (!nodes) return;

        ctx.tree.style.width = width + 'px';
        ctx.tree.style.height = height + 'px';
        ctx.tree.style.minHeight = height + 'px';

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('class', 'tree-connection-lines');
        svg.setAttribute('width', width);
        svg.setAttribute('height', height);
        svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
        ctx.tree.appendChild(svg);

        (edges || []).forEach(edge => {
            const pts = edge.points;
            if (!pts || pts.length < 2) return;
            const d = buildSmoothPath(pts);
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', d);
            path.setAttribute('stroke-width', '1.5');
            path.setAttribute('fill', 'none');
            path.setAttribute('data-from-task', edge.from);
            path.setAttribute('data-to-task', edge.to);
            path.setAttribute('class', 'connection-line');
            svg.appendChild(path);
        });

        const nodesContainer = document.createElement('div');
        nodesContainer.className = 'tree-nodes-container';
        nodesContainer.style.cssText = `position:absolute;top:0;left:0;width:${width}px;height:${height}px;`;
        ctx.tree.appendChild(nodesContainer);

        const taskById = new Map(tasks.map(t => [t.task_id, t]));
        const parentIds = new Set((edges || []).map(e => e.from));
        const leafIds = new Set(Object.keys(nodes).filter(id => !parentIds.has(id)));

        for (const [taskId, pos] of Object.entries(nodes)) {
            const task = taskById.get(taskId);
            if (!task) continue;

            const el = createTaskNodeEl(task);
            if (areaSelector === AREA.planner && leafIds.has(taskId)) el.classList.add('tree-task-leaf');
            el.style.position = 'absolute';
            el.style.left = pos.x + 'px';
            el.style.top = pos.y + 'px';
            el.style.width = pos.w + 'px';
            el.style.minHeight = pos.h + 'px';
            nodesContainer.appendChild(el);
        }
    }

    function clear(areaSelector) {
        if (areaSelector === AREA.planner) {
            plannerTreeData = [];
            plannerLayout = null;
        }
        const ctx = getTreeContainer(areaSelector);
        if (!ctx) return;
        ctx.tree.innerHTML = '';
        ctx.tree.style.width = '';
        ctx.tree.style.height = '';
        ctx.tree.style.minHeight = '';
    }

    function renderPlannerTree(treeData, layout) {
        if (!Array.isArray(treeData)) return;
        plannerTreeData = treeData;
        plannerLayout = layout || null;
        renderFull(plannerTreeData, layout, AREA.planner);
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
        const v = task.validation;
        const hasValidation = v && (v.description || (Array.isArray(v.criteria) && v.criteria.length > 0));
        const validationRow = hasValidation ? (() => {
            const desc = v.description ? `<div class="validation-desc">${escapeHtml(v.description)}</div>` : '';
            const criteriaList = (v.criteria || []).map(c => `<li>${escapeHtml(c)}</li>`).join('');
            const criteriaHtml = criteriaList ? `<ul class="validation-criteria">${criteriaList}</ul>` : '';
            const optionalList = (v.optionalChecks || []).map(c => `<li>${escapeHtml(c)}</li>`).join('');
            const optionalHtml = optionalList ? `<ul class="validation-optional">${optionalList}</ul>` : '';
            return `<div class="task-detail-row task-detail-validation"><span class="task-detail-label">Validation:</span><div class="task-detail-value">${desc}${criteriaHtml}${optionalHtml}</div></div>`;
        })() : '';

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
                ${validationRow}
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

    function updatePlannerQualityBadge(score, comment) {
        const badge = document.getElementById('plannerQualityBadge');
        if (!badge) return;
        if (score == null || score === undefined) {
            badge.style.display = 'none';
            return;
        }
        badge.textContent = `质量: ${score}`;
        badge.title = comment || '';
        badge.style.display = '';
        badge.classList.remove('quality-high', 'quality-mid', 'quality-low');
        if (score >= 80) badge.classList.add('quality-high');
        else if (score >= 60) badge.classList.add('quality-mid');
        else badge.classList.add('quality-low');
    }

    window.TaskTree = {
        AREA,
        renderPlannerTree,
        renderMonitorTasksTree: (data, layout) => renderFull(data, layout, AREA.monitor),
        clearPlannerTree: () => { clear(AREA.planner); updatePlannerQualityBadge(null); },
        initClickHandlers,
        showTaskPopover,
        hideTaskPopover,
        updatePlannerQualityBadge,
        buildTaskDataForPopover: (task) => getTaskDataForPopover(task),
        get plannerTreeData() { return plannerTreeData; },
        get plannerLayout() { return plannerLayout; },
    };
})();
