/**
 * Task tree rendering module
 * Frontend only renders; backend provides treeData (tasks with stage). No computation.
 */
(function () {
    'use strict';

    const TRUNCATE_LEN = 60;
    const TASK_SELECTOR = '.tree-task, [data-task-id]';

    let plannerTasks = [];

    function buildConnectionLines(tasks) {
        const lines = [];
        const ids = new Set(tasks.map(t => t.task_id));
        tasks.forEach(task => {
            const tid = task.task_id;
            if (!tid) return;
            (task.dependencies || []).forEach(depId => {
                if (ids.has(depId)) lines.push({ fromTaskId: depId, toTaskId: tid });
            });
        });
        return lines;
    }

    /** @returns {{ displayText: string, truncated: string, label: string }} */
    function formatTaskDisplay(task) {
        const tid = task.task_id;
        const displayText = (task.description || task.objective || '').trim() || tid || 'Task';
        const truncated = displayText.length > TRUNCATE_LEN ? displayText.slice(0, TRUNCATE_LEN - 3) + '...' : displayText;
        return { displayText, truncated, label: tid };
    }

    /**
     * Extract serializable task data for popover display
     */
    function getTaskDataForStorage(task) {
        return {
            task_id: task.task_id,
            description: task.description,
            objective: task.objective,
            dependencies: task.dependencies,
            status: task.status,
            task_type: task.task_type,
            inputs: task.inputs,
            outputs: task.outputs,
            target: task.target,
            timeout_seconds: task.timeout_seconds
        };
    }

    /**
     * Create a single task node element. Used by both full render and incremental append.
     * @param {Object} task - { task_id, description?, objective?, dependencies?, status? }
     * @param {{ withStatus?: boolean, isIdea?: boolean }} options
     */
    function createTaskNode(task, options = {}) {
        const { withStatus = false, isIdea = false } = options;
        const tid = task.task_id;
        const { displayText, truncated, label } = formatTaskDisplay(task);
        const deps = (task.dependencies || []).join(',');
        const status = task.status || 'undone';

        const taskDiv = document.createElement('div');
        const statusClass = withStatus ? `task-status-${status}` : '';
        const ideaClass = isIdea ? 'tree-task-idea' : '';
        taskDiv.setAttribute('class', `tree-task ${statusClass} ${ideaClass}`.trim());
        taskDiv.setAttribute('data-task-id', tid);
        taskDiv.setAttribute('data-dependencies', deps);
        taskDiv.setAttribute('data-task-data', JSON.stringify(getTaskDataForStorage(task)));
        taskDiv.setAttribute('title', displayText);

        const numberSpan = document.createElement('span');
        numberSpan.setAttribute('class', 'task-number');
        numberSpan.textContent = label;

        const descSpan = document.createElement('span');
        descSpan.setAttribute('class', 'task-description');
        descSpan.textContent = truncated;

        taskDiv.appendChild(numberSpan);
        taskDiv.appendChild(descSpan);
        return taskDiv;
    }

    let scrollRedrawState = null;

    function attachScrollRedraw(container, connectionLines) {
        const treeContainer = container?.querySelector('.tasks-tree');
        const scrollContainer = treeContainer?.parentElement;
        if (!scrollContainer || !connectionLines?.length) return;
        if (scrollRedrawState) {
            scrollRedrawState.scrollContainer.removeEventListener('scroll', scrollRedrawState.handler);
        }
        const handler = () => requestAnimationFrame(() => drawConnectionLines(container, connectionLines));
        scrollContainer.addEventListener('scroll', handler);
        scrollRedrawState = { scrollContainer, handler };
    }

    function drawConnectionLines(container, connectionLines) {
        if (!connectionLines || connectionLines.length === 0) return;

        const svg = container.querySelector('.tree-connection-lines');
        const treeContainer = container.querySelector('.tasks-tree') || container;
        if (!svg || !treeContainer) return;

        const scrollWidth = treeContainer.scrollWidth;
        const scrollHeight = treeContainer.scrollHeight;
        svg.setAttribute('width', scrollWidth.toString());
        svg.setAttribute('height', scrollHeight.toString());
        svg.setAttribute('viewBox', `0 0 ${scrollWidth} ${scrollHeight}`);
        svg.innerHTML = '';

        const taskElementMap = new Map();
        container.querySelectorAll(TASK_SELECTOR).forEach(el => {
            const tid = el.getAttribute('data-task-id');
            if (tid) taskElementMap.set(tid, el);
        });

        connectionLines.forEach(line => {
            const depTaskEl = taskElementMap.get(line.fromTaskId);
            const taskEl = taskElementMap.get(line.toTaskId);
            if (!depTaskEl || !taskEl) return;

            const depRect = depTaskEl.getBoundingClientRect();
            const taskRect = taskEl.getBoundingClientRect();
            const containerRect = treeContainer.getBoundingClientRect();

            const depX = depRect.left + depRect.width / 2 - containerRect.left + treeContainer.scrollLeft;
            const depY = depRect.top + depRect.height - containerRect.top + treeContainer.scrollTop;
            const taskX = taskRect.left + taskRect.width / 2 - containerRect.left + treeContainer.scrollLeft;
            const taskY = taskRect.top - containerRect.top + treeContainer.scrollTop;

            const midY = (depY + taskY) / 2;
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', `M ${depX} ${depY} L ${depX} ${midY} L ${taskX} ${midY} L ${taskX} ${taskY}`);
            path.setAttribute('stroke-width', '1');
            path.setAttribute('fill', 'none');
            path.setAttribute('data-from-task', line.fromTaskId);
            path.setAttribute('data-to-task', line.toTaskId);
            path.setAttribute('class', 'connection-line');
            svg.appendChild(path);
        });
    }

    /**
     * Render task tree from backend treeData (tasks with stage). No computation.
     * @param {Array} tasks - Flat tasks with stage from backend
     * @param {string} areaSelector - e.g. '.planner-tree-area' or '.monitor-tasks-tree-area'
     * @param {Object} options - { withStatus: true }
     */
    function _renderTaskTree(tasks, areaSelector, options = {}) {
        const area = document.querySelector(areaSelector);
        const tasksTree = area?.querySelector('.monitor-tasks-tree') || area?.querySelector('.tasks-tree');
        if (!area || !tasksTree) return;

        const withStatus = options.withStatus !== false;

        tasksTree.querySelectorAll('.tree-stage').forEach(el => el.remove());
        const svg = tasksTree.querySelector('.tree-connection-lines');
        if (svg) svg.innerHTML = '';

        const validTasks = (tasks || []).filter(t => t && t.task_id && t.stage != null);
        if (validTasks.length === 0) return;

        const stages = new Map();
        validTasks.forEach(t => {
            const stageIdx = t.stage - 1;
            if (!stages.has(stageIdx)) stages.set(stageIdx, []);
            stages.get(stageIdx).push(t);
        });

        const sortedStageIndices = [...stages.keys()].sort((a, b) => a - b);
        sortedStageIndices.forEach(stageIdx => {
            const stageDiv = document.createElement('div');
            stageDiv.setAttribute('class', 'tree-stage');
            stageDiv.setAttribute('data-stage', String(stageIdx + 1));
            const tasksDiv = document.createElement('div');
            tasksDiv.setAttribute('class', 'tree-stage-tasks');
            stages.get(stageIdx).forEach(task => {
                const isIdea = task.task_id === '0';
                const taskDiv = createTaskNode(task, { withStatus, isIdea });
                tasksDiv.appendChild(taskDiv);
            });
            stageDiv.appendChild(tasksDiv);
            tasksTree.appendChild(stageDiv);
        });

        const lines = buildConnectionLines(validTasks);
        requestAnimationFrame(() => {
            drawConnectionLines(area, lines);
            attachScrollRedraw(area, lines);
        });
    }

    function clearPlannerTree() {
        plannerTasks = [];
        if (scrollRedrawState) {
            scrollRedrawState.scrollContainer.removeEventListener('scroll', scrollRedrawState.handler);
            scrollRedrawState = null;
        }
        const area = document.querySelector('.planner-tree-area');
        const tasksTree = area?.querySelector('.planner-tasks-tree') || area?.querySelector('.tasks-tree');
        if (tasksTree) {
            tasksTree.querySelectorAll('.tree-stage').forEach(el => el.remove());
            const svg = tasksTree.querySelector('.tree-connection-lines');
            if (svg) svg.innerHTML = '';
        }
    }

    function appendPlannerTaskNode(task) {
        const tid = task?.task_id;
        if (!task || !tid || task.stage == null) return;
        plannerTasks.push(task);

        const area = document.querySelector('.planner-tree-area');
        const tasksTree = area?.querySelector('.planner-tasks-tree') || area?.querySelector('.tasks-tree');
        if (!area || !tasksTree) return;

        const stageIdx = task.stage - 1;
        let stageDiv = tasksTree.querySelector(`.tree-stage[data-stage="${task.stage}"]`);
        if (!stageDiv) {
            stageDiv = document.createElement('div');
            stageDiv.setAttribute('class', 'tree-stage');
            stageDiv.setAttribute('data-stage', String(task.stage));
            const tasksDiv = document.createElement('div');
            tasksDiv.setAttribute('class', 'tree-stage-tasks');
            stageDiv.appendChild(tasksDiv);
            const existingStages = tasksTree.querySelectorAll('.tree-stage');
            const insertBefore = Array.from(existingStages).find(s => parseInt(s.dataset.stage, 10) > task.stage);
            tasksTree.insertBefore(stageDiv, insertBefore || null);
        }
        const tasksDiv = stageDiv.querySelector('.tree-stage-tasks');
        const isIdea = task.task_id === '0';
        tasksDiv.appendChild(createTaskNode(task, { withStatus: false, isIdea }));

        const lines = buildConnectionLines(plannerTasks);
        requestAnimationFrame(() => {
            drawConnectionLines(area, lines);
            attachScrollRedraw(area, lines);
        });
    }

    /** Unified entry: flat treeData only. Planner/Monitor use same format. */
    function renderTree(treeData, areaSelector, options = {}) {
        if (!treeData || treeData.length === 0) return;
        if (areaSelector === '.planner-tree-area') plannerTasks = treeData;
        _renderTaskTree(treeData, areaSelector, options);
    }

    function renderPlannerTree(treeData) {
        renderTree(treeData, '.planner-tree-area', { withStatus: false });
    }

    function renderMonitorTasksTree(treeData) {
        renderTree(treeData, '.monitor-tasks-tree-area', { withStatus: true });
    }

    function redrawPlannerConnectionLines() {
        if (!plannerTasks || plannerTasks.length < 2) return;
        const area = document.querySelector('.planner-tree-area');
        if (!area) return;
        const lines = buildConnectionLines(plannerTasks);
        if (lines.length > 0) requestAnimationFrame(() => drawConnectionLines(area, lines));
    }

    let taskDetailPopover = null;
    let taskDetailPopoverAnchor = null;

    function showTaskDetailPopover(task, anchorEl) {
        if (taskDetailPopover && taskDetailPopoverAnchor === anchorEl) {
            hideTaskDetailPopover();
            return;
        }
        hideTaskDetailPopover();
        const rect = anchorEl.getBoundingClientRect();
        const popover = document.createElement('div');
        popover.className = 'task-detail-popover';
        popover.setAttribute('role', 'dialog');
        popover.setAttribute('aria-label', 'Task details');

        const desc = (task.description || task.objective || '').trim() || '-';
        const deps = (task.dependencies || []).length > 0
            ? (task.dependencies || []).join(', ')
            : 'None';
        const status = task.status || 'undone';

        popover.innerHTML = `
            <div class="task-detail-popover-header">
                <span class="task-detail-popover-title">${escapeHtml(task.task_id)}</span>
                <button class="task-detail-popover-close" aria-label="Close">&times;</button>
            </div>
            <div class="task-detail-popover-body">
                <div class="task-detail-row"><span class="task-detail-label">Description:</span><span class="task-detail-value">${escapeHtml(desc)}</span></div>
                <div class="task-detail-row"><span class="task-detail-label">Dependencies:</span><span class="task-detail-value">${escapeHtml(deps)}</span></div>
                <div class="task-detail-row"><span class="task-detail-label">Status:</span><span class="task-detail-value task-status-${status}">${escapeHtml(status)}</span></div>
            </div>
        `;

        document.body.appendChild(popover);
        taskDetailPopover = popover;
        taskDetailPopoverAnchor = anchorEl;

        const gap = 8;
        let left = rect.right + gap;
        let top = rect.top + (rect.height / 2) - (popover.offsetHeight / 2);
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        if (left + popover.offsetWidth > viewportWidth - 12) {
            left = rect.left - popover.offsetWidth - gap;
        }
        if (left < 12) left = 12;
        if (top < 12) top = 12;
        if (top + popover.offsetHeight > viewportHeight - 12) {
            top = viewportHeight - popover.offsetHeight - 12;
        }

        popover.style.left = left + 'px';
        popover.style.top = top + 'px';

        popover.querySelector('.task-detail-popover-close').addEventListener('click', hideTaskDetailPopover);
        document.addEventListener('click', handlePopoverOutsideClick);
        document.addEventListener('keydown', handlePopoverEscape);
    }

    function escapeHtml(str) {
        if (str == null) return '';
        const s = String(str);
        const div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    function handlePopoverOutsideClick(e) {
        if (taskDetailPopover && !taskDetailPopover.contains(e.target) &&
            !e.target.closest('.tree-task')) {
            hideTaskDetailPopover();
        }
    }

    function handlePopoverEscape(e) {
        if (e.key === 'Escape') hideTaskDetailPopover();
    }

    function hideTaskDetailPopover() {
        if (taskDetailPopover) {
            taskDetailPopover.remove();
            taskDetailPopover = null;
            taskDetailPopoverAnchor = null;
            document.removeEventListener('click', handlePopoverOutsideClick);
            document.removeEventListener('keydown', handlePopoverEscape);
        }
    }

    function initTaskNodeClickHandlers() {
        document.addEventListener('click', (e) => {
            const node = e.target.closest('.tree-task');
            if (!node) return;
            const dataStr = node.getAttribute('data-task-data');
            if (!dataStr) return;
            try {
                const task = JSON.parse(dataStr);
                showTaskDetailPopover(task, node);
                e.stopPropagation();
            } catch (_) {}
        });
    }

    window.TaskTree = {
        renderTree,
        clearPlannerTree,
        appendPlannerTaskNode,
        renderPlannerTree,
        renderMonitorTasksTree,
        redrawPlannerConnectionLines,
        drawConnectionLines,
        initTaskNodeClickHandlers,
        showTaskDetailPopover,
        hideTaskDetailPopover,
        get plannerTasks() { return plannerTasks; }
    };
})();
