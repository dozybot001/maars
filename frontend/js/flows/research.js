/**
 * MAARS Research flow - Create page + Research detail page (auto pipeline).
 */
(function () {
    'use strict';

    const cfg = window.MAARS?.config;
    const api = window.MAARS?.api;
    const executeUtils = window.MAARS?.researchExecuteUtils || {};
    const navUtils = window.MAARS?.researchNavUtils || {};
    if (!cfg || !api) return;

    const homeView = document.getElementById('homeView');
    const researchView = document.getElementById('researchView');
    const promptInput = document.getElementById('researchPromptInput');
    const createBtn = document.getElementById('createResearchBtn');

    const breadcrumbEl = document.getElementById('researchBreadcrumb');
    const titleEl = document.getElementById('researchTitle');

    const stageButtons = {
        refine: document.getElementById('stageBtnRefine'),
        plan: document.getElementById('stageBtnPlan'),
        execute: document.getElementById('stageBtnExecute'),
        paper: document.getElementById('stageBtnPaper'),
    };
    const stageMetaEls = {
        refine: document.getElementById('stageMetaRefine'),
        plan: document.getElementById('stageMetaPlan'),
        execute: document.getElementById('stageMetaExecute'),
        paper: document.getElementById('stageMetaPaper'),
    };
    const stageActionBtns = {
        refine: {
            run: document.getElementById('stageRunRefine'),
            resume: document.getElementById('stageResumeRefine'),
            retry: document.getElementById('stageRetryRefine'),
            stop: document.getElementById('stageStopRefine'),
        },
        plan: {
            run: document.getElementById('stageRunPlan'),
            resume: document.getElementById('stageResumePlan'),
            retry: document.getElementById('stageRetryPlan'),
            stop: document.getElementById('stageStopPlan'),
        },
        execute: {
            run: document.getElementById('stageRunExecute'),
            resume: document.getElementById('stageResumeExecute'),
            retry: document.getElementById('stageRetryExecute'),
            stop: document.getElementById('stageStopExecute'),
        },
        paper: {
            run: document.getElementById('stageRunPaper'),
            resume: document.getElementById('stageResumePaper'),
            retry: document.getElementById('stageRetryPaper'),
            stop: document.getElementById('stageStopPaper'),
        },
    };

    const panelRefine = document.getElementById('researchPanelRefine');
    const panelWorkbench = document.getElementById('researchDetailHost');
    const panelPaper = document.getElementById('researchPanelPaper');
    const executeSplitterEl = document.getElementById('researchExecuteSplitter');

    const refineRefsEl = document.getElementById('researchRefineReferences');
    const refineLogicEl = document.getElementById('researchRefineLogic');
    const paperBodyEl = document.getElementById('researchPaperBody');

    const executeStreamEl = document.getElementById('researchExecuteStream');
    const executeStreamBodyEl = document.getElementById('researchExecuteStreamBody');
    const executeToggleAllBtnEl = document.getElementById('researchExecuteToggleAllBtn');
    const executeJumpLatestBtnEl = document.getElementById('researchExecuteJumpLatestBtn');
    const executeRuntimeBadgeEl = document.getElementById('researchExecutionRuntimeBadge');
    const executeRuntimeMetaEl = document.getElementById('researchExecutionRuntimeMeta');

    const treeTabsHost = panelWorkbench?.querySelector?.('.tree-view-tabs');
    const treeTabButtons = treeTabsHost ? Array.from(treeTabsHost.querySelectorAll('.tree-view-tab')) : [];
    const treePanels = panelWorkbench ? Array.from(panelWorkbench.querySelectorAll('.tree-view-panel')) : [];

    let currentResearchId = null;
    let activeStage = 'refine';
    let stageData = {
        papers: [],
        refined: '',
        refineThinking: '',
        paper: '',
    };
    let executionGraphPayload = {
        treeData: [],
        layout: null,
    };
    const executionGraphHelpers = window.MAARS?.createResearchExecutionGraphHelpers?.({
        getPayload: () => executionGraphPayload,
        setPayload: (payload) => { executionGraphPayload = payload || { treeData: [], layout: null }; },
        upsertTaskMeta: (task) => _upsertTaskMeta(task),
        getStatuses: () => executeState.statuses,
        getActiveStage: () => activeStage,
    });

    let executeState = {
        order: [],
        statuses: new Map(),
        latestStepBByTask: new Map(),
        recentOutputsByTask: new Map(),
        taskMetaById: new Map(),
        messages: [],
        taskExpandedById: new Map(),
        currentAttemptByTask: new Map(),
        attemptExpandedById: new Map(),
    };
    let executionRuntimeStatus = null;
    let runtimeStatusRequestId = 0;
    let executeElapsedTimerId = 0;
    let executeAutoFollow = true;
    let executeSplitRatio = 80;
    const EXECUTE_TIMELINE_MAX_MESSAGES = 2000;
    let currentStageState = {
        refine: { started: false },
        plan: { started: false },
        execute: { started: false },
        paper: { started: false },
    };
    let stageStatusDetails = {
        refine: { status: 'idle', message: 'idle' },
        plan: { status: 'idle', message: 'idle' },
        execute: { status: 'idle', message: 'idle' },
        paper: { status: 'idle', message: 'idle' },
    };

    function setStageStarted(stage, started) {
        if (!currentStageState[stage]) return;
        currentStageState[stage].started = !!started;
        renderStageButtons();
    }

    function _isStagePrerequisiteCompleted(stage) {
        const order = ['refine', 'plan', 'execute', 'paper'];
        const idx = order.indexOf(String(stage || '').trim());
        if (idx <= 0) return true;
        for (let i = 0; i < idx; i += 1) {
            const prev = order[i];
            const prevStatus = String(stageStatusDetails?.[prev]?.status || 'idle').trim() || 'idle';
            if (prevStatus !== 'completed') return false;
        }
        return true;
    }

    function renderStageButtons(activeStage) {
        const order = ['refine', 'plan', 'execute', 'paper'];
        const current = String(activeStage || '').trim() || String(window.MAARS?.researchCurrentStage || '') || 'refine';
        const currentRank = order.indexOf(current);

        Object.entries(stageButtons).forEach(([stage, btn]) => {
            if (!btn) return;
            const started = !!currentStageState?.[stage]?.started;
            const stageRank = order.indexOf(stage);
            btn.disabled = !started;
            btn.setAttribute('aria-disabled', started ? 'false' : 'true');
            btn.classList.toggle('is-started', started);
            btn.classList.toggle('is-active', stage === current);
            btn.classList.toggle('is-completed', started && currentRank >= 0 && stageRank >= 0 && stageRank < currentRank);
        });
        renderStageStatusDetails();
    }

    function renderStageStatusDetails() {
        const runningStage = Object.entries(stageStatusDetails).find(([, info]) => String(info?.status || '') === 'running')?.[0] || '';
        Object.entries(stageMetaEls).forEach(([stage, metaEl]) => {
            if (!metaEl) return;
            const info = stageStatusDetails[stage] || { status: 'idle', message: 'idle' };
            const status = String(info.status || 'idle').trim() || 'idle';
            const message = String(info.message || status).trim() || status;
            metaEl.textContent = `${status} · ${message}`;
        });

        Object.entries(stageActionBtns).forEach(([stage, actions]) => {
            const info = stageStatusDetails[stage] || { status: 'idle' };
            const status = String(info.status || 'idle').trim() || 'idle';
            const stageStarted = !!currentStageState?.[stage]?.started;
            const isRunningSelf = status === 'running';
            // Also enable Stop when the execute runner is still active (runner may have outlived its pipeline task)
            const executeRunnerActive = stage === 'execute' && !!(executionRuntimeStatus?.running);
            const hasOtherRunning = !!runningStage && runningStage !== stage;
            const blocked = hasOtherRunning;
            const prereqOk = _isStagePrerequisiteCompleted(stage);
            if (actions?.run) actions.run.disabled = blocked || !prereqOk;
            if (actions?.resume) actions.resume.disabled = blocked || !prereqOk || !(status === 'stopped' || status === 'failed');
            if (actions?.retry) actions.retry.disabled = blocked || !prereqOk || !(stageStarted || status === 'failed' || status === 'stopped');
            if (actions?.stop) actions.stop.disabled = blocked || !(isRunningSelf || executeRunnerActive);
        });
    }

    function _mdToHtml(md) {
        const src = (md == null ? '' : String(md));
        let html = '';
        try {
            html = (typeof marked !== 'undefined') ? marked.parse(src) : src;
        } catch (_) {
            html = src;
        }
        try {
            if (typeof DOMPurify !== 'undefined') html = DOMPurify.sanitize(html);
        } catch (_) { }
        return html;
    }

    function _renderRefinePanel() {
        if (refineLogicEl) {
            const refined = (stageData.refined || '').trim();
            const thinking = (stageData.refineThinking || '').trim();
            refineLogicEl.innerHTML = refined
                ? _mdToHtml(refined)
                : (thinking ? _mdToHtml(thinking) : '—');
        }
        if (refineRefsEl) {
            const papers = Array.isArray(stageData.papers) ? stageData.papers : [];
            if (!papers.length) {
                refineRefsEl.textContent = '—';
            } else {
                const md = papers.map((p, i) => {
                    const title = (p?.title || '').replace(/\s+/g, ' ').trim();
                    const url = p?.url || '';
                    const head = url ? `${i + 1}. [${title || 'Untitled'}](${url})` : `${i + 1}. ${title || 'Untitled'}`;
                    return `${head}`;
                }).join('\n');
                refineRefsEl.innerHTML = _mdToHtml(md);
            }
        }
    }

    function _renderPaperPanel() {
        if (!paperBodyEl) return;
        const content = (stageData.paper || '').trim();
        paperBodyEl.innerHTML = content ? _mdToHtml(content) : '—';
    }

    function _setPanelActive(panelEl, on) {
        if (!panelEl) return;
        panelEl.classList.toggle('is-active', !!on);
    }

    function _loadExecuteSplitRatio() {
        try {
            const raw = localStorage.getItem('maars-execute-split-ratio');
            const val = Number(raw);
            if (Number.isFinite(val)) executeSplitRatio = Math.max(35, Math.min(90, val));
        } catch (_) { }
    }

    function _saveExecuteSplitRatio() {
        try {
            localStorage.setItem('maars-execute-split-ratio', String(executeSplitRatio));
        } catch (_) { }
    }

    function _applyExecuteSplitRatio() {
        if (!panelWorkbench) return;
        panelWorkbench.style.setProperty('--execute-left-ratio', String(executeSplitRatio));
    }

    function setTreeView(view) {
        const v = String(view || '').trim();
        treeTabButtons.forEach((btn) => {
            const isActive = (btn.getAttribute('data-view') || '') === v;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });
        treePanels.forEach((p) => {
            const isActive = (p.getAttribute('data-view-panel') || '') === v;
            p.classList.toggle('active', isActive);
        });
    }

    function setActiveStage(stage) {
        const s = String(stage || '').trim();
        activeStage = s;
        window.MAARS = window.MAARS || {};
        window.MAARS.researchCurrentStage = s;
        renderStageButtons(s);
        _syncExecuteElapsedTicker();

        // Panels
        _setPanelActive(panelRefine, s === 'refine');
        _setPanelActive(panelWorkbench, s === 'plan' || s === 'execute');
        _setPanelActive(panelPaper, s === 'paper');

        // Workbench modes
        if (panelWorkbench) {
            panelWorkbench.classList.toggle('research-workbench--plan', s === 'plan');
            panelWorkbench.classList.toggle('research-workbench--execute', s === 'execute');
        }

        if (executeStreamEl) {
            executeStreamEl.hidden = !(s === 'execute');
        }

        if (s === 'plan') {
            setTreeView('decomposition');
        } else if (s === 'execute') {
            _applyExecuteSplitRatio();
            setTreeView('execution');
            scheduleExecutionGraphRender({ force: true, delays: [0, 100, 320, 700] });
            renderExecuteStream();
            refreshExecutionRuntimeStatus();
        }

        if (s === 'refine') _renderRefinePanel();
        if (s === 'paper') _renderPaperPanel();
    }

    function _getTaskDataFromNode(node) {
        if (!node) return null;
        const raw = node.getAttribute('data-task-data');
        if (!raw) return null;
        try {
            const parsed = JSON.parse(raw);
            if (Array.isArray(parsed)) return parsed[0] || null;
            return parsed;
        } catch (_) {
            return null;
        }
    }

    function _stringifyOutput(val) {
        if (typeof executeUtils.stringifyOutput === 'function') {
            return executeUtils.stringifyOutput(val);
        }
        return String(val || '');
    }

    function _ensureTaskInOrder(taskId) {
        const id = String(taskId || '').trim();
        if (!id) return '';
        if (!executeState.order.includes(id)) executeState.order.push(id);
        if (!executeState.taskExpandedById.has(id)) executeState.taskExpandedById.set(id, true);
        return id;
    }

    function _updateExecuteToggleAllButton() {
        if (!executeToggleAllBtnEl) return;
        const taskIds = executeState.order || [];
        if (!taskIds.length) {
            executeToggleAllBtnEl.textContent = 'Collapse All';
            return;
        }
        const allCollapsed = taskIds.every((taskId) => executeState.taskExpandedById.get(taskId) === false);
        executeToggleAllBtnEl.textContent = allCollapsed ? 'Expand All' : 'Collapse All';
    }

    function _setAllExecuteTaskExpanded(expanded) {
        (executeState.order || []).forEach((taskId) => {
            executeState.taskExpandedById.set(taskId, !!expanded);
        });
        _updateExecuteToggleAllButton();
        if (activeStage === 'execute') renderExecuteStream();
    }

    function _upsertTaskMeta(task) {
        const id = String(task?.task_id || '').trim();
        if (!id) return;
        const current = executeState.taskMetaById.get(id) || {};
        const outputFormat = String(task?.output?.format || task?.outputFormat || current.outputFormat || '').trim();
        executeState.taskMetaById.set(id, {
            ...current,
            task_id: id,
            title: String(task?.title || current.title || '').trim(),
            description: String(task?.description || task?.objective || current.description || '').trim(),
            status: String(task?.status || current.status || '').trim(),
            outputFormat,
        });
        _ensureTaskInOrder(id);
    }

    function _getTaskMetaById(taskId) {
        const id = String(taskId || '').trim();
        if (!id) return null;
        return executeState.taskMetaById.get(id) || null;
    }

    function _pushRecentOutput(taskId, outputText) {
        const id = String(taskId || '').trim();
        if (!id) return;
        const text = String(outputText || '').trim();
        if (!text) return;
        const list = executeState.recentOutputsByTask.get(id) || [];
        list.push(text);
        while (list.length > 8) list.shift();
        executeState.recentOutputsByTask.set(id, list);
    }

    function _statusLabel(status) {
        if (typeof executeUtils.statusLabel === 'function') {
            return executeUtils.statusLabel(status);
        }
        return String(status || 'undone');
    }

    function _statusTone(status) {
        if (typeof executeUtils.statusTone === 'function') {
            return executeUtils.statusTone(status);
        }
        return 'pending';
    }

    function _extractValidationDirectReason(reportText) {
        if (typeof executeUtils.extractValidationDirectReason === 'function') {
            return executeUtils.extractValidationDirectReason(reportText);
        }
        return 'Validation gate failed.';
    }

    function _buildValidationSummaryBody(taskId, detail, meta, options = {}) {
        if (typeof executeUtils.buildValidationSummaryBody === 'function') {
            return executeUtils.buildValidationSummaryBody({
                taskId,
                detail,
                meta,
                statusLabel: options.statusLabel,
                latestStepBByTask: executeState.latestStepBByTask,
            });
        }
        return 'Validation report unavailable.';
    }

    function renderExecutionRuntimeStatus(status) {
        executionRuntimeStatus = status && typeof status === 'object' ? status : null;
        if (!executeRuntimeBadgeEl || !executeRuntimeMetaEl) return;

        const viewModel = (typeof executeUtils.buildRuntimeStatusViewModel === 'function')
            ? executeUtils.buildRuntimeStatusViewModel(executionRuntimeStatus)
            : {
                badgeText: 'Docker: checking...',
                tone: 'is-warn',
                shortMetaText: '',
                detailMetaText: '',
            };

        executeRuntimeBadgeEl.textContent = viewModel.badgeText;
        executeRuntimeBadgeEl.classList.remove('is-ok', 'is-warn', 'is-error');
        executeRuntimeBadgeEl.classList.add(viewModel.tone);
        executeRuntimeMetaEl.textContent = viewModel.shortMetaText;
        executeRuntimeMetaEl.title = viewModel.detailMetaText;
    }

    async function refreshExecutionRuntimeStatus(explicitIds) {
        if (!executeRuntimeBadgeEl) return null;
        const requestId = ++runtimeStatusRequestId;
        if (!executionRuntimeStatus) {
            renderExecutionRuntimeStatus({ enabled: true, available: true, connected: false });
        }
        try {
            const ids = explicitIds && (explicitIds.ideaId || explicitIds.planId)
                ? explicitIds
                : await cfg.resolvePlanIds();
            const status = await api.getExecutionRuntimeStatus?.(ids?.ideaId || '', ids?.planId || '');
            if (requestId !== runtimeStatusRequestId) return null;
            renderExecutionRuntimeStatus(status || {});
            return status || null;
        } catch (error) {
            if (requestId !== runtimeStatusRequestId) return null;
            renderExecutionRuntimeStatus({
                enabled: true,
                available: true,
                connected: false,
                error: error?.message || 'Failed to load Docker runtime status',
            });
            return null;
        }
    }

    function _appendExecuteMessage(message) {
        if (!message || !message.taskId && message.kind !== 'system') return;
        const taskId = String(message.taskId || '').trim();
        let attempt = Number(message.attempt);
        if (taskId) {
            if (!Number.isFinite(attempt) || attempt < 1) {
                attempt = Number(executeState.currentAttemptByTask.get(taskId));
            }
            if (!Number.isFinite(attempt) || attempt < 1) attempt = 1;
            executeState.currentAttemptByTask.set(taskId, attempt);
            if (!executeState.attemptExpandedById.has(`${taskId}:${attempt}`)) {
                executeState.attemptExpandedById.set(`${taskId}:${attempt}`, true);
            }
        }
        const dedupeKey = String(message.dedupeKey || '').trim();
        if (dedupeKey) {
            const exists = executeState.messages.some((m) => m.dedupeKey === dedupeKey);
            if (exists) return;
        }
        executeState.messages.push({
            id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            at: Date.now(),
            ...message,
            startedAt: Number(message?.startedAt) || Date.now(),
            attempt: taskId ? attempt : undefined,
        });
        if (executeState.messages.length > EXECUTE_TIMELINE_MAX_MESSAGES) {
            executeState.messages = executeState.messages.slice(-EXECUTE_TIMELINE_MAX_MESSAGES);
        }
    }

    function _isExecuteStreamNearBottom() {
        if (!executeStreamBodyEl) return true;
        return (executeStreamBodyEl.scrollHeight - executeStreamBodyEl.scrollTop - executeStreamBodyEl.clientHeight) < 48;
    }

    function _scrollExecuteStreamToLatest() {
        if (!executeStreamBodyEl) return;
        executeStreamBodyEl.scrollTop = executeStreamBodyEl.scrollHeight;
    }

    function _updateExecuteJumpLatestButton() {
        if (!executeJumpLatestBtnEl || !executeStreamBodyEl) return;
        const hasMessages = (executeState.messages || []).length > 0;
        const shouldShow = hasMessages && !executeAutoFollow && !_isExecuteStreamNearBottom();
        executeJumpLatestBtnEl.hidden = !shouldShow;
    }

    function _formatElapsedDuration(ms) {
        if (typeof executeUtils.formatElapsedDuration === 'function') {
            return executeUtils.formatElapsedDuration(ms);
        }
        return '0s';
    }

    function _hasActiveExecuteBubble() {
        return executeState.messages.some((msg) => {
            if (msg.kind !== 'assistant') return false;
            const taskId = String(msg.taskId || '').trim();
            if (!taskId) return false;
            const status = String(executeState.statuses.get(taskId) || '').trim();
            return status === 'doing' || status === 'validating';
        });
    }

    function _syncExecuteElapsedTicker() {
        const shouldRun = activeStage === 'execute' && _hasActiveExecuteBubble();
        if (!shouldRun) {
            if (executeElapsedTimerId) {
                window.clearInterval(executeElapsedTimerId);
                executeElapsedTimerId = 0;
            }
            return;
        }
        if (executeElapsedTimerId) return;
        executeElapsedTimerId = window.setInterval(() => {
            if (activeStage !== 'execute' || !_hasActiveExecuteBubble()) {
                _syncExecuteElapsedTicker();
                return;
            }
            renderExecuteStream();
        }, 1000);
    }

    function _getAttemptKey(taskId, attempt) {
        if (typeof executeUtils.getAttemptKey === 'function') {
            return executeUtils.getAttemptKey(taskId, attempt);
        }
        return `${String(taskId || '').trim()}:${Number(attempt) || 1}`;
    }

    function _getCurrentAttempt(taskId) {
        const id = String(taskId || '').trim();
        if (!id) return 1;
        const current = Number(executeState.currentAttemptByTask.get(id));
        return Number.isFinite(current) && current > 0 ? current : 1;
    }

    function _setCurrentAttempt(taskId, attempt) {
        const id = String(taskId || '').trim();
        const n = Number(attempt);
        if (!id || !Number.isFinite(n) || n < 1) return;
        const current = _getCurrentAttempt(id);
        const next = Math.max(current, n);
        executeState.currentAttemptByTask.set(id, next);
        const key = _getAttemptKey(id, next);
        if (!executeState.attemptExpandedById.has(key)) {
            executeState.attemptExpandedById.set(key, true);
        }
    }

    function _getAttemptStatus(taskId, attempt, msgs, fallbackStatus) {
        if (typeof executeUtils.getAttemptStatus === 'function') {
            return executeUtils.getAttemptStatus({
                taskId,
                attempt,
                msgs,
                fallbackStatus,
                currentAttempt: _getCurrentAttempt(taskId),
            });
        }
        return String(fallbackStatus || 'doing').trim() || 'doing';
    }

    function _getAttemptSummary(msgs) {
        if (typeof executeUtils.getAttemptSummary === 'function') {
            return executeUtils.getAttemptSummary(msgs);
        }
        return '';
    }

    function _replayPersistedStepEvents(stepEvents) {
        if (typeof executeUtils.replayPersistedStepEvents === 'function') {
            executeUtils.replayPersistedStepEvents(stepEvents);
        }
    }

    function scheduleExecutionGraphRender(options = {}) {
        executionGraphHelpers?.schedule?.(options);
    }

    function ensureExecutionGraphRendered(force = false, options = {}) {
        executionGraphHelpers?.ensure?.(force, options);
    }

    function invalidateExecutionGraphRender() {
        executionGraphHelpers?.invalidate?.();
    }

    function _upsertExecuteThinkingMessage(taskId, operation, body, scheduleInfo, attemptHint) {
        const id = String(taskId || '').trim();
        if (!id) return;
        const op = String(operation || 'Execute').trim() || 'Execute';
        const text = String(body || '').trim();
        if (!text) return;
        const hintedAttempt = Number(attemptHint || scheduleInfo?.attempt) || 0;
        const currentAttempt = Math.max(_getCurrentAttempt(id), hintedAttempt, 1);

        const turn = Number(scheduleInfo?.turn);
        const maxTurns = Number(scheduleInfo?.max_turns);
        const toolName = String(scheduleInfo?.tool_name || '').trim();
        const tokenUsage = scheduleInfo?.token_usage || {};
        const totalTokens = Number(tokenUsage?.total);
        const deltaTokens = Number(tokenUsage?.deltaTotal);
        const inputTokens = Number(tokenUsage?.input);
        const outputTokens = Number(tokenUsage?.output);
        const contextTokens = Number(tokenUsage?.contextInputEst);

        let title = `${id} · ${op}`;
        if (toolName) title += ` · ${toolName}`;

        let tokenMetaText = '';
        if (Number.isFinite(inputTokens) && Number.isFinite(outputTokens) && (inputTokens > 0 || outputTokens > 0)) {
            const tokenBits = [`in ${inputTokens || 0}`, `out ${outputTokens || 0}`];
            if (Number.isFinite(deltaTokens) && deltaTokens > 0) tokenBits.push(`Δ ${deltaTokens}`);
            if (Number.isFinite(totalTokens) && totalTokens > 0) tokenBits.push(`total ${totalTokens}`);
            tokenMetaText = tokenBits.join(' · ');
        } else if (Number.isFinite(contextTokens) && contextTokens > 0) {
            tokenMetaText = `ctx ~${contextTokens}`;
        }

        const bodyText = Number.isFinite(turn) && Number.isFinite(maxTurns)
            ? `[${turn}/${maxTurns}] ${text}`
            : text;
        const dedupeKey = Number.isFinite(turn)
            ? `thinking:${id}:${currentAttempt}:${op}:${toolName}:${turn}:${bodyText.slice(0, 240)}`
            : '';

        const last = executeState.messages[executeState.messages.length - 1];
        if (
            last
            && last.taskId === id
            && Number(last.attempt || 1) === currentAttempt
            && last.kind === 'assistant'
            && String(last.title || '') === title
            && String(last.tokenMetaText || '') === tokenMetaText
        ) {
            const previous = String(last.body || '').trim();
            if (previous && previous !== bodyText) {
                const merged = `${previous}\n${bodyText}`;
                // Keep one continuous bubble but prevent unbounded growth in long streams.
                last.body = merged.length > 12000 ? merged.slice(-12000) : merged;
            } else if (!previous) {
                last.body = bodyText;
            } else {
                const nextRepeat = Number(last.repeatCount || 1) + 1;
                last.repeatCount = nextRepeat;
            }
            last.at = Date.now();
            return;
        }

        _appendExecuteMessage({
            taskId: id,
            kind: 'assistant',
            title,
            body: bodyText,
            tokenMetaText,
            status: executeState.statuses.get(id) || 'doing',
            attempt: currentAttempt,
            dedupeKey,
            repeatCount: 1,
            startedAt: Date.now(),
        });
    }

    function _seedExecutionState(treeData, execution, outputs, options = {}) {
        executeState.order = [];
        executeState.statuses = new Map();
        executeState.latestStepBByTask = new Map();
        executeState.recentOutputsByTask = new Map();
        executeState.taskMetaById = new Map();
        executeState.messages = [];
        executeState.taskExpandedById = new Map();
        executeState.currentAttemptByTask = new Map();
        executeState.attemptExpandedById = new Map();

        const treeTasks = Array.isArray(treeData) ? treeData : [];
        const execTasks = Array.isArray(execution?.tasks) ? execution.tasks : [];
        treeTasks.forEach(_upsertTaskMeta);
        execTasks.forEach((task) => {
            _upsertTaskMeta(task);
            if (task?.status) executeState.statuses.set(task.task_id, String(task.status));
            _setCurrentAttempt(task.task_id, 1);
        });

        const skipOutputSeed = options?.skipOutputSeed === true;
        const outputMap = outputs && typeof outputs === 'object' ? outputs : {};
        if (!skipOutputSeed) {
            Object.entries(outputMap).forEach(([taskId, output]) => {
                const text = _stringifyOutput(output).trim();
                if (!text) return;
                _ensureTaskInOrder(taskId);
                _pushRecentOutput(taskId, text);
            });
        }

        _appendExecuteMessage({
            kind: 'system',
            title: 'Execution timeline ready',
            body: execTasks.length ? `Loaded ${execTasks.length} execution steps.` : 'Waiting for execution to start.',
            dedupeKey: `seed:${currentResearchId || ''}`,
        });

        // Only append existing outputs, not task descriptions
        // Task descriptions will be shown when task-started events arrive
        executeState.order.forEach((taskId) => {
            const meta = _getTaskMetaById(taskId) || {};
            const status = executeState.statuses.get(taskId) || meta.status || 'undone';

            if (!skipOutputSeed) {
                const outputsForTask = executeState.recentOutputsByTask.get(taskId) || [];
                if (outputsForTask.length) {
                    _appendExecuteMessage({
                        taskId,
                        kind: status === 'execution-failed' || status === 'validation-failed' ? 'error' : 'output',
                        title: meta.title || taskId,
                        body: outputsForTask[outputsForTask.length - 1],
                        status,
                        dedupeKey: `seed-output:${taskId}`,
                    });
                }
            }
        });
    }

    function _resetExecuteTimelineForNewRun() {
        executeState.messages = [];
        executeState.latestStepBByTask = new Map();
        executeState.recentOutputsByTask = new Map();
        executeState.currentAttemptByTask = new Map();
        executeState.attemptExpandedById = new Map();
        executeAutoFollow = true;
        executeState.order.forEach((taskId) => {
            _setCurrentAttempt(taskId, 1);
        });
        _updateExecuteJumpLatestButton();
        _syncExecuteElapsedTicker();
    }

    function renderExecuteStream() {
        if (!executeStreamBodyEl) return;
        const wasNearBottom = _isExecuteStreamNearBottom();
        const messages = Array.isArray(executeState.messages) ? executeState.messages : [];

        executeStreamBodyEl.textContent = '';

        if (!messages.length) {
            const empty = document.createElement('div');
            empty.className = 'research-execute-empty';
            empty.textContent = '执行开始后，这里会像对话流一样持续展示每一步的状态与产出。';
            executeStreamBodyEl.appendChild(empty);
            return;
        }

        // Group messages by task
        const taskMessages = new Map();
        messages.forEach((msg) => {
            const taskId = msg.taskId || 'system';
            if (!taskMessages.has(taskId)) {
                taskMessages.set(taskId, []);
            }
            taskMessages.get(taskId).push(msg);
        });

        // Collect rendering blocks: one for each task, and one for each global system message
        const renderBlocks = [];

        // 1. Task cards
        executeState.order.forEach((taskId) => {
            if (!taskMessages.has(taskId)) return;
            const msgs = taskMessages.get(taskId);
            if (!msgs.length) return;
            renderBlocks.push({
                type: 'task',
                taskId: taskId,
                msgs: msgs,
                firstIndex: messages.indexOf(msgs[0])
            });
        });

        // 2. Global system messages (no taskId)
        const systemMsgs = messages.filter((m) => !m.taskId);
        systemMsgs.forEach((msg) => {
            renderBlocks.push({
                type: 'system',
                msg: msg,
                firstIndex: messages.indexOf(msg)
            });
        });

        // Sort blocks by their appearance order in the global messages array
        renderBlocks.sort((a, b) => a.firstIndex - b.firstIndex);

        // Render each block in chronological order
        renderBlocks.forEach((block) => {
            if (block.type === 'task') {
                const taskId = block.taskId;
                const msgs = block.msgs;
                const meta = _getTaskMetaById(taskId) || {};
                const status = executeState.statuses.get(taskId) || meta.status || 'undone';
                const statusTone = _statusTone(status);
                const attemptGroups = new Map();
                msgs.forEach((msg) => {
                    const attempt = Number(msg.attempt) || 1;
                    if (!attemptGroups.has(attempt)) attemptGroups.set(attempt, []);
                    attemptGroups.get(attempt).push(msg);
                });
                const attemptNumbers = Array.from(attemptGroups.keys()).sort((a, b) => a - b);
                const latestAttempt = attemptNumbers.length ? attemptNumbers[attemptNumbers.length - 1] : _getCurrentAttempt(taskId);

                // Task card container
                const cardEl = document.createElement('div');
                cardEl.className = `research-execute-task-card research-execute-task-card--${statusTone}`;
                cardEl.setAttribute('data-task-id', taskId);

                // Task header (clickable for expand/collapse)
                const headerEl = document.createElement('div');
                headerEl.className = 'research-execute-task-header';

                // Expand/Collapse toggle
                const toggleEl = document.createElement('button');
                toggleEl.className = 'research-execute-task-toggle';
                toggleEl.innerHTML = '▶';
                toggleEl.setAttribute('aria-label', 'Toggle task details');
                toggleEl.type = 'button';
                headerEl.appendChild(toggleEl);

                // Status indicator
                const dotEl = document.createElement('span');
                dotEl.className = `research-execute-status-dot is-${statusTone}`;
                headerEl.appendChild(dotEl);

                // Task title and description (main content)
                const titleWrapEl = document.createElement('div');
                titleWrapEl.style.flex = '1 1 auto';
                titleWrapEl.style.minWidth = '0';
                titleWrapEl.style.display = 'flex';
                titleWrapEl.style.flexDirection = 'column';
                titleWrapEl.style.gap = '4px';

                const titleEl = document.createElement('div');
                titleEl.className = 'research-execute-task-title';
                titleEl.textContent = `${meta.title || taskId} · Attempt ${latestAttempt}`;
                titleWrapEl.appendChild(titleEl);

                // Current operation (thinking message)
                const thinkingMsg = [...msgs].reverse().find((m) => Number(m.attempt) === latestAttempt && m.kind === 'assistant');
                if (thinkingMsg) {
                    const opEl = document.createElement('div');
                    opEl.className = 'research-execute-task-operation';
                    const opText = String(thinkingMsg.title || '').split('·').slice(1).join('·').trim();
                    opEl.textContent = opText ? `— ${opText}` : '';
                    titleWrapEl.appendChild(opEl);
                }

                headerEl.appendChild(titleWrapEl);

                // Status label
                const labelEl = document.createElement('span');
                labelEl.className = 'research-execute-task-status-label';
                labelEl.textContent = _statusLabel(status);
                headerEl.appendChild(labelEl);

                cardEl.appendChild(headerEl);

                // Task details (collapsible)
                const detailsEl = document.createElement('div');
                detailsEl.className = 'research-execute-task-details';
                let isExpanded = executeState.taskExpandedById.get(taskId);
                if (typeof isExpanded !== 'boolean') isExpanded = true;
                executeState.taskExpandedById.set(taskId, isExpanded);

                const contentEl = document.createElement('div');
                contentEl.className = 'research-execute-task-content';

                attemptNumbers.forEach((attemptNumber) => {
                    const attemptMsgs = attemptGroups.get(attemptNumber) || [];
                    const attemptKey = _getAttemptKey(taskId, attemptNumber);
                    let attemptExpanded = executeState.attemptExpandedById.get(attemptKey);
                    if (typeof attemptExpanded !== 'boolean') {
                        attemptExpanded = attemptNumber >= latestAttempt;
                        executeState.attemptExpandedById.set(attemptKey, attemptExpanded);
                    }
                    const attemptStatus = _getAttemptStatus(taskId, attemptNumber, attemptMsgs, status);
                    const attemptTone = _statusTone(attemptStatus);

                    const attemptEl = document.createElement('div');
                    attemptEl.className = `research-execute-attempt research-execute-attempt--${attemptTone}`;

                    const attemptHeaderEl = document.createElement('div');
                    attemptHeaderEl.className = 'research-execute-attempt-header';

                    const attemptToggleEl = document.createElement('button');
                    attemptToggleEl.className = 'research-execute-attempt-toggle';
                    attemptToggleEl.innerHTML = '▶';
                    attemptToggleEl.setAttribute('aria-label', 'Toggle attempt details');
                    attemptToggleEl.type = 'button';
                    attemptHeaderEl.appendChild(attemptToggleEl);

                    const attemptTitleEl = document.createElement('div');
                    attemptTitleEl.className = 'research-execute-attempt-title';
                    attemptTitleEl.textContent = `Attempt ${attemptNumber}${attemptNumber === latestAttempt ? ' · Current' : ''}`;
                    attemptHeaderEl.appendChild(attemptTitleEl);

                    const attemptLabelEl = document.createElement('span');
                    attemptLabelEl.className = 'research-execute-attempt-status-label';
                    attemptLabelEl.textContent = _statusLabel(attemptStatus);
                    attemptHeaderEl.appendChild(attemptLabelEl);

                    const attemptSummary = _getAttemptSummary(attemptMsgs);
                    if (attemptSummary) {
                        const attemptSummaryEl = document.createElement('div');
                        attemptSummaryEl.className = 'research-execute-attempt-summary';
                        attemptSummaryEl.textContent = attemptSummary;
                        attemptHeaderEl.appendChild(attemptSummaryEl);
                    }

                    const attemptBodyEl = document.createElement('div');
                    attemptBodyEl.className = 'research-execute-attempt-body';
                    const activeAssistantMsg = (attemptNumber === latestAttempt && (attemptStatus === 'doing' || attemptStatus === 'validating'))
                        ? [...attemptMsgs].reverse().find((m) => m.kind === 'assistant') || null
                        : null;

                    attemptMsgs.forEach((msg) => {
                        const msgEl = document.createElement('div');
                        msgEl.className = `research-execute-message research-execute-message--${msg.kind || 'assistant'}`;

                        const metaEl = document.createElement('div');
                        metaEl.className = 'research-execute-message-meta';
                        if (msg.kind && msg.kind !== 'system') {
                            const kindEl = document.createElement('span');
                            kindEl.className = 'research-execute-message-kind';
                            kindEl.textContent = msg.kind === 'output'
                                ? 'Output'
                                : msg.kind === 'error'
                                    ? 'Error'
                                    : msg.kind === 'system'
                                        ? 'System'
                                        : 'Think';
                            metaEl.appendChild(kindEl);
                        }
                        msgEl.appendChild(metaEl);

                        const bubbleEl = document.createElement('div');
                        bubbleEl.className = 'research-execute-message-bubble';

                        if (msg.title) {
                            const messageTitleEl = document.createElement('div');
                            messageTitleEl.className = 'research-execute-message-title';
                            const repeatCount = Number(msg.repeatCount || 1);
                            messageTitleEl.textContent = repeatCount > 1 ? `${msg.title} ×${repeatCount}` : msg.title;
                            bubbleEl.appendChild(messageTitleEl);
                            if (msg.tokenMetaText) {
                                const tokenMetaEl = document.createElement('div');
                                tokenMetaEl.className = 'research-execute-message-token-meta';
                                const tokenMetaBits = [String(msg.tokenMetaText || '').trim()].filter(Boolean);
                                if (msg === activeAssistantMsg) {
                                    tokenMetaBits.push(`elapsed ${_formatElapsedDuration(Date.now() - Number(msg.startedAt || msg.at || Date.now()))}`);
                                }
                                tokenMetaEl.textContent = tokenMetaBits.join(' · ');
                                bubbleEl.appendChild(tokenMetaEl);
                            } else if (msg === activeAssistantMsg) {
                                const tokenMetaEl = document.createElement('div');
                                tokenMetaEl.className = 'research-execute-message-token-meta';
                                tokenMetaEl.textContent = `elapsed ${_formatElapsedDuration(Date.now() - Number(msg.startedAt || msg.at || Date.now()))}`;
                                bubbleEl.appendChild(tokenMetaEl);
                            }
                        }

                        const bodyEl = document.createElement('div');
                        bodyEl.className = 'research-execute-message-body';
                        const bodyText = String(msg.body || '').trim() || '—';
                        bodyEl.textContent = bodyText.length > 6000 ? bodyText.slice(-6000) : bodyText;
                        bubbleEl.appendChild(bodyEl);

                        msgEl.appendChild(bubbleEl);
                        attemptBodyEl.appendChild(msgEl);
                    });

                    attemptEl.appendChild(attemptHeaderEl);
                    attemptEl.appendChild(attemptBodyEl);
                    attemptBodyEl.style.display = attemptExpanded ? 'block' : 'none';
                    attemptToggleEl.style.transform = attemptExpanded ? 'rotate(90deg)' : 'rotate(0deg)';

                    const toggleAttempt = () => {
                        attemptExpanded = !attemptExpanded;
                        executeState.attemptExpandedById.set(attemptKey, attemptExpanded);
                        attemptBodyEl.style.display = attemptExpanded ? 'block' : 'none';
                        attemptToggleEl.style.transform = attemptExpanded ? 'rotate(90deg)' : 'rotate(0deg)';
                    };

                    attemptToggleEl.addEventListener('click', (e) => {
                        e.stopPropagation();
                        toggleAttempt();
                    });
                    attemptHeaderEl.addEventListener('click', toggleAttempt);

                    contentEl.appendChild(attemptEl);
                });

                detailsEl.appendChild(contentEl);
                cardEl.appendChild(detailsEl);

                // Toggle handler
                toggleEl.addEventListener('click', (e) => {
                    e.stopPropagation();
                    isExpanded = !isExpanded;
                    executeState.taskExpandedById.set(taskId, isExpanded);
                    toggleEl.style.transform = isExpanded ? 'rotate(90deg)' : 'rotate(0deg)';
                    detailsEl.style.display = isExpanded ? 'block' : 'none';
                    _updateExecuteToggleAllButton();
                });

                // Keep user-controlled expanded state (default: expanded)
                detailsEl.style.display = isExpanded ? 'block' : 'none';
                toggleEl.style.transform = isExpanded ? 'rotate(90deg)' : 'rotate(0deg)';
                headerEl.addEventListener('click', () => {
                    isExpanded = !isExpanded;
                    executeState.taskExpandedById.set(taskId, isExpanded);
                    toggleEl.style.transform = isExpanded ? 'rotate(90deg)' : 'rotate(0deg)';
                    detailsEl.style.display = isExpanded ? 'block' : 'none';
                    _updateExecuteToggleAllButton();
                });

                executeStreamBodyEl.appendChild(cardEl);
            } else if (block.type === 'system') {
                const msg = block.msg;
                const wrap = document.createElement('div');
                wrap.className = `research-execute-message research-execute-message--system`;

                const bubble = document.createElement('div');
                bubble.className = 'research-execute-message-bubble';

                if (msg.title) {
                    const titleEl = document.createElement('div');
                    titleEl.className = 'research-execute-message-title';
                    titleEl.textContent = msg.title;
                    bubble.appendChild(titleEl);
                }

                const bodyEl = document.createElement('div');
                bodyEl.className = 'research-execute-message-body';
                const bodyText = String(msg.body || '').trim() || '—';
                bodyEl.textContent = bodyText.length > 6000 ? bodyText.slice(-6000) : bodyText;
                bubble.appendChild(bodyEl);

                wrap.appendChild(bubble);
                executeStreamBodyEl.appendChild(wrap);
            }
        });

        if (executeAutoFollow || (wasNearBottom && executeStreamBodyEl.childElementCount <= 2)) {
            _scrollExecuteStreamToLatest();
        }
        _updateExecuteToggleAllButton();
        _updateExecuteJumpLatestButton();
        _syncExecuteElapsedTicker();
    }

    function initExecuteStreamControls() {
        if (executeToggleAllBtnEl) {
            executeToggleAllBtnEl.addEventListener('click', () => {
                const taskIds = executeState.order || [];
                if (!taskIds.length) return;
                const allCollapsed = taskIds.every((taskId) => executeState.taskExpandedById.get(taskId) === false);
                _setAllExecuteTaskExpanded(allCollapsed);
            });
        }
        if (executeJumpLatestBtnEl) {
            executeJumpLatestBtnEl.addEventListener('click', () => {
                executeAutoFollow = true;
                _scrollExecuteStreamToLatest();
                _updateExecuteJumpLatestButton();
            });
        }
        if (executeStreamBodyEl) {
            executeStreamBodyEl.addEventListener('scroll', () => {
                const nearBottom = _isExecuteStreamNearBottom();
                executeAutoFollow = nearBottom;
                _updateExecuteJumpLatestButton();
            }, { passive: true });
        }
        _updateExecuteToggleAllButton();
        _updateExecuteJumpLatestButton();
    }

    function _getQueryParam(name) {
        if (typeof navUtils.getQueryParam === 'function') return navUtils.getQueryParam(name);
        try {
            const params = new URLSearchParams(window.location.search || '');
            return (params.get(name) || '').trim();
        } catch (_) {
            return '';
        }
    }

    function _getResearchIdFromUrl() {
        if (typeof navUtils.getResearchIdFromUrl === 'function') return navUtils.getResearchIdFromUrl();
        const byQuery = _getQueryParam('researchId') || _getQueryParam('rid');
        if (byQuery) return byQuery;
        const hash = (window.location.hash || '').replace(/^#/, '');
        const m = hash.match(/^\/r\/(.+)$/);
        if (m) return decodeURIComponent(m[1]);
        return '';
    }

    function navigateToCreateResearch() {
        if (typeof navUtils.navigateToCreateResearch === 'function') {
            navUtils.navigateToCreateResearch();
            return;
        }
        window.location.href = 'research.html';
    }

    function navigateToResearch(researchId) {
        if (typeof navUtils.navigateToResearch === 'function') {
            navUtils.navigateToResearch(researchId);
            return;
        }
        if (!researchId) return;
        window.location.href = `research_detail.html?researchId=${encodeURIComponent(researchId)}`;
    }

    function _scrollToDetails() {
        if (typeof navUtils.scrollToDetails === 'function') {
            navUtils.scrollToDetails();
            return;
        }
        const host = document.getElementById('researchDetailHost');
        if (!host) return;
        host.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function initStageNav() {
        Object.entries(stageButtons).forEach(([stage, btn]) => {
            if (!btn) return;
            btn.addEventListener('click', () => {
                if (btn.disabled) return;
                setActiveStage(stage);
            });
        });
    }

    function initTreeTabs() {
        if (!treeTabButtons.length) return;
        treeTabButtons.forEach((btn) => {
            btn.addEventListener('click', () => {
                const view = String(btn.getAttribute('data-view') || '').trim();
                if (!view) return;
                setTreeView(view);
            });
        });
        document.addEventListener('maars:switch-to-output-tab', () => {
            // Only switch when execute stage is active; avoid overriding plan/refine/paper.
            if (activeStage === 'execute') setTreeView('output');
        });
    }

    function initExecuteSplitter() {
        if (!executeSplitterEl || !panelWorkbench) return;

        _loadExecuteSplitRatio();
        _applyExecuteSplitRatio();

        let dragging = false;

        const onPointerMove = (e) => {
            if (!dragging) return;
            const rect = panelWorkbench.getBoundingClientRect();
            if (!rect || rect.width <= 0) return;
            const x = Number(e.clientX || 0);
            const pct = ((x - rect.left) / rect.width) * 100;
            executeSplitRatio = Math.max(35, Math.min(90, pct));
            _applyExecuteSplitRatio();
        };

        const stopDrag = () => {
            if (!dragging) return;
            dragging = false;
            document.body.style.userSelect = '';
            document.body.style.cursor = '';
            _saveExecuteSplitRatio();
            window.removeEventListener('pointermove', onPointerMove);
            window.removeEventListener('pointerup', stopDrag);
            window.removeEventListener('pointercancel', stopDrag);
        };

        executeSplitterEl.addEventListener('pointerdown', (e) => {
            if (activeStage !== 'execute') return;
            dragging = true;
            document.body.style.userSelect = 'none';
            document.body.style.cursor = 'col-resize';
            try { executeSplitterEl.setPointerCapture(e.pointerId); } catch (_) { }
            window.addEventListener('pointermove', onPointerMove);
            window.addEventListener('pointerup', stopDrag);
            window.addEventListener('pointercancel', stopDrag);
        });
    }

    async function createResearchFromHome() {
        const prompt = (promptInput?.value || '').trim();
        if (!prompt) return;
        createBtn && (createBtn.disabled = true);
        try {
            const { researchId } = await api.createResearch(prompt);
            if (!researchId) throw new Error('Create failed');
            document.dispatchEvent(new CustomEvent('maars:research-list-refresh'));
            navigateToResearch(researchId);
        } catch (e) {
            console.error(e);
            alert(e?.message || 'Failed to create research');
        } finally {
            createBtn && (createBtn.disabled = false);
        }
    }

    async function loadResearch(researchId) {
        currentResearchId = researchId;
        cfg.setCurrentResearchId?.(researchId);

        // clear UI, then restore from DB snapshot
        document.dispatchEvent(new CustomEvent('maars:restore-start'));

        const data = await api.getResearch(researchId);
        const research = data?.research || {};
        const idea = data?.idea || null;
        const plan = data?.plan || null;
        const execution = data?.execution || null;
        const outputs = data?.outputs || {};
        const stepEvents = data?.stepEvents || { runId: '', events: [] };
        const paper = data?.paper || null;

        if (breadcrumbEl) breadcrumbEl.textContent = 'Research';
        if (titleEl) titleEl.textContent = research.title || research.researchId || 'Research';

        stageData.originalIdea = (idea?.idea || research.prompt || '').trim();
        stageData.papers = Array.isArray(idea?.papers) ? idea.papers : [];
        stageData.refined = (idea?.refined_idea || '').trim();
        stageData.refineThinking = '';
        stageData.paper = (paper?.content || '').trim();
        _renderRefinePanel();
        _renderPaperPanel();

        // Stage enablement: stage becomes clickable once started.
        // Use DB snapshot heuristics + runtime events.
        currentStageState = {
            refine: { started: !!(research.currentIdeaId || stageData.refined || stageData.papers.length) },
            plan: { started: !!(plan && Array.isArray(plan.tasks) && plan.tasks.length) },
            execute: { started: !!(execution && Array.isArray(execution.tasks) && execution.tasks.length) },
            paper: { started: !!(paper && String(paper.content || '').trim()) },
        };
        stageStatusDetails = {
            refine: { status: 'idle', message: 'idle' },
            plan: { status: 'idle', message: 'idle' },
            execute: { status: 'idle', message: 'idle' },
            paper: { status: 'idle', message: 'idle' },
        };
        const rs = String(research.stage || 'refine').trim() || 'refine';
        const rss = String(research.stageStatus || 'idle').trim() || 'idle';
        const order = ['refine', 'plan', 'execute', 'paper'];
        const rank = order.indexOf(rs);
        if (rank >= 0) {
            if (rss === 'completed') {
                for (let i = 0; i <= rank; i += 1) {
                    const s = order[i];
                    stageStatusDetails[s] = { status: 'completed', message: 'completed' };
                }
            } else if (rss === 'running' || rss === 'stopped' || rss === 'failed') {
                for (let i = 0; i < rank; i += 1) {
                    const s = order[i];
                    stageStatusDetails[s] = { status: 'completed', message: 'completed' };
                }
                stageStatusDetails[rs] = { status: rss, message: rss };
            } else {
                stageStatusDetails[rs] = { status: rss, message: rss };
            }
        }
        renderStageButtons();

        const ideaId = research.currentIdeaId || '';
        const planId = research.currentPlanId || '';
        cfg.setCurrentIdeaId?.(ideaId);
        cfg.setCurrentPlanId?.(planId);

        let treePayload = { treeData: [], layout: null };
        let executionLayout = null;
        let executionForRestore = execution;
        if (ideaId && planId) {
            try {
                const res = await cfg.fetchWithSession(`${cfg.API_BASE_URL}/plan/tree?ideaId=${encodeURIComponent(ideaId)}&planId=${encodeURIComponent(planId)}`);
                const json = await res.json();
                if (res.ok) treePayload = { treeData: json.treeData || [], layout: json.layout || null };
            } catch (_) { }

            // Restore execute tree layout as well; otherwise Execute panel appears empty on revisit.
            try {
                let executionSnapshot = execution;
                let execTasks = Array.isArray(executionSnapshot?.tasks) ? executionSnapshot.tasks : [];
                if (!execTasks.length) {
                    const genRes = await cfg.fetchWithSession(`${cfg.API_BASE_URL}/execution/generate-from-plan`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ ideaId, planId }),
                    });
                    const genJson = await genRes.json().catch(() => ({}));
                    const generatedExecution = genJson?.execution;
                    if (genRes.ok && Array.isArray(generatedExecution?.tasks) && generatedExecution.tasks.length) {
                        executionSnapshot = generatedExecution;
                        execTasks = generatedExecution.tasks;
                    }
                }
                if (execTasks.length) {
                    executionForRestore = executionSnapshot;
                    const layoutRes = await cfg.fetchWithSession(`${cfg.API_BASE_URL}/plan/layout`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ execution: executionSnapshot, ideaId, planId }),
                    });
                    const layoutJson = await layoutRes.json().catch(() => ({}));
                    if (layoutRes.ok && layoutJson?.layout) {
                        executionLayout = layoutJson.layout;
                        executionGraphPayload = {
                            treeData: Array.isArray(layoutJson.layout?.treeData) ? layoutJson.layout.treeData : [],
                            layout: layoutJson.layout?.layout || null,
                        };
                        invalidateExecutionGraphRender();
                    }
                }
            } catch (_) { }
        }

        document.dispatchEvent(new CustomEvent('maars:restore-complete', {
            detail: {
                ideaId,
                planId,
                treePayload,
                plan,
                layout: executionLayout,
                execution: executionForRestore,
                outputs: outputs || {},
                ideaText: idea?.idea || research.prompt || '',
            },
        }));

        const hasPersistedTimeline = Array.isArray(stepEvents?.events) && stepEvents.events.length > 0;
        _seedExecutionState(treePayload.treeData, executionForRestore, outputs, {
            skipOutputSeed: hasPersistedTimeline,
        });
        if (hasPersistedTimeline) {
            _replayPersistedStepEvents(stepEvents);
        }
        if (executionGraphPayload?.layout) {
            scheduleExecutionGraphRender({ force: true, allowInactive: true, delays: [0, 100, 320, 700] });
        }
        if (activeStage === 'execute') renderExecuteStream();
        refreshExecutionRuntimeStatus({ ideaId, planId });

        // Restore refine + paper output using their normal event paths.
        if (idea && (idea.keywords || idea.papers || idea.refined_idea)) {
            document.dispatchEvent(new CustomEvent('maars:idea-complete', {
                detail: {
                    ideaId,
                    keywords: idea.keywords || [],
                    papers: idea.papers || [],
                    refined_idea: idea.refined_idea || '',
                },
            }));
        }
        if (paper?.content) {
            document.dispatchEvent(new CustomEvent('maars:paper-complete', {
                detail: {
                    ideaId,
                    planId,
                    content: paper.content,
                    format: paper.format || 'markdown',
                },
            }));
        }

        // Auto-run pipeline when entering research page.
        // Only auto-run on first entry (idle). On revisit, show snapshot and let user Retry manually.
        try {
            const stageStatus = String(research.stageStatus || '').trim().toLowerCase();
            if (stageStatus === 'idle') {
                await api.runResearch(researchId);
            }
        } catch (e) {
            // Ignore 409 conflicts (already running)
            const msg = String(e?.message || '');
            if (!/already running|409/.test(msg)) console.warn('runResearch failed', e);
        }
    }

    function initDetailControls(researchId) {
        const bindStageAction = (stage, action, handler) => {
            const btn = stageActionBtns?.[stage]?.[action];
            if (!btn) return;
            btn.addEventListener('click', async () => {
                if (!researchId) return;
                if (action !== 'stop' && !_isStagePrerequisiteCompleted(stage)) {
                    alert(`Cannot start ${stage} stage before previous stage is completed.`);
                    renderStageStatusDetails();
                    return;
                }
                btn.disabled = true;
                try {
                    await handler();
                    document.dispatchEvent(new CustomEvent('maars:research-list-refresh'));
                } catch (e) {
                    console.error(e);
                    alert(e?.message || `Failed to ${action} stage`);
                } finally {
                    renderStageStatusDetails();
                }
            });
        };

        ['refine', 'plan', 'execute', 'paper'].forEach((stage) => {
            bindStageAction(stage, 'run', async () => {
                await api.runResearchStage(researchId, stage);
                if (stage === 'execute') {
                    _resetExecuteTimelineForNewRun();
                    if (activeStage === 'execute') {
                        scheduleExecutionGraphRender({ force: true, delays: [0, 100, 320, 700] });
                        renderExecuteStream();
                    }
                }
                setActiveStage(stage);
            });
            bindStageAction(stage, 'resume', async () => {
                await api.resumeResearchStage(researchId, stage);
                setActiveStage(stage);
            });
            bindStageAction(stage, 'retry', async () => {
                await api.retryResearchStage(researchId, stage);
                if (stage === 'execute') {
                    _resetExecuteTimelineForNewRun();
                    if (activeStage === 'execute') {
                        scheduleExecutionGraphRender({ force: true, delays: [0, 100, 320, 700] });
                        renderExecuteStream();
                    }
                }
                setActiveStage(stage);
            });
            bindStageAction(stage, 'stop', async () => {
                await api.stopResearchStage(researchId, stage);
            });
        });
    }

    function initEventBridges() {
        // Update stage state based on live pipeline events.
        document.addEventListener('maars:idea-start', () => setStageStarted('refine', true));
        document.addEventListener('maars:plan-start', () => setStageStarted('plan', true));
        document.addEventListener('maars:task-start', () => {
            setStageStarted('execute', true);
            if (activeStage === 'execute') {
                scheduleExecutionGraphRender({ force: true, delays: [0, 100, 320, 700] });
                renderExecuteStream();
            }
        });
        document.addEventListener('maars:paper-start', () => setStageStarted('paper', true));
        document.addEventListener('maars:task-start', () => refreshExecutionRuntimeStatus());

        document.addEventListener('maars:research-stage', (e) => {
            const d = e?.detail || {};
            if (d.researchId && currentResearchId && d.researchId !== currentResearchId) return;
            const stage = String(d.stage || '').trim();
            const status = String(d.status || '').trim() || 'idle';
            const error = String(d.error || '').trim();
            if (stage && currentStageState[stage] != null) {
                if (status === 'running' || status === 'completed' || status === 'stopped' || status === 'failed') {
                    setStageStarted(stage, true);
                }
                stageStatusDetails[stage] = {
                    status,
                    message: error || status,
                };
                renderStageButtons(stage);
                if (status === 'running' || status === 'completed') {
                    setActiveStage(stage);
                }
            }
            document.dispatchEvent(new CustomEvent('maars:research-list-refresh'));
        });

        document.addEventListener('maars:research-error', (e) => {
            const d = e?.detail || {};
            if (d.researchId && currentResearchId && d.researchId !== currentResearchId) return;
            if (d.error) {
                console.warn('Research error:', d.error);
                const msg = String(d.error || '').trim();
                if (refineLogicEl && !String(stageData.refined || '').trim()) {
                    refineLogicEl.innerHTML = _mdToHtml(`> Refine failed\n\n${msg}`);
                }
            }
        });

        // Keep sidebar list in sync
        document.addEventListener('maars:research-list-refresh', () => {
            window.MAARS?.sidebar?.refreshResearchList?.();
        });

        // Keep refine/paper panels updated
        document.addEventListener('maars:idea-complete', (e) => {
            const d = e?.detail || {};
            if (d.idea) stageData.originalIdea = String(d.idea || '').trim() || stageData.originalIdea;
            if (Array.isArray(d.papers)) stageData.papers = d.papers;
            if (typeof d.refined_idea === 'string') stageData.refined = d.refined_idea;
            stageData.refineThinking = '';
            _renderRefinePanel();
        });

        document.addEventListener('maars:idea-thinking', (e) => {
            const d = e?.detail || {};
            const chunk = String(d.chunk || '').trim();
            const toolName = String(d?.scheduleInfo?.tool_name || '').trim();
            const turn = d?.scheduleInfo?.turn;
            const maxTurns = d?.scheduleInfo?.max_turns;
            const parts = [];
            if (toolName) parts.push(`Running tool: **${toolName}**`);
            if (Number.isFinite(turn) && Number.isFinite(maxTurns)) parts.push(`Turn ${turn}/${maxTurns}`);
            if (chunk) parts.push(chunk);
            if (!parts.length) return;
            stageData.refineThinking = parts.join('\n\n');
            if (!String(stageData.refined || '').trim()) {
                _renderRefinePanel();
            }
        });
        document.addEventListener('maars:paper-complete', (e) => {
            const d = e?.detail || {};
            if (typeof d.content === 'string') stageData.paper = d.content;
            _renderPaperPanel();
        });

        document.addEventListener('maars:task-states-update', (e) => {
            const d = e?.detail || {};
            const tasks = Array.isArray(d.tasks) ? d.tasks : [];
            if (!tasks.length) return;
            tasks.forEach((t) => {
                if (!t?.task_id) return;
                const id = _ensureTaskInOrder(t.task_id);
                _upsertTaskMeta(t);
                if (!id) return;
                const nextStatus = String(t.status || '');
                const prevStatus = executeState.statuses.get(id) || '';
                executeState.statuses.set(id, nextStatus);
                // Only update status map, don't add duplicate description messages
                // Task descriptions are shown in task-started event, status changes are shown in status labels
            });
            if (activeStage === 'execute') {
                scheduleExecutionGraphRender();
                renderExecuteStream();
            }
        });

        document.addEventListener('maars:task-thinking', (e) => {
            const d = e?.detail || {};
            const taskId = String(d.taskId || d.task_id || '').trim();
            const chunk = String(d.chunk || '').trim();
            const operation = String(d.operation || 'Execute').trim() || 'Execute';
            if (!taskId || !chunk) return;

            // Keep validation/Step-B details in the final failure summary bubble only.
            if (/^validate$/i.test(operation) || /^step-b$/i.test(operation)) return;

            _ensureTaskInOrder(taskId);
            _setCurrentAttempt(taskId, Number(d.attempt || d?.scheduleInfo?.attempt) || _getCurrentAttempt(taskId));
            _upsertExecuteThinkingMessage(
                taskId,
                operation,
                chunk,
                d.scheduleInfo || null,
                Number(d.attempt || d?.scheduleInfo?.attempt) || 0,
            );

            if (activeStage === 'execute') {
                renderExecuteStream();
            }
        });

        document.addEventListener('maars:task-started', (e) => {
            const d = e?.detail || {};
            const taskId = String(d.taskId || d.task_id || '').trim();
            if (!taskId) return;

            _ensureTaskInOrder(taskId);
            _setCurrentAttempt(taskId, Number(d.attempt) || _getCurrentAttempt(taskId));
            _upsertTaskMeta({
                task_id: taskId,
                title: String(d.title || d.description || taskId).trim() || taskId,
                description: String(d.description || '').trim() || '',
                status: 'doing',
            });

            const meta = _getTaskMetaById(taskId) || {};
            _appendExecuteMessage({
                taskId,
                kind: 'system',
                title: `${taskId} started · Attempt ${_getCurrentAttempt(taskId)}`,
                body: meta.description || 'Task execution started',
                status: 'doing',
                attempt: _getCurrentAttempt(taskId),
            });

            if (activeStage === 'execute') {
                scheduleExecutionGraphRender();
                renderExecuteStream();
            }
        });

        document.addEventListener('maars:task-output', (e) => {
            const d = e?.detail || {};
            const taskId = String(d.taskId || d.task_id || '').trim();
            if (!taskId) return;
            _ensureTaskInOrder(taskId);
            _setCurrentAttempt(taskId, Number(d.attempt) || _getCurrentAttempt(taskId));
            const outputText = _stringifyOutput(d.output);
            _pushRecentOutput(taskId, outputText);
            const meta = _getTaskMetaById(taskId) || {};
            const attemptNumber = _getCurrentAttempt(taskId);
            _appendExecuteMessage({
                taskId,
                kind: 'output',
                title: meta.title || taskId,
                body: outputText,
                attempt: attemptNumber,
                status: executeState.statuses.get(taskId) || meta.status || '',
                dedupeKey: `output:${taskId}:${attemptNumber}:${outputText.slice(0, 120)}`,
            });

            if (activeStage === 'execute') {
                renderExecuteStream();
            }
        });

        document.addEventListener('maars:task-completed', (e) => {
            const d = e?.detail || {};
            const taskId = String(d.taskId || d.task_id || '').trim();
            if (!taskId) return;

            _setCurrentAttempt(taskId, Number(d.attempt) || _getCurrentAttempt(taskId));
            executeState.statuses.set(taskId, 'done');
            const meta = _getTaskMetaById(taskId) || {};
            const validated = !!d.validated;
            const attemptNumber = _getCurrentAttempt(taskId);
            const body = validated
                ? _buildValidationSummaryBody(taskId, d, meta, { statusLabel: 'PASS' })
                : 'Task completed successfully.';

            _appendExecuteMessage({
                taskId,
                kind: 'system',
                title: `${taskId} ${validated ? 'validation summary' : 'completed'} · Attempt ${attemptNumber}`,
                body,
                attempt: attemptNumber,
                status: 'done',
                dedupeKey: validated ? `validation-pass:${taskId}:${attemptNumber}` : '',
            });

            if (activeStage === 'execute') {
                scheduleExecutionGraphRender();
                renderExecuteStream();
            }
        });

        document.addEventListener('maars:execution-sync', (e) => {
            const d = e?.detail || {};
            const tasks = Array.isArray(d.tasks) ? d.tasks : [];
            if (!tasks.length) return;
            tasks.forEach((task) => {
                _upsertTaskMeta(task);
                const id = _ensureTaskInOrder(task.task_id);
                if (!id) return;
                const nextStatus = String(task.status || '');
                if (nextStatus) executeState.statuses.set(id, nextStatus);
            });
            if (activeStage === 'execute') {
                scheduleExecutionGraphRender();
                renderExecuteStream();
            }
            refreshExecutionRuntimeStatus();
        });

        document.addEventListener('maars:task-complete', (e) => {
            const d = e?.detail || {};
            const taskId = String(d.taskId || d.task_id || '').trim();
            if (!taskId) return;
            _setCurrentAttempt(taskId, Number(d.attempt) || _getCurrentAttempt(taskId));
            const meta = _getTaskMetaById(taskId) || {};
            _appendExecuteMessage({
                taskId,
                kind: 'assistant',
                title: `${meta.title || taskId} · Attempt ${_getCurrentAttempt(taskId)}`,
                body: 'Step completed.',
                attempt: _getCurrentAttempt(taskId),
                status: 'done',
            });
            executeState.statuses.set(taskId, 'done');
            if (activeStage === 'execute') {
                scheduleExecutionGraphRender();
                renderExecuteStream();
            }
            refreshExecutionRuntimeStatus();
        });

        document.addEventListener('maars:task-error', (e) => {
            const d = e?.detail || {};
            // fatal=true comes from _trigger_fail_fast after _retry_or_fail already emitted
            // a full validation summary — skip to avoid duplicate bubble
            if (d.fatal === true) return;
            const taskId = String(d.taskId || d.task_id || '').trim();
            const errorText = String(d.error || '').trim();
            const phase = String(d.phase || '').trim();
            const attempt = Number(d.attempt);
            const maxAttempts = Number(d.maxAttempts);
            const willRetry = d.willRetry === true;
            if (!taskId && !errorText) return;
            const meta = _getTaskMetaById(taskId) || {};
            const messageAttempt = Number.isFinite(attempt) ? attempt : _getCurrentAttempt(taskId);
            _setCurrentAttempt(taskId, messageAttempt);
            const detailParts = [];
            if (phase) detailParts.push(`Phase: ${phase}`);
            if (Number.isFinite(attempt) && Number.isFinite(maxAttempts)) {
                detailParts.push(`Attempt ${attempt}/${maxAttempts}`);
            }
            if (typeof d.willRetry === 'boolean') {
                detailParts.push(willRetry ? 'Retry scheduled' : 'No more automatic retries');
            }
            const detailPrefix = detailParts.length ? `${detailParts.join(' · ')}\n` : '';
            const terminalStatus = phase === 'validation' ? 'validation-failed' : 'execution-failed';
            const currentStatus = taskId ? (executeState.statuses.get(taskId) || '') : '';
            const nextStatus = willRetry ? (currentStatus || 'doing') : terminalStatus;
            const isValidationPhase = phase === 'validation';
            const body = isValidationPhase
                ? _buildValidationSummaryBody(taskId, d, meta, { statusLabel: 'FAIL' })
                : `${detailPrefix}${errorText || 'Unknown execution error.'}`;
            _appendExecuteMessage({
                taskId: taskId || '',
                kind: isValidationPhase ? 'error' : (willRetry ? 'system' : 'error'),
                title: isValidationPhase
                    ? `${meta.title || taskId || 'Task'} · Validation failed · Attempt ${messageAttempt}`
                    : `${meta.title || taskId || (willRetry ? 'Retrying Task' : 'Execution Error')} · Attempt ${messageAttempt}`,
                body,
                attempt: messageAttempt,
                status: taskId ? nextStatus : terminalStatus,
                dedupeKey: isValidationPhase ? `validation-fail:${taskId}:${messageAttempt}` : '',
            });
            if (taskId) executeState.statuses.set(taskId, nextStatus);
            if (activeStage === 'execute') renderExecuteStream();
            refreshExecutionRuntimeStatus();
        });

        document.addEventListener('maars:attempt-retry', (e) => {
            const d = e?.detail || {};
            const taskId = String(d.taskId || d.task_id || '').trim();
            if (!taskId) return;
            _ensureTaskInOrder(taskId);
            const phase = String(d.phase || '').trim() || 'execution';
            const reason = String(d.reason || '').trim() || 'Retry requested';
            const attempt = Number(d.attempt);
            const nextAttempt = Number(d.nextAttempt);
            const maxAttempts = Number(d.maxAttempts);
            const detailParts = [`Phase: ${phase}`];
            if (Number.isFinite(attempt) && Number.isFinite(nextAttempt) && Number.isFinite(maxAttempts)) {
                detailParts.push(`Retry ${nextAttempt}/${maxAttempts} (failed ${attempt}/${maxAttempts})`);
            }
            const failedAttempt = Number.isFinite(attempt) ? attempt : _getCurrentAttempt(taskId);
            const upcomingAttempt = Number.isFinite(nextAttempt) ? nextAttempt : failedAttempt + 1;
            const validationSummary = d?.decision?.validationSummary || {};
            const directReasonRaw = String(validationSummary?.directReason || '').trim();
            const directReason = directReasonRaw || _extractValidationDirectReason(reason);
            const body = phase === 'validation'
                ? `Direct reason: ${directReason || 'Validation failed'}\n${detailParts.join(' · ')}\n${reason}`
                : `${detailParts.join(' · ')}\n${reason}`;
            _appendExecuteMessage({
                taskId,
                kind: 'system',
                title: `${taskId} retrying · Attempt ${failedAttempt}`,
                body,
                attempt: failedAttempt,
                status: executeState.statuses.get(taskId) || 'execution-failed',
                dedupeKey: `retry:${taskId}:${phase}:${failedAttempt}:${upcomingAttempt}`,
            });
            executeState.attemptExpandedById.set(_getAttemptKey(taskId, failedAttempt), false);
            _setCurrentAttempt(taskId, upcomingAttempt);
            executeState.attemptExpandedById.set(_getAttemptKey(taskId, upcomingAttempt), true);
            if (activeStage === 'execute') renderExecuteStream();
        });

        document.addEventListener('maars:task-step-b', (e) => {
            const d = e?.detail || {};
            const taskId = String(d.taskId || d.task_id || '').trim();
            if (!taskId) return;
            _ensureTaskInOrder(taskId);
            const attempt = Number(d.attempt) || _getCurrentAttempt(taskId);
            _setCurrentAttempt(taskId, attempt);
            executeState.latestStepBByTask.set(taskId, {
                shouldAdjust: d.shouldAdjust === true,
                immutableImpacted: d.immutableImpacted === true,
                patchSummary: String(d.patchSummary || '').trim(),
                reasoning: String(d.reasoning || '').trim(),
            });
        });

        document.addEventListener('maars:execution-runtime-status', (e) => {
            renderExecutionRuntimeStatus(e?.detail || {});
        });

        document.addEventListener('maars:execution-layout', (e) => {
            const d = e?.detail || {};
            const treeData = Array.isArray(d?.layout?.treeData) ? d.layout.treeData : [];
            const graphLayout = d?.layout?.layout || null;
            if (!treeData.length || !graphLayout) return;
            executionGraphPayload = { treeData, layout: graphLayout };
            invalidateExecutionGraphRender();
            treeData.forEach(_upsertTaskMeta);
            if (activeStage === 'execute') {
                scheduleExecutionGraphRender({ force: true, delays: [0, 100, 320, 700] });
                renderExecuteStream();
            }
        });

        window.addEventListener('pageshow', () => {
            scheduleExecutionGraphRender({ force: true, allowInactive: true, delays: [0, 120, 360, 900] });
        });

        window.addEventListener('resize', () => {
            if (activeStage !== 'execute') return;
            scheduleExecutionGraphRender({ force: true, delays: [0, 120] });
        });

        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState !== 'visible') return;
            scheduleExecutionGraphRender({
                force: true,
                allowInactive: activeStage !== 'execute',
                delays: [0, 120, 360],
            });
        });
    }

    function init() {
        initStageNav();
        initTreeTabs();
        initExecuteSplitter();
        initExecuteStreamControls();
        initEventBridges();

        // Create page (index.html / research.html)
        if (homeView && promptInput && createBtn) {
            createBtn.addEventListener('click', createResearchFromHome);
            // Prefer focusing the prompt on the dedicated research create page.
            try {
                if (/research\.html$/.test(window.location.pathname || '')) {
                    promptInput.focus();
                }
            } catch (_) { }
        }

        // Detail page (research_detail.html)
        if (researchView) {
            const rid = _getResearchIdFromUrl();
            if (rid) {
                initDetailControls(rid);
                // Default to Refine view on entry.
                setActiveStage('refine');
                renderExecutionRuntimeStatus({ enabled: true, available: true, connected: false });
                loadResearch(rid).catch((e) => {
                    console.error(e);
                    alert(e?.message || 'Failed to load research');
                    navigateToCreateResearch();
                });
            } else {
                // No id - send user to create page
                navigateToCreateResearch();
            }
        }
    }

    window.MAARS = window.MAARS || {};
    window.MAARS.research = { init, navigateToResearch, navigateToCreateResearch };
})();
