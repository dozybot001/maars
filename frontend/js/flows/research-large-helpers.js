/**
 * Large helper functions extracted from research flow.
 */
(function () {

    function _isExecuteStreamNearBottom(ctx) {
        const bodyEl = ctx.executeStreamBodyEl;
        if (!bodyEl) return true;
        return (bodyEl.scrollHeight - bodyEl.scrollTop - bodyEl.clientHeight) < 48;
    }

    function _scrollExecuteStreamToLatest(ctx) {
        const bodyEl = ctx.executeStreamBodyEl;
        if (!bodyEl) return;
        bodyEl.scrollTop = bodyEl.scrollHeight;
    }

    function _updateExecuteJumpLatestButton(ctx) {
        const jumpBtnEl = ctx.executeJumpLatestBtnEl;
        if (!jumpBtnEl || !ctx.executeStreamBodyEl) return;
        const hasMessages = (ctx.executeState.messages || []).length > 0;
        const shouldShow = hasMessages && !ctx.getExecuteAutoFollow() && !_isExecuteStreamNearBottom(ctx);
        jumpBtnEl.hidden = !shouldShow;
    }

    function _formatElapsedDuration(ctx, ms) {
        if (typeof ctx.executeUtils.formatElapsedDuration === 'function') {
            return ctx.executeUtils.formatElapsedDuration(ms);
        }
        return '0s';
    }

    function _hasActiveExecuteBubble(ctx) {
        return ctx.executeState.messages.some((msg) => {
            if (msg.kind !== 'assistant') return false;
            const taskId = String(msg.taskId || '').trim();
            if (!taskId) return false;
            const status = String(ctx.executeState.statuses.get(taskId) || '').trim();
            return status === 'doing' || status === 'validating';
        });
    }

    function _syncExecuteElapsedTicker(ctx) {
        const shouldRun = ctx.getActiveStage() === 'execute' && _hasActiveExecuteBubble(ctx);
        if (!shouldRun) {
            if (ctx.getExecuteElapsedTimerId()) {
                window.clearInterval(ctx.getExecuteElapsedTimerId());
                ctx.setExecuteElapsedTimerId(0);
            }
            return;
        }
        if (ctx.getExecuteElapsedTimerId()) return;
        const timerId = window.setInterval(() => {
            if (ctx.getActiveStage() !== 'execute' || !_hasActiveExecuteBubble(ctx)) {
                _syncExecuteElapsedTicker(ctx);
                return;
            }
            ctx.renderExecuteStream();
        }, 1000);
        ctx.setExecuteElapsedTimerId(timerId);
    }

    function _getAttemptKey(ctx, taskId, attempt) {
        if (typeof ctx.executeUtils.getAttemptKey === 'function') {
            return ctx.executeUtils.getAttemptKey(taskId, attempt);
        }
        return `${String(taskId || '').trim()}:${Number(attempt) || 1}`;
    }

    function _getCurrentAttempt(ctx, taskId) {
        const id = String(taskId || '').trim();
        if (!id) return 1;
        const current = Number(ctx.executeState.currentAttemptByTask.get(id));
        return Number.isFinite(current) && current > 0 ? current : 1;
    }

    function _setCurrentAttempt(ctx, taskId, attempt) {
        const id = String(taskId || '').trim();
        const n = Number(attempt);
        if (!id || !Number.isFinite(n) || n < 1) return;
        const current = _getCurrentAttempt(ctx, id);
        const next = Math.max(current, n);
        ctx.executeState.currentAttemptByTask.set(id, next);
        const key = _getAttemptKey(ctx, id, next);
        if (!ctx.executeState.attemptExpandedById.has(key)) {
            ctx.executeState.attemptExpandedById.set(key, true);
        }
    }

    function _getAttemptStatus(ctx, taskId, attempt, msgs, fallbackStatus) {
        if (typeof ctx.executeUtils.getAttemptStatus === 'function') {
            return ctx.executeUtils.getAttemptStatus({
                taskId,
                attempt,
                msgs,
                fallbackStatus,
                currentAttempt: _getCurrentAttempt(ctx, taskId),
            });
        }
        return String(fallbackStatus || 'doing').trim() || 'doing';
    }

    function _getAttemptSummary(ctx, msgs) {
        if (typeof ctx.executeUtils.getAttemptSummary === 'function') {
            return ctx.executeUtils.getAttemptSummary(msgs);
        }
        return '';
    }

    function appendExecuteMessage(ctx, message) {
        if (!message || !message.taskId && message.kind !== 'system') return;
        const taskId = String(message.taskId || '').trim();
        let attempt = Number(message.attempt);
        if (taskId) {
            if (!Number.isFinite(attempt) || attempt < 1) {
                attempt = Number(ctx.executeState.currentAttemptByTask.get(taskId));
            }
            if (!Number.isFinite(attempt) || attempt < 1) attempt = 1;
            ctx.executeState.currentAttemptByTask.set(taskId, attempt);
            if (!ctx.executeState.attemptExpandedById.has(`${taskId}:${attempt}`)) {
                ctx.executeState.attemptExpandedById.set(`${taskId}:${attempt}`, true);
            }
        }
        const dedupeKey = String(message.dedupeKey || '').trim();
        if (dedupeKey) {
            const exists = ctx.executeState.messages.some((m) => m.dedupeKey === dedupeKey);
            if (exists) return;
        }
        ctx.executeState.messages.push({
            id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            at: Date.now(),
            ...message,
            startedAt: Number(message?.startedAt) || Date.now(),
            attempt: taskId ? attempt : undefined,
        });
        if (ctx.executeState.messages.length > ctx.EXECUTE_TIMELINE_MAX_MESSAGES) {
            ctx.executeState.messages = ctx.executeState.messages.slice(-ctx.EXECUTE_TIMELINE_MAX_MESSAGES);
        }
    }

    function upsertExecuteThinkingMessage(ctx, taskId, operation, body, scheduleInfo, attemptHint) {
        const id = String(taskId || '').trim();
        if (!id) return;
        const op = String(operation || 'Execute').trim() || 'Execute';
        const text = String(body || '').trim();
        if (!text) return;
        const hintedAttempt = Number(attemptHint || scheduleInfo?.attempt) || 0;
        const currentAttempt = Math.max(_getCurrentAttempt(ctx, id), hintedAttempt, 1);

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

        const last = ctx.executeState.messages[ctx.executeState.messages.length - 1];
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

        appendExecuteMessage(ctx, {
            taskId: id,
            kind: 'assistant',
            title,
            body: bodyText,
            tokenMetaText,
            status: ctx.executeState.statuses.get(id) || 'doing',
            attempt: currentAttempt,
            dedupeKey,
            repeatCount: 1,
            startedAt: Date.now(),
        });
    }

    function seedExecutionState(ctx, treeData, execution, outputs, options = {}) {
        ctx.executeState.order = [];
        ctx.executeState.statuses = new Map();
        ctx.executeState.latestStepBByTask = new Map();
        ctx.executeState.recentOutputsByTask = new Map();
        ctx.executeState.taskMetaById = new Map();
        ctx.executeState.messages = [];
        ctx.executeState.taskExpandedById = new Map();
        ctx.executeState.currentAttemptByTask = new Map();
        ctx.executeState.attemptExpandedById = new Map();

        const treeTasks = Array.isArray(treeData) ? treeData : [];
        const execTasks = Array.isArray(execution?.tasks) ? execution.tasks : [];
        treeTasks.forEach(ctx.upsertTaskMeta);
        execTasks.forEach((task) => {
            ctx.upsertTaskMeta(task);
            if (task?.status) ctx.executeState.statuses.set(task.task_id, String(task.status));
            _setCurrentAttempt(ctx, task.task_id, 1);
        });

        const skipOutputSeed = options?.skipOutputSeed === true;
        const outputMap = outputs && typeof outputs === 'object' ? outputs : {};
        if (!skipOutputSeed) {
            Object.entries(outputMap).forEach(([taskId, output]) => {
                const text = ctx.stringifyOutput(output).trim();
                if (!text) return;
                ctx.ensureTaskInOrder(taskId);
                ctx.pushRecentOutput(taskId, text);
            });
        }

        appendExecuteMessage(ctx, {
            kind: 'system',
            title: 'Execution timeline ready',
            body: execTasks.length ? `Loaded ${execTasks.length} execution steps.` : 'Waiting for execution to start.',
            dedupeKey: `seed:${ctx.getCurrentResearchId() || ''}`,
        });

        ctx.executeState.order.forEach((taskId) => {
            const meta = ctx.getTaskMetaById(taskId) || {};
            const status = ctx.executeState.statuses.get(taskId) || meta.status || 'undone';
            if (!skipOutputSeed) {
                const outputsForTask = ctx.executeState.recentOutputsByTask.get(taskId) || [];
                if (outputsForTask.length) {
                    appendExecuteMessage(ctx, {
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

    function resetExecuteTimelineForNewRun(ctx) {
        ctx.executeState.messages = [];
        ctx.executeState.latestStepBByTask = new Map();
        ctx.executeState.recentOutputsByTask = new Map();
        ctx.executeState.currentAttemptByTask = new Map();
        ctx.executeState.attemptExpandedById = new Map();
        ctx.setExecuteAutoFollow(true);
        ctx.executeState.order.forEach((taskId) => {
            _setCurrentAttempt(ctx, taskId, 1);
        });
        _updateExecuteJumpLatestButton(ctx);
        _syncExecuteElapsedTicker(ctx);
    }

    function renderExecuteStream(ctx) {
        const render = window.MAARS?.researchExecuteRender?.renderExecuteStream;
        if (typeof render === 'function') {
            render(ctx);
        }
    }

    function initExecuteStreamControls(ctx) {
        const initControls = window.MAARS?.researchExecuteRender?.initExecuteStreamControls;
        if (typeof initControls === 'function') {
            initControls(ctx);
        }
    }

    async function loadResearch(ctx, researchId) {
        ctx.setCurrentResearchId(researchId);
        ctx.cfg.setCurrentResearchId?.(researchId);

        document.dispatchEvent(new CustomEvent('maars:restore-start'));

        const data = await ctx.api.getResearch(researchId);
        const research = data?.research || {};
        const idea = data?.idea || null;
        const plan = data?.plan || null;
        const execution = data?.execution || null;
        const outputs = data?.outputs || {};
        const stepEvents = data?.stepEvents || { runId: '', events: [] };
        const paper = data?.paper || null;

        if (ctx.breadcrumbEl) ctx.breadcrumbEl.textContent = 'Research';
        if (ctx.titleEl) ctx.titleEl.textContent = research.title || research.researchId || 'Research';

        ctx.stageData.originalIdea = (idea?.idea || research.prompt || '').trim();
        ctx.stageData.papers = Array.isArray(idea?.papers) ? idea.papers : [];
        ctx.stageData.refined = (idea?.refined_idea || '').trim();
        ctx.stageData.refineThinking = '';
        ctx.stageData.paper = (paper?.content || '').trim();
        ctx.renderRefinePanel();
        ctx.renderPaperPanel();

        ctx.setCurrentStageState({
            refine: { started: !!(research.currentIdeaId || ctx.stageData.refined || ctx.stageData.papers.length) },
            plan: { started: !!(plan && Array.isArray(plan.tasks) && plan.tasks.length) },
            execute: { started: !!(execution && Array.isArray(execution.tasks) && execution.tasks.length) },
            paper: { started: !!(paper && String(paper.content || '').trim()) },
        });
        ctx.setStageStatusDetails({
            refine: { status: 'idle', message: 'idle' },
            plan: { status: 'idle', message: 'idle' },
            execute: { status: 'idle', message: 'idle' },
            paper: { status: 'idle', message: 'idle' },
        });
        const rs = String(research.stage || 'refine').trim() || 'refine';
        const rss = String(research.stageStatus || 'idle').trim() || 'idle';
        const order = ['refine', 'plan', 'execute', 'paper'];
        const rank = order.indexOf(rs);
        const stageStatusDetails = ctx.getStageStatusDetails();
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
        ctx.renderStageButtons();

        const ideaId = research.currentIdeaId || '';
        const planId = research.currentPlanId || '';
        ctx.cfg.setCurrentIdeaId?.(ideaId);
        ctx.cfg.setCurrentPlanId?.(planId);

        let treePayload = { treeData: [], layout: null };
        let executionLayout = null;
        let executionForRestore = execution;
        if (ideaId && planId) {
            try {
                const res = await ctx.cfg.fetchWithSession(`${ctx.cfg.API_BASE_URL}/plan/tree?ideaId=${encodeURIComponent(ideaId)}&planId=${encodeURIComponent(planId)}`);
                const json = await res.json();
                if (res.ok) treePayload = { treeData: json.treeData || [], layout: json.layout || null };
            } catch (_) { }

            try {
                let executionSnapshot = execution;
                let execTasks = Array.isArray(executionSnapshot?.tasks) ? executionSnapshot.tasks : [];
                if (!execTasks.length) {
                    const genRes = await ctx.cfg.fetchWithSession(`${ctx.cfg.API_BASE_URL}/execution/generate-from-plan`, {
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
                    const layoutRes = await ctx.cfg.fetchWithSession(`${ctx.cfg.API_BASE_URL}/plan/layout`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ execution: executionSnapshot, ideaId, planId }),
                    });
                    const layoutJson = await layoutRes.json().catch(() => ({}));
                    if (layoutRes.ok && layoutJson?.layout) {
                        executionLayout = layoutJson.layout;
                        ctx.setExecutionGraphPayload({
                            treeData: Array.isArray(layoutJson.layout?.treeData) ? layoutJson.layout.treeData : [],
                            layout: layoutJson.layout?.layout || null,
                        });
                        ctx.invalidateExecutionGraphRender();
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
        seedExecutionState(ctx, treePayload.treeData, executionForRestore, outputs, {
            skipOutputSeed: hasPersistedTimeline,
        });
        if (hasPersistedTimeline) {
            ctx.replayPersistedStepEvents(stepEvents);
        }
        if (ctx.getExecutionGraphPayload()?.layout) {
            ctx.scheduleExecutionGraphRender({ force: true, allowInactive: true, delays: [0, 100, 320, 700] });
        }
        if (ctx.getActiveStage() === 'execute') ctx.renderExecuteStream();
        ctx.refreshExecutionRuntimeStatus({ ideaId, planId });

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

        try {
            const stageStatus = String(research.stageStatus || '').trim().toLowerCase();
            if (stageStatus === 'idle') {
                await ctx.api.runResearch(researchId);
            }
        } catch (e) {
            const msg = String(e?.message || '');
            if (!/already running|409/.test(msg)) console.warn('runResearch failed', e);
        }
    }

    const INIT_EVENT_BRIDGES_SRC_B64 = 'ICAgICAgICAvLyBVcGRhdGUgc3RhZ2Ugc3RhdGUgYmFzZWQgb24gbGl2ZSBwaXBlbGluZSBldmVudHMuCiAgICAgICAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignbWFhcnM6aWRlYS1zdGFydCcsICgpID0+IHNldFN0YWdlU3RhcnRlZCgncmVmaW5lJywgdHJ1ZSkpOwogICAgICAgIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ21hYXJzOnBsYW4tc3RhcnQnLCAoKSA9PiBzZXRTdGFnZVN0YXJ0ZWQoJ3BsYW4nLCB0cnVlKSk7CiAgICAgICAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignbWFhcnM6dGFzay1zdGFydCcsICgpID0+IHsKICAgICAgICAgICAgc2V0U3RhZ2VTdGFydGVkKCdleGVjdXRlJywgdHJ1ZSk7CiAgICAgICAgICAgIGlmIChhY3RpdmVTdGFnZSA9PT0gJ2V4ZWN1dGUnKSB7CiAgICAgICAgICAgICAgICBzY2hlZHVsZUV4ZWN1dGlvbkdyYXBoUmVuZGVyKHsgZm9yY2U6IHRydWUsIGRlbGF5czogWzAsIDEwMCwgMzIwLCA3MDBdIH0pOwogICAgICAgICAgICAgICAgcmVuZGVyRXhlY3V0ZVN0cmVhbSgpOwogICAgICAgICAgICB9CiAgICAgICAgfSk7CiAgICAgICAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignbWFhcnM6cGFwZXItc3RhcnQnLCAoKSA9PiBzZXRTdGFnZVN0YXJ0ZWQoJ3BhcGVyJywgdHJ1ZSkpOwogICAgICAgIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ21hYXJzOnRhc2stc3RhcnQnLCAoKSA9PiByZWZyZXNoRXhlY3V0aW9uUnVudGltZVN0YXR1cygpKTsKCiAgICAgICAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignbWFhcnM6cmVzZWFyY2gtc3RhZ2UnLCAoZSkgPT4gewogICAgICAgICAgICBjb25zdCBkID0gZT8uZGV0YWlsIHx8IHt9OwogICAgICAgICAgICBpZiAoZC5yZXNlYXJjaElkICYmIGN1cnJlbnRSZXNlYXJjaElkICYmIGQucmVzZWFyY2hJZCAhPT0gY3VycmVudFJlc2VhcmNoSWQpIHJldHVybjsKICAgICAgICAgICAgY29uc3Qgc3RhZ2UgPSBTdHJpbmcoZC5zdGFnZSB8fCAnJykudHJpbSgpOwogICAgICAgICAgICBjb25zdCBzdGF0dXMgPSBTdHJpbmcoZC5zdGF0dXMgfHwgJycpLnRyaW0oKSB8fCAnaWRsZSc7CiAgICAgICAgICAgIGNvbnN0IGVycm9yID0gU3RyaW5nKGQuZXJyb3IgfHwgJycpLnRyaW0oKTsKICAgICAgICAgICAgaWYgKHN0YWdlICYmIGN1cnJlbnRTdGFnZVN0YXRlW3N0YWdlXSAhPSBudWxsKSB7CiAgICAgICAgICAgICAgICBpZiAoc3RhdHVzID09PSAncnVubmluZycgfHwgc3RhdHVzID09PSAnY29tcGxldGVkJyB8fCBzdGF0dXMgPT09ICdzdG9wcGVkJyB8fCBzdGF0dXMgPT09ICdmYWlsZWQnKSB7CiAgICAgICAgICAgICAgICAgICAgc2V0U3RhZ2VTdGFydGVkKHN0YWdlLCB0cnVlKTsKICAgICAgICAgICAgICAgIH0KICAgICAgICAgICAgICAgIHN0YWdlU3RhdHVzRGV0YWlsc1tzdGFnZV0gPSB7CiAgICAgICAgICAgICAgICAgICAgc3RhdHVzLAogICAgICAgICAgICAgICAgICAgIG1lc3NhZ2U6IGVycm9yIHx8IHN0YXR1cywKICAgICAgICAgICAgICAgIH07CiAgICAgICAgICAgICAgICByZW5kZXJTdGFnZUJ1dHRvbnMoc3RhZ2UpOwogICAgICAgICAgICAgICAgaWYgKHN0YXR1cyA9PT0gJ3J1bm5pbmcnIHx8IHN0YXR1cyA9PT0gJ2NvbXBsZXRlZCcpIHsKICAgICAgICAgICAgICAgICAgICBzZXRBY3RpdmVTdGFnZShzdGFnZSk7CiAgICAgICAgICAgICAgICB9CiAgICAgICAgICAgIH0KICAgICAgICAgICAgZG9jdW1lbnQuZGlzcGF0Y2hFdmVudChuZXcgQ3VzdG9tRXZlbnQoJ21hYXJzOnJlc2VhcmNoLWxpc3QtcmVmcmVzaCcpKTsKICAgICAgICB9KTsKCiAgICAgICAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignbWFhcnM6cmVzZWFyY2gtZXJyb3InLCAoZSkgPT4gewogICAgICAgICAgICBjb25zdCBkID0gZT8uZGV0YWlsIHx8IHt9OwogICAgICAgICAgICBpZiAoZC5yZXNlYXJjaElkICYmIGN1cnJlbnRSZXNlYXJjaElkICYmIGQucmVzZWFyY2hJZCAhPT0gY3VycmVudFJlc2VhcmNoSWQpIHJldHVybjsKICAgICAgICAgICAgaWYgKGQuZXJyb3IpIHsKICAgICAgICAgICAgICAgIGNvbnNvbGUud2FybignUmVzZWFyY2ggZXJyb3I6JywgZC5lcnJvcik7CiAgICAgICAgICAgICAgICBjb25zdCBtc2cgPSBTdHJpbmcoZC5lcnJvciB8fCAnJykudHJpbSgpOwogICAgICAgICAgICAgICAgaWYgKHJlZmluZUxvZ2ljRWwgJiYgIVN0cmluZyhzdGFnZURhdGEucmVmaW5lZCB8fCAnJykudHJpbSgpKSB7CiAgICAgICAgICAgICAgICAgICAgcmVmaW5lTG9naWNFbC5pbm5lckhUTUwgPSBfbWRUb0h0bWwoYD4gUmVmaW5lIGZhaWxlZFxuXG4ke21zZ31gKTsKICAgICAgICAgICAgICAgIH0KICAgICAgICAgICAgfQogICAgICAgIH0pOwoKICAgICAgICAvLyBLZWVwIHNpZGViYXIgbGlzdCBpbiBzeW5jCiAgICAgICAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignbWFhcnM6cmVzZWFyY2gtbGlzdC1yZWZyZXNoJywgKCkgPT4gewogICAgICAgICAgICB3aW5kb3cuTUFBUlM/LnNpZGViYXI/LnJlZnJlc2hSZXNlYXJjaExpc3Q/LigpOwogICAgICAgIH0pOwoKICAgICAgICAvLyBLZWVwIHJlZmluZS9wYXBlciBwYW5lbHMgdXBkYXRlZAogICAgICAgIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ21hYXJzOmlkZWEtY29tcGxldGUnLCAoZSkgPT4gewogICAgICAgICAgICBjb25zdCBkID0gZT8uZGV0YWlsIHx8IHt9OwogICAgICAgICAgICBpZiAoZC5pZGVhKSBzdGFnZURhdGEub3JpZ2luYWxJZGVhID0gU3RyaW5nKGQuaWRlYSB8fCAnJykudHJpbSgpIHx8IHN0YWdlRGF0YS5vcmlnaW5hbElkZWE7CiAgICAgICAgICAgIGlmIChBcnJheS5pc0FycmF5KGQucGFwZXJzKSkgc3RhZ2VEYXRhLnBhcGVycyA9IGQucGFwZXJzOwogICAgICAgICAgICBpZiAodHlwZW9mIGQucmVmaW5lZF9pZGVhID09PSAnc3RyaW5nJykgc3RhZ2VEYXRhLnJlZmluZWQgPSBkLnJlZmluZWRfaWRlYTsKICAgICAgICAgICAgc3RhZ2VEYXRhLnJlZmluZVRoaW5raW5nID0gJyc7CiAgICAgICAgICAgIF9yZW5kZXJSZWZpbmVQYW5lbCgpOwogICAgICAgIH0pOwoKICAgICAgICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdtYWFyczppZGVhLXRoaW5raW5nJywgKGUpID0+IHsKICAgICAgICAgICAgY29uc3QgZCA9IGU/LmRldGFpbCB8fCB7fTsKICAgICAgICAgICAgY29uc3QgY2h1bmsgPSBTdHJpbmcoZC5jaHVuayB8fCAnJykudHJpbSgpOwogICAgICAgICAgICBjb25zdCB0b29sTmFtZSA9IFN0cmluZyhkPy5zY2hlZHVsZUluZm8/LnRvb2xfbmFtZSB8fCAnJykudHJpbSgpOwogICAgICAgICAgICBjb25zdCB0dXJuID0gZD8uc2NoZWR1bGVJbmZvPy50dXJuOwogICAgICAgICAgICBjb25zdCBtYXhUdXJucyA9IGQ/LnNjaGVkdWxlSW5mbz8ubWF4X3R1cm5zOwogICAgICAgICAgICBjb25zdCBwYXJ0cyA9IFtdOwogICAgICAgICAgICBpZiAodG9vbE5hbWUpIHBhcnRzLnB1c2goYFJ1bm5pbmcgdG9vbDogKioke3Rvb2xOYW1lfSoqYCk7CiAgICAgICAgICAgIGlmIChOdW1iZXIuaXNGaW5pdGUodHVybikgJiYgTnVtYmVyLmlzRmluaXRlKG1heFR1cm5zKSkgcGFydHMucHVzaChgVHVybiAke3R1cm59LyR7bWF4VHVybnN9YCk7CiAgICAgICAgICAgIGlmIChjaHVuaykgcGFydHMucHVzaChjaHVuayk7CiAgICAgICAgICAgIGlmICghcGFydHMubGVuZ3RoKSByZXR1cm47CiAgICAgICAgICAgIHN0YWdlRGF0YS5yZWZpbmVUaGlua2luZyA9IHBhcnRzLmpvaW4oJ1xuXG4nKTsKICAgICAgICAgICAgaWYgKCFTdHJpbmcoc3RhZ2VEYXRhLnJlZmluZWQgfHwgJycpLnRyaW0oKSkgewogICAgICAgICAgICAgICAgX3JlbmRlclJlZmluZVBhbmVsKCk7CiAgICAgICAgICAgIH0KICAgICAgICB9KTsKICAgICAgICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdtYWFyczpwYXBlci1jb21wbGV0ZScsIChlKSA9PiB7CiAgICAgICAgICAgIGNvbnN0IGQgPSBlPy5kZXRhaWwgfHwge307CiAgICAgICAgICAgIGlmICh0eXBlb2YgZC5jb250ZW50ID09PSAnc3RyaW5nJykgc3RhZ2VEYXRhLnBhcGVyID0gZC5jb250ZW50OwogICAgICAgICAgICBfcmVuZGVyUGFwZXJQYW5lbCgpOwogICAgICAgIH0pOwoKICAgICAgICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdtYWFyczp0YXNrLXN0YXRlcy11cGRhdGUnLCAoZSkgPT4gewogICAgICAgICAgICBjb25zdCBkID0gZT8uZGV0YWlsIHx8IHt9OwogICAgICAgICAgICBjb25zdCB0YXNrcyA9IEFycmF5LmlzQXJyYXkoZC50YXNrcykgPyBkLnRhc2tzIDogW107CiAgICAgICAgICAgIGlmICghdGFza3MubGVuZ3RoKSByZXR1cm47CiAgICAgICAgICAgIHRhc2tzLmZvckVhY2goKHQpID0+IHsKICAgICAgICAgICAgICAgIGlmICghdD8udGFza19pZCkgcmV0dXJuOwogICAgICAgICAgICAgICAgY29uc3QgaWQgPSBfZW5zdXJlVGFza0luT3JkZXIodC50YXNrX2lkKTsKICAgICAgICAgICAgICAgIF91cHNlcnRUYXNrTWV0YSh0KTsKICAgICAgICAgICAgICAgIGlmICghaWQpIHJldHVybjsKICAgICAgICAgICAgICAgIGNvbnN0IG5leHRTdGF0dXMgPSBTdHJpbmcodC5zdGF0dXMgfHwgJycpOwogICAgICAgICAgICAgICAgY29uc3QgcHJldlN0YXR1cyA9IGV4ZWN1dGVTdGF0ZS5zdGF0dXNlcy5nZXQoaWQpIHx8ICcnOwogICAgICAgICAgICAgICAgZXhlY3V0ZVN0YXRlLnN0YXR1c2VzLnNldChpZCwgbmV4dFN0YXR1cyk7CiAgICAgICAgICAgICAgICAvLyBPbmx5IHVwZGF0ZSBzdGF0dXMgbWFwLCBkb24ndCBhZGQgZHVwbGljYXRlIGRlc2NyaXB0aW9uIG1lc3NhZ2VzCiAgICAgICAgICAgICAgICAvLyBUYXNrIGRlc2NyaXB0aW9ucyBhcmUgc2hvd24gaW4gdGFzay1zdGFydGVkIGV2ZW50LCBzdGF0dXMgY2hhbmdlcyBhcmUgc2hvd24gaW4gc3RhdHVzIGxhYmVscwogICAgICAgICAgICB9KTsKICAgICAgICAgICAgaWYgKGFjdGl2ZVN0YWdlID09PSAnZXhlY3V0ZScpIHsKICAgICAgICAgICAgICAgIHNjaGVkdWxlRXhlY3V0aW9uR3JhcGhSZW5kZXIoKTsKICAgICAgICAgICAgICAgIHJlbmRlckV4ZWN1dGVTdHJlYW0oKTsKICAgICAgICAgICAgfQogICAgICAgIH0pOwoKICAgICAgICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdtYWFyczp0YXNrLXRoaW5raW5nJywgKGUpID0+IHsKICAgICAgICAgICAgY29uc3QgZCA9IGU/LmRldGFpbCB8fCB7fTsKICAgICAgICAgICAgY29uc3QgdGFza0lkID0gU3RyaW5nKGQudGFza0lkIHx8IGQudGFza19pZCB8fCAnJykudHJpbSgpOwogICAgICAgICAgICBjb25zdCBjaHVuayA9IFN0cmluZyhkLmNodW5rIHx8ICcnKS50cmltKCk7CiAgICAgICAgICAgIGNvbnN0IG9wZXJhdGlvbiA9IFN0cmluZyhkLm9wZXJhdGlvbiB8fCAnRXhlY3V0ZScpLnRyaW0oKSB8fCAnRXhlY3V0ZSc7CiAgICAgICAgICAgIGlmICghdGFza0lkIHx8ICFjaHVuaykgcmV0dXJuOwoKICAgICAgICAgICAgLy8gS2VlcCB2YWxpZGF0aW9uL1N0ZXAtQiBkZXRhaWxzIGluIHRoZSBmaW5hbCBmYWlsdXJlIHN1bW1hcnkgYnViYmxlIG9ubHkuCiAgICAgICAgICAgIGlmICgvXnZhbGlkYXRlJC9pLnRlc3Qob3BlcmF0aW9uKSB8fCAvXnN0ZXAtYiQvaS50ZXN0KG9wZXJhdGlvbikpIHJldHVybjsKCiAgICAgICAgICAgIF9lbnN1cmVUYXNrSW5PcmRlcih0YXNrSWQpOwogICAgICAgICAgICBfc2V0Q3VycmVudEF0dGVtcHQodGFza0lkLCBOdW1iZXIoZC5hdHRlbXB0IHx8IGQ/LnNjaGVkdWxlSW5mbz8uYXR0ZW1wdCkgfHwgX2dldEN1cnJlbnRBdHRlbXB0KHRhc2tJZCkpOwogICAgICAgICAgICBfdXBzZXJ0RXhlY3V0ZVRoaW5raW5nTWVzc2FnZSgKICAgICAgICAgICAgICAgIHRhc2tJZCwKICAgICAgICAgICAgICAgIG9wZXJhdGlvbiwKICAgICAgICAgICAgICAgIGNodW5rLAogICAgICAgICAgICAgICAgZC5zY2hlZHVsZUluZm8gfHwgbnVsbCwKICAgICAgICAgICAgICAgIE51bWJlcihkLmF0dGVtcHQgfHwgZD8uc2NoZWR1bGVJbmZvPy5hdHRlbXB0KSB8fCAwLAogICAgICAgICAgICApOwoKICAgICAgICAgICAgaWYgKGFjdGl2ZVN0YWdlID09PSAnZXhlY3V0ZScpIHsKICAgICAgICAgICAgICAgIHJlbmRlckV4ZWN1dGVTdHJlYW0oKTsKICAgICAgICAgICAgfQogICAgICAgIH0pOwoKICAgICAgICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdtYWFyczp0YXNrLXN0YXJ0ZWQnLCAoZSkgPT4gewogICAgICAgICAgICBjb25zdCBkID0gZT8uZGV0YWlsIHx8IHt9OwogICAgICAgICAgICBjb25zdCB0YXNrSWQgPSBTdHJpbmcoZC50YXNrSWQgfHwgZC50YXNrX2lkIHx8ICcnKS50cmltKCk7CiAgICAgICAgICAgIGlmICghdGFza0lkKSByZXR1cm47CgogICAgICAgICAgICBfZW5zdXJlVGFza0luT3JkZXIodGFza0lkKTsKICAgICAgICAgICAgX3NldEN1cnJlbnRBdHRlbXB0KHRhc2tJZCwgTnVtYmVyKGQuYXR0ZW1wdCkgfHwgX2dldEN1cnJlbnRBdHRlbXB0KHRhc2tJZCkpOwogICAgICAgICAgICBfdXBzZXJ0VGFza01ldGEoewogICAgICAgICAgICAgICAgdGFza19pZDogdGFza0lkLAogICAgICAgICAgICAgICAgdGl0bGU6IFN0cmluZyhkLnRpdGxlIHx8IGQuZGVzY3JpcHRpb24gfHwgdGFza0lkKS50cmltKCkgfHwgdGFza0lkLAogICAgICAgICAgICAgICAgZGVzY3JpcHRpb246IFN0cmluZyhkLmRlc2NyaXB0aW9uIHx8ICcnKS50cmltKCkgfHwgJycsCiAgICAgICAgICAgICAgICBzdGF0dXM6ICdkb2luZycsCiAgICAgICAgICAgIH0pOwoKICAgICAgICAgICAgY29uc3QgbWV0YSA9IF9nZXRUYXNrTWV0YUJ5SWQodGFza0lkKSB8fCB7fTsKICAgICAgICAgICAgX2FwcGVuZEV4ZWN1dGVNZXNzYWdlKHsKICAgICAgICAgICAgICAgIHRhc2tJZCwKICAgICAgICAgICAgICAgIGtpbmQ6ICdzeXN0ZW0nLAogICAgICAgICAgICAgICAgdGl0bGU6IGAke3Rhc2tJZH0gc3RhcnRlZCDCtyBBdHRlbXB0ICR7X2dldEN1cnJlbnRBdHRlbXB0KHRhc2tJZCl9YCwKICAgICAgICAgICAgICAgIGJvZHk6IG1ldGEuZGVzY3JpcHRpb24gfHwgJ1Rhc2sgZXhlY3V0aW9uIHN0YXJ0ZWQnLAogICAgICAgICAgICAgICAgc3RhdHVzOiAnZG9pbmcnLAogICAgICAgICAgICAgICAgYXR0ZW1wdDogX2dldEN1cnJlbnRBdHRlbXB0KHRhc2tJZCksCiAgICAgICAgICAgIH0pOwoKICAgICAgICAgICAgaWYgKGFjdGl2ZVN0YWdlID09PSAnZXhlY3V0ZScpIHsKICAgICAgICAgICAgICAgIHNjaGVkdWxlRXhlY3V0aW9uR3JhcGhSZW5kZXIoKTsKICAgICAgICAgICAgICAgIHJlbmRlckV4ZWN1dGVTdHJlYW0oKTsKICAgICAgICAgICAgfQogICAgICAgIH0pOwoKICAgICAgICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdtYWFyczp0YXNrLW91dHB1dCcsIChlKSA9PiB7CiAgICAgICAgICAgIGNvbnN0IGQgPSBlPy5kZXRhaWwgfHwge307CiAgICAgICAgICAgIGNvbnN0IHRhc2tJZCA9IFN0cmluZyhkLnRhc2tJZCB8fCBkLnRhc2tfaWQgfHwgJycpLnRyaW0oKTsKICAgICAgICAgICAgaWYgKCF0YXNrSWQpIHJldHVybjsKICAgICAgICAgICAgX2Vuc3VyZVRhc2tJbk9yZGVyKHRhc2tJZCk7CiAgICAgICAgICAgIF9zZXRDdXJyZW50QXR0ZW1wdCh0YXNrSWQsIE51bWJlcihkLmF0dGVtcHQpIHx8IF9nZXRDdXJyZW50QXR0ZW1wdCh0YXNrSWQpKTsKICAgICAgICAgICAgY29uc3Qgb3V0cHV0VGV4dCA9IF9zdHJpbmdpZnlPdXRwdXQoZC5vdXRwdXQpOwogICAgICAgICAgICBfcHVzaFJlY2VudE91dHB1dCh0YXNrSWQsIG91dHB1dFRleHQpOwogICAgICAgICAgICBjb25zdCBtZXRhID0gX2dldFRhc2tNZXRhQnlJZCh0YXNrSWQpIHx8IHt9OwogICAgICAgICAgICBjb25zdCBhdHRlbXB0TnVtYmVyID0gX2dldEN1cnJlbnRBdHRlbXB0KHRhc2tJZCk7CiAgICAgICAgICAgIF9hcHBlbmRFeGVjdXRlTWVzc2FnZSh7CiAgICAgICAgICAgICAgICB0YXNrSWQsCiAgICAgICAgICAgICAgICBraW5kOiAnb3V0cHV0JywKICAgICAgICAgICAgICAgIHRpdGxlOiBtZXRhLnRpdGxlIHx8IHRhc2tJZCwKICAgICAgICAgICAgICAgIGJvZHk6IG91dHB1dFRleHQsCiAgICAgICAgICAgICAgICBhdHRlbXB0OiBhdHRlbXB0TnVtYmVyLAogICAgICAgICAgICAgICAgc3RhdHVzOiBleGVjdXRlU3RhdGUuc3RhdHVzZXMuZ2V0KHRhc2tJZCkgfHwgbWV0YS5zdGF0dXMgfHwgJycsCiAgICAgICAgICAgICAgICBkZWR1cGVLZXk6IGBvdXRwdXQ6JHt0YXNrSWR9OiR7YXR0ZW1wdE51bWJlcn06JHtvdXRwdXRUZXh0LnNsaWNlKDAsIDEyMCl9YCwKICAgICAgICAgICAgfSk7CgogICAgICAgICAgICBpZiAoYWN0aXZlU3RhZ2UgPT09ICdleGVjdXRlJykgewogICAgICAgICAgICAgICAgcmVuZGVyRXhlY3V0ZVN0cmVhbSgpOwogICAgICAgICAgICB9CiAgICAgICAgfSk7CgogICAgICAgIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ21hYXJzOnRhc2stY29tcGxldGVkJywgKGUpID0+IHsKICAgICAgICAgICAgY29uc3QgZCA9IGU/LmRldGFpbCB8fCB7fTsKICAgICAgICAgICAgY29uc3QgdGFza0lkID0gU3RyaW5nKGQudGFza0lkIHx8IGQudGFza19pZCB8fCAnJykudHJpbSgpOwogICAgICAgICAgICBpZiAoIXRhc2tJZCkgcmV0dXJuOwoKICAgICAgICAgICAgX3NldEN1cnJlbnRBdHRlbXB0KHRhc2tJZCwgTnVtYmVyKGQuYXR0ZW1wdCkgfHwgX2dldEN1cnJlbnRBdHRlbXB0KHRhc2tJZCkpOwogICAgICAgICAgICBleGVjdXRlU3RhdGUuc3RhdHVzZXMuc2V0KHRhc2tJZCwgJ2RvbmUnKTsKICAgICAgICAgICAgY29uc3QgbWV0YSA9IF9nZXRUYXNrTWV0YUJ5SWQodGFza0lkKSB8fCB7fTsKICAgICAgICAgICAgY29uc3QgdmFsaWRhdGVkID0gISFkLnZhbGlkYXRlZDsKICAgICAgICAgICAgY29uc3QgYXR0ZW1wdE51bWJlciA9IF9nZXRDdXJyZW50QXR0ZW1wdCh0YXNrSWQpOwogICAgICAgICAgICBjb25zdCBib2R5ID0gdmFsaWRhdGVkCiAgICAgICAgICAgICAgICA/IF9idWlsZFZhbGlkYXRpb25TdW1tYXJ5Qm9keSh0YXNrSWQsIGQsIG1ldGEsIHsgc3RhdHVzTGFiZWw6ICdQQVNTJyB9KQogICAgICAgICAgICAgICAgOiAnVGFzayBjb21wbGV0ZWQgc3VjY2Vzc2Z1bGx5Lic7CgogICAgICAgICAgICBfYXBwZW5kRXhlY3V0ZU1lc3NhZ2UoewogICAgICAgICAgICAgICAgdGFza0lkLAogICAgICAgICAgICAgICAga2luZDogJ3N5c3RlbScsCiAgICAgICAgICAgICAgICB0aXRsZTogYCR7dGFza0lkfSAke3ZhbGlkYXRlZCA/ICd2YWxpZGF0aW9uIHN1bW1hcnknIDogJ2NvbXBsZXRlZCd9IMK3IEF0dGVtcHQgJHthdHRlbXB0TnVtYmVyfWAsCiAgICAgICAgICAgICAgICBib2R5LAogICAgICAgICAgICAgICAgYXR0ZW1wdDogYXR0ZW1wdE51bWJlciwKICAgICAgICAgICAgICAgIHN0YXR1czogJ2RvbmUnLAogICAgICAgICAgICAgICAgZGVkdXBlS2V5OiB2YWxpZGF0ZWQgPyBgdmFsaWRhdGlvbi1wYXNzOiR7dGFza0lkfToke2F0dGVtcHROdW1iZXJ9YCA6ICcnLAogICAgICAgICAgICB9KTsKCiAgICAgICAgICAgIGlmIChhY3RpdmVTdGFnZSA9PT0gJ2V4ZWN1dGUnKSB7CiAgICAgICAgICAgICAgICBzY2hlZHVsZUV4ZWN1dGlvbkdyYXBoUmVuZGVyKCk7CiAgICAgICAgICAgICAgICByZW5kZXJFeGVjdXRlU3RyZWFtKCk7CiAgICAgICAgICAgIH0KICAgICAgICB9KTsKCiAgICAgICAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignbWFhcnM6ZXhlY3V0aW9uLXN5bmMnLCAoZSkgPT4gewogICAgICAgICAgICBjb25zdCBkID0gZT8uZGV0YWlsIHx8IHt9OwogICAgICAgICAgICBjb25zdCB0YXNrcyA9IEFycmF5LmlzQXJyYXkoZC50YXNrcykgPyBkLnRhc2tzIDogW107CiAgICAgICAgICAgIGlmICghdGFza3MubGVuZ3RoKSByZXR1cm47CiAgICAgICAgICAgIHRhc2tzLmZvckVhY2goKHRhc2spID0+IHsKICAgICAgICAgICAgICAgIF91cHNlcnRUYXNrTWV0YSh0YXNrKTsKICAgICAgICAgICAgICAgIGNvbnN0IGlkID0gX2Vuc3VyZVRhc2tJbk9yZGVyKHRhc2sudGFza19pZCk7CiAgICAgICAgICAgICAgICBpZiAoIWlkKSByZXR1cm47CiAgICAgICAgICAgICAgICBjb25zdCBuZXh0U3RhdHVzID0gU3RyaW5nKHRhc2suc3RhdHVzIHx8ICcnKTsKICAgICAgICAgICAgICAgIGlmIChuZXh0U3RhdHVzKSBleGVjdXRlU3RhdGUuc3RhdHVzZXMuc2V0KGlkLCBuZXh0U3RhdHVzKTsKICAgICAgICAgICAgfSk7CiAgICAgICAgICAgIGlmIChhY3RpdmVTdGFnZSA9PT0gJ2V4ZWN1dGUnKSB7CiAgICAgICAgICAgICAgICBzY2hlZHVsZUV4ZWN1dGlvbkdyYXBoUmVuZGVyKCk7CiAgICAgICAgICAgICAgICByZW5kZXJFeGVjdXRlU3RyZWFtKCk7CiAgICAgICAgICAgIH0KICAgICAgICAgICAgcmVmcmVzaEV4ZWN1dGlvblJ1bnRpbWVTdGF0dXMoKTsKICAgICAgICB9KTsKCiAgICAgICAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignbWFhcnM6dGFzay1jb21wbGV0ZScsIChlKSA9PiB7CiAgICAgICAgICAgIGNvbnN0IGQgPSBlPy5kZXRhaWwgfHwge307CiAgICAgICAgICAgIGNvbnN0IHRhc2tJZCA9IFN0cmluZyhkLnRhc2tJZCB8fCBkLnRhc2tfaWQgfHwgJycpLnRyaW0oKTsKICAgICAgICAgICAgaWYgKCF0YXNrSWQpIHJldHVybjsKICAgICAgICAgICAgX3NldEN1cnJlbnRBdHRlbXB0KHRhc2tJZCwgTnVtYmVyKGQuYXR0ZW1wdCkgfHwgX2dldEN1cnJlbnRBdHRlbXB0KHRhc2tJZCkpOwogICAgICAgICAgICBjb25zdCBtZXRhID0gX2dldFRhc2tNZXRhQnlJZCh0YXNrSWQpIHx8IHt9OwogICAgICAgICAgICBfYXBwZW5kRXhlY3V0ZU1lc3NhZ2UoewogICAgICAgICAgICAgICAgdGFza0lkLAogICAgICAgICAgICAgICAga2luZDogJ2Fzc2lzdGFudCcsCiAgICAgICAgICAgICAgICB0aXRsZTogYCR7bWV0YS50aXRsZSB8fCB0YXNrSWR9IMK3IEF0dGVtcHQgJHtfZ2V0Q3VycmVudEF0dGVtcHQodGFza0lkKX1gLAogICAgICAgICAgICAgICAgYm9keTogJ1N0ZXAgY29tcGxldGVkLicsCiAgICAgICAgICAgICAgICBhdHRlbXB0OiBfZ2V0Q3VycmVudEF0dGVtcHQodGFza0lkKSwKICAgICAgICAgICAgICAgIHN0YXR1czogJ2RvbmUnLAogICAgICAgICAgICB9KTsKICAgICAgICAgICAgZXhlY3V0ZVN0YXRlLnN0YXR1c2VzLnNldCh0YXNrSWQsICdkb25lJyk7CiAgICAgICAgICAgIGlmIChhY3RpdmVTdGFnZSA9PT0gJ2V4ZWN1dGUnKSB7CiAgICAgICAgICAgICAgICBzY2hlZHVsZUV4ZWN1dGlvbkdyYXBoUmVuZGVyKCk7CiAgICAgICAgICAgICAgICByZW5kZXJFeGVjdXRlU3RyZWFtKCk7CiAgICAgICAgICAgIH0KICAgICAgICAgICAgcmVmcmVzaEV4ZWN1dGlvblJ1bnRpbWVTdGF0dXMoKTsKICAgICAgICB9KTsKCiAgICAgICAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignbWFhcnM6dGFzay1lcnJvcicsIChlKSA9PiB7CiAgICAgICAgICAgIGNvbnN0IGQgPSBlPy5kZXRhaWwgfHwge307CiAgICAgICAgICAgIC8vIGZhdGFsPXRydWUgY29tZXMgZnJvbSBfdHJpZ2dlcl9mYWlsX2Zhc3QgYWZ0ZXIgX3JldHJ5X29yX2ZhaWwgYWxyZWFkeSBlbWl0dGVkCiAgICAgICAgICAgIC8vIGEgZnVsbCB2YWxpZGF0aW9uIHN1bW1hcnkg4oCUIHNraXAgdG8gYXZvaWQgZHVwbGljYXRlIGJ1YmJsZQogICAgICAgICAgICBpZiAoZC5mYXRhbCA9PT0gdHJ1ZSkgcmV0dXJuOwogICAgICAgICAgICBjb25zdCB0YXNrSWQgPSBTdHJpbmcoZC50YXNrSWQgfHwgZC50YXNrX2lkIHx8ICcnKS50cmltKCk7CiAgICAgICAgICAgIGNvbnN0IGVycm9yVGV4dCA9IFN0cmluZyhkLmVycm9yIHx8ICcnKS50cmltKCk7CiAgICAgICAgICAgIGNvbnN0IHBoYXNlID0gU3RyaW5nKGQucGhhc2UgfHwgJycpLnRyaW0oKTsKICAgICAgICAgICAgY29uc3QgYXR0ZW1wdCA9IE51bWJlcihkLmF0dGVtcHQpOwogICAgICAgICAgICBjb25zdCBtYXhBdHRlbXB0cyA9IE51bWJlcihkLm1heEF0dGVtcHRzKTsKICAgICAgICAgICAgY29uc3Qgd2lsbFJldHJ5ID0gZC53aWxsUmV0cnkgPT09IHRydWU7CiAgICAgICAgICAgIGlmICghdGFza0lkICYmICFlcnJvclRleHQpIHJldHVybjsKICAgICAgICAgICAgY29uc3QgbWV0YSA9IF9nZXRUYXNrTWV0YUJ5SWQodGFza0lkKSB8fCB7fTsKICAgICAgICAgICAgY29uc3QgbWVzc2FnZUF0dGVtcHQgPSBOdW1iZXIuaXNGaW5pdGUoYXR0ZW1wdCkgPyBhdHRlbXB0IDogX2dldEN1cnJlbnRBdHRlbXB0KHRhc2tJZCk7CiAgICAgICAgICAgIF9zZXRDdXJyZW50QXR0ZW1wdCh0YXNrSWQsIG1lc3NhZ2VBdHRlbXB0KTsKICAgICAgICAgICAgY29uc3QgZGV0YWlsUGFydHMgPSBbXTsKICAgICAgICAgICAgaWYgKHBoYXNlKSBkZXRhaWxQYXJ0cy5wdXNoKGBQaGFzZTogJHtwaGFzZX1gKTsKICAgICAgICAgICAgaWYgKE51bWJlci5pc0Zpbml0ZShhdHRlbXB0KSAmJiBOdW1iZXIuaXNGaW5pdGUobWF4QXR0ZW1wdHMpKSB7CiAgICAgICAgICAgICAgICBkZXRhaWxQYXJ0cy5wdXNoKGBBdHRlbXB0ICR7YXR0ZW1wdH0vJHttYXhBdHRlbXB0c31gKTsKICAgICAgICAgICAgfQogICAgICAgICAgICBpZiAodHlwZW9mIGQud2lsbFJldHJ5ID09PSAnYm9vbGVhbicpIHsKICAgICAgICAgICAgICAgIGRldGFpbFBhcnRzLnB1c2god2lsbFJldHJ5ID8gJ1JldHJ5IHNjaGVkdWxlZCcgOiAnTm8gbW9yZSBhdXRvbWF0aWMgcmV0cmllcycpOwogICAgICAgICAgICB9CiAgICAgICAgICAgIGNvbnN0IGRldGFpbFByZWZpeCA9IGRldGFpbFBhcnRzLmxlbmd0aCA/IGAke2RldGFpbFBhcnRzLmpvaW4oJyDCtyAnKX1cbmAgOiAnJzsKICAgICAgICAgICAgY29uc3QgdGVybWluYWxTdGF0dXMgPSBwaGFzZSA9PT0gJ3ZhbGlkYXRpb24nID8gJ3ZhbGlkYXRpb24tZmFpbGVkJyA6ICdleGVjdXRpb24tZmFpbGVkJzsKICAgICAgICAgICAgY29uc3QgY3VycmVudFN0YXR1cyA9IHRhc2tJZCA/IChleGVjdXRlU3RhdGUuc3RhdHVzZXMuZ2V0KHRhc2tJZCkgfHwgJycpIDogJyc7CiAgICAgICAgICAgIGNvbnN0IG5leHRTdGF0dXMgPSB3aWxsUmV0cnkgPyAoY3VycmVudFN0YXR1cyB8fCAnZG9pbmcnKSA6IHRlcm1pbmFsU3RhdHVzOwogICAgICAgICAgICBjb25zdCBpc1ZhbGlkYXRpb25QaGFzZSA9IHBoYXNlID09PSAndmFsaWRhdGlvbic7CiAgICAgICAgICAgIGNvbnN0IGJvZHkgPSBpc1ZhbGlkYXRpb25QaGFzZQogICAgICAgICAgICAgICAgPyBfYnVpbGRWYWxpZGF0aW9uU3VtbWFyeUJvZHkodGFza0lkLCBkLCBtZXRhLCB7IHN0YXR1c0xhYmVsOiAnRkFJTCcgfSkKICAgICAgICAgICAgICAgIDogYCR7ZGV0YWlsUHJlZml4fSR7ZXJyb3JUZXh0IHx8ICdVbmtub3duIGV4ZWN1dGlvbiBlcnJvci4nfWA7CiAgICAgICAgICAgIF9hcHBlbmRFeGVjdXRlTWVzc2FnZSh7CiAgICAgICAgICAgICAgICB0YXNrSWQ6IHRhc2tJZCB8fCAnJywKICAgICAgICAgICAgICAgIGtpbmQ6IGlzVmFsaWRhdGlvblBoYXNlID8gJ2Vycm9yJyA6ICh3aWxsUmV0cnkgPyAnc3lzdGVtJyA6ICdlcnJvcicpLAogICAgICAgICAgICAgICAgdGl0bGU6IGlzVmFsaWRhdGlvblBoYXNlCiAgICAgICAgICAgICAgICAgICAgPyBgJHttZXRhLnRpdGxlIHx8IHRhc2tJZCB8fCAnVGFzayd9IMK3IFZhbGlkYXRpb24gZmFpbGVkIMK3IEF0dGVtcHQgJHttZXNzYWdlQXR0ZW1wdH1gCiAgICAgICAgICAgICAgICAgICAgOiBgJHttZXRhLnRpdGxlIHx8IHRhc2tJZCB8fCAod2lsbFJldHJ5ID8gJ1JldHJ5aW5nIFRhc2snIDogJ0V4ZWN1dGlvbiBFcnJvcicpfSDCtyBBdHRlbXB0ICR7bWVzc2FnZUF0dGVtcHR9YCwKICAgICAgICAgICAgICAgIGJvZHksCiAgICAgICAgICAgICAgICBhdHRlbXB0OiBtZXNzYWdlQXR0ZW1wdCwKICAgICAgICAgICAgICAgIHN0YXR1czogdGFza0lkID8gbmV4dFN0YXR1cyA6IHRlcm1pbmFsU3RhdHVzLAogICAgICAgICAgICAgICAgZGVkdXBlS2V5OiBpc1ZhbGlkYXRpb25QaGFzZSA/IGB2YWxpZGF0aW9uLWZhaWw6JHt0YXNrSWR9OiR7bWVzc2FnZUF0dGVtcHR9YCA6ICcnLAogICAgICAgICAgICB9KTsKICAgICAgICAgICAgaWYgKHRhc2tJZCkgZXhlY3V0ZVN0YXRlLnN0YXR1c2VzLnNldCh0YXNrSWQsIG5leHRTdGF0dXMpOwogICAgICAgICAgICBpZiAoYWN0aXZlU3RhZ2UgPT09ICdleGVjdXRlJykgcmVuZGVyRXhlY3V0ZVN0cmVhbSgpOwogICAgICAgICAgICByZWZyZXNoRXhlY3V0aW9uUnVudGltZVN0YXR1cygpOwogICAgICAgIH0pOwoKICAgICAgICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdtYWFyczphdHRlbXB0LXJldHJ5JywgKGUpID0+IHsKICAgICAgICAgICAgY29uc3QgZCA9IGU/LmRldGFpbCB8fCB7fTsKICAgICAgICAgICAgY29uc3QgdGFza0lkID0gU3RyaW5nKGQudGFza0lkIHx8IGQudGFza19pZCB8fCAnJykudHJpbSgpOwogICAgICAgICAgICBpZiAoIXRhc2tJZCkgcmV0dXJuOwogICAgICAgICAgICBfZW5zdXJlVGFza0luT3JkZXIodGFza0lkKTsKICAgICAgICAgICAgY29uc3QgcGhhc2UgPSBTdHJpbmcoZC5waGFzZSB8fCAnJykudHJpbSgpIHx8ICdleGVjdXRpb24nOwogICAgICAgICAgICBjb25zdCByZWFzb24gPSBTdHJpbmcoZC5yZWFzb24gfHwgJycpLnRyaW0oKSB8fCAnUmV0cnkgcmVxdWVzdGVkJzsKICAgICAgICAgICAgY29uc3QgYXR0ZW1wdCA9IE51bWJlcihkLmF0dGVtcHQpOwogICAgICAgICAgICBjb25zdCBuZXh0QXR0ZW1wdCA9IE51bWJlcihkLm5leHRBdHRlbXB0KTsKICAgICAgICAgICAgY29uc3QgbWF4QXR0ZW1wdHMgPSBOdW1iZXIoZC5tYXhBdHRlbXB0cyk7CiAgICAgICAgICAgIGNvbnN0IGRldGFpbFBhcnRzID0gW2BQaGFzZTogJHtwaGFzZX1gXTsKICAgICAgICAgICAgaWYgKE51bWJlci5pc0Zpbml0ZShhdHRlbXB0KSAmJiBOdW1iZXIuaXNGaW5pdGUobmV4dEF0dGVtcHQpICYmIE51bWJlci5pc0Zpbml0ZShtYXhBdHRlbXB0cykpIHsKICAgICAgICAgICAgICAgIGRldGFpbFBhcnRzLnB1c2goYFJldHJ5ICR7bmV4dEF0dGVtcHR9LyR7bWF4QXR0ZW1wdHN9IChmYWlsZWQgJHthdHRlbXB0fS8ke21heEF0dGVtcHRzfSlgKTsKICAgICAgICAgICAgfQogICAgICAgICAgICBjb25zdCBmYWlsZWRBdHRlbXB0ID0gTnVtYmVyLmlzRmluaXRlKGF0dGVtcHQpID8gYXR0ZW1wdCA6IF9nZXRDdXJyZW50QXR0ZW1wdCh0YXNrSWQpOwogICAgICAgICAgICBjb25zdCB1cGNvbWluZ0F0dGVtcHQgPSBOdW1iZXIuaXNGaW5pdGUobmV4dEF0dGVtcHQpID8gbmV4dEF0dGVtcHQgOiBmYWlsZWRBdHRlbXB0ICsgMTsKICAgICAgICAgICAgY29uc3QgdmFsaWRhdGlvblN1bW1hcnkgPSBkPy5kZWNpc2lvbj8udmFsaWRhdGlvblN1bW1hcnkgfHwge307CiAgICAgICAgICAgIGNvbnN0IGRpcmVjdFJlYXNvblJhdyA9IFN0cmluZyh2YWxpZGF0aW9uU3VtbWFyeT8uZGlyZWN0UmVhc29uIHx8ICcnKS50cmltKCk7CiAgICAgICAgICAgIGNvbnN0IGRpcmVjdFJlYXNvbiA9IGRpcmVjdFJlYXNvblJhdyB8fCBfZXh0cmFjdFZhbGlkYXRpb25EaXJlY3RSZWFzb24ocmVhc29uKTsKICAgICAgICAgICAgY29uc3QgYm9keSA9IHBoYXNlID09PSAndmFsaWRhdGlvbicKICAgICAgICAgICAgICAgID8gYERpcmVjdCByZWFzb246ICR7ZGlyZWN0UmVhc29uIHx8ICdWYWxpZGF0aW9uIGZhaWxlZCd9XG4ke2RldGFpbFBhcnRzLmpvaW4oJyDCtyAnKX1cbiR7cmVhc29ufWAKICAgICAgICAgICAgICAgIDogYCR7ZGV0YWlsUGFydHMuam9pbignIMK3ICcpfVxuJHtyZWFzb259YDsKICAgICAgICAgICAgX2FwcGVuZEV4ZWN1dGVNZXNzYWdlKHsKICAgICAgICAgICAgICAgIHRhc2tJZCwKICAgICAgICAgICAgICAgIGtpbmQ6ICdzeXN0ZW0nLAogICAgICAgICAgICAgICAgdGl0bGU6IGAke3Rhc2tJZH0gcmV0cnlpbmcgwrcgQXR0ZW1wdCAke2ZhaWxlZEF0dGVtcHR9YCwKICAgICAgICAgICAgICAgIGJvZHksCiAgICAgICAgICAgICAgICBhdHRlbXB0OiBmYWlsZWRBdHRlbXB0LAogICAgICAgICAgICAgICAgc3RhdHVzOiBleGVjdXRlU3RhdGUuc3RhdHVzZXMuZ2V0KHRhc2tJZCkgfHwgJ2V4ZWN1dGlvbi1mYWlsZWQnLAogICAgICAgICAgICAgICAgZGVkdXBlS2V5OiBgcmV0cnk6JHt0YXNrSWR9OiR7cGhhc2V9OiR7ZmFpbGVkQXR0ZW1wdH06JHt1cGNvbWluZ0F0dGVtcHR9YCwKICAgICAgICAgICAgfSk7CiAgICAgICAgICAgIGV4ZWN1dGVTdGF0ZS5hdHRlbXB0RXhwYW5kZWRCeUlkLnNldChfZ2V0QXR0ZW1wdEtleSh0YXNrSWQsIGZhaWxlZEF0dGVtcHQpLCBmYWxzZSk7CiAgICAgICAgICAgIF9zZXRDdXJyZW50QXR0ZW1wdCh0YXNrSWQsIHVwY29taW5nQXR0ZW1wdCk7CiAgICAgICAgICAgIGV4ZWN1dGVTdGF0ZS5hdHRlbXB0RXhwYW5kZWRCeUlkLnNldChfZ2V0QXR0ZW1wdEtleSh0YXNrSWQsIHVwY29taW5nQXR0ZW1wdCksIHRydWUpOwogICAgICAgICAgICBpZiAoYWN0aXZlU3RhZ2UgPT09ICdleGVjdXRlJykgcmVuZGVyRXhlY3V0ZVN0cmVhbSgpOwogICAgICAgIH0pOwoKICAgICAgICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdtYWFyczp0YXNrLXN0ZXAtYicsIChlKSA9PiB7CiAgICAgICAgICAgIGNvbnN0IGQgPSBlPy5kZXRhaWwgfHwge307CiAgICAgICAgICAgIGNvbnN0IHRhc2tJZCA9IFN0cmluZyhkLnRhc2tJZCB8fCBkLnRhc2tfaWQgfHwgJycpLnRyaW0oKTsKICAgICAgICAgICAgaWYgKCF0YXNrSWQpIHJldHVybjsKICAgICAgICAgICAgX2Vuc3VyZVRhc2tJbk9yZGVyKHRhc2tJZCk7CiAgICAgICAgICAgIGNvbnN0IGF0dGVtcHQgPSBOdW1iZXIoZC5hdHRlbXB0KSB8fCBfZ2V0Q3VycmVudEF0dGVtcHQodGFza0lkKTsKICAgICAgICAgICAgX3NldEN1cnJlbnRBdHRlbXB0KHRhc2tJZCwgYXR0ZW1wdCk7CiAgICAgICAgICAgIGV4ZWN1dGVTdGF0ZS5sYXRlc3RTdGVwQkJ5VGFzay5zZXQodGFza0lkLCB7CiAgICAgICAgICAgICAgICBzaG91bGRBZGp1c3Q6IGQuc2hvdWxkQWRqdXN0ID09PSB0cnVlLAogICAgICAgICAgICAgICAgaW1tdXRhYmxlSW1wYWN0ZWQ6IGQuaW1tdXRhYmxlSW1wYWN0ZWQgPT09IHRydWUsCiAgICAgICAgICAgICAgICBwYXRjaFN1bW1hcnk6IFN0cmluZyhkLnBhdGNoU3VtbWFyeSB8fCAnJykudHJpbSgpLAogICAgICAgICAgICAgICAgcmVhc29uaW5nOiBTdHJpbmcoZC5yZWFzb25pbmcgfHwgJycpLnRyaW0oKSwKICAgICAgICAgICAgfSk7CiAgICAgICAgfSk7CgogICAgICAgIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ21hYXJzOmV4ZWN1dGlvbi1ydW50aW1lLXN0YXR1cycsIChlKSA9PiB7CiAgICAgICAgICAgIHJlbmRlckV4ZWN1dGlvblJ1bnRpbWVTdGF0dXMoZT8uZGV0YWlsIHx8IHt9KTsKICAgICAgICB9KTsKCiAgICAgICAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignbWFhcnM6ZXhlY3V0aW9uLWxheW91dCcsIChlKSA9PiB7CiAgICAgICAgICAgIGNvbnN0IGQgPSBlPy5kZXRhaWwgfHwge307CiAgICAgICAgICAgIGNvbnN0IHRyZWVEYXRhID0gQXJyYXkuaXNBcnJheShkPy5sYXlvdXQ/LnRyZWVEYXRhKSA/IGQubGF5b3V0LnRyZWVEYXRhIDogW107CiAgICAgICAgICAgIGNvbnN0IGdyYXBoTGF5b3V0ID0gZD8ubGF5b3V0Py5sYXlvdXQgfHwgbnVsbDsKICAgICAgICAgICAgaWYgKCF0cmVlRGF0YS5sZW5ndGggfHwgIWdyYXBoTGF5b3V0KSByZXR1cm47CiAgICAgICAgICAgIGV4ZWN1dGlvbkdyYXBoUGF5bG9hZCA9IHsgdHJlZURhdGEsIGxheW91dDogZ3JhcGhMYXlvdXQgfTsKICAgICAgICAgICAgaW52YWxpZGF0ZUV4ZWN1dGlvbkdyYXBoUmVuZGVyKCk7CiAgICAgICAgICAgIHRyZWVEYXRhLmZvckVhY2goX3Vwc2VydFRhc2tNZXRhKTsKICAgICAgICAgICAgaWYgKGFjdGl2ZVN0YWdlID09PSAnZXhlY3V0ZScpIHsKICAgICAgICAgICAgICAgIHNjaGVkdWxlRXhlY3V0aW9uR3JhcGhSZW5kZXIoeyBmb3JjZTogdHJ1ZSwgZGVsYXlzOiBbMCwgMTAwLCAzMjAsIDcwMF0gfSk7CiAgICAgICAgICAgICAgICByZW5kZXJFeGVjdXRlU3RyZWFtKCk7CiAgICAgICAgICAgIH0KICAgICAgICB9KTsKCiAgICAgICAgd2luZG93LmFkZEV2ZW50TGlzdGVuZXIoJ3BhZ2VzaG93JywgKCkgPT4gewogICAgICAgICAgICBzY2hlZHVsZUV4ZWN1dGlvbkdyYXBoUmVuZGVyKHsgZm9yY2U6IHRydWUsIGFsbG93SW5hY3RpdmU6IHRydWUsIGRlbGF5czogWzAsIDEyMCwgMzYwLCA5MDBdIH0pOwogICAgICAgIH0pOwoKICAgICAgICB3aW5kb3cuYWRkRXZlbnRMaXN0ZW5lcigncmVzaXplJywgKCkgPT4gewogICAgICAgICAgICBpZiAoYWN0aXZlU3RhZ2UgIT09ICdleGVjdXRlJykgcmV0dXJuOwogICAgICAgICAgICBzY2hlZHVsZUV4ZWN1dGlvbkdyYXBoUmVuZGVyKHsgZm9yY2U6IHRydWUsIGRlbGF5czogWzAsIDEyMF0gfSk7CiAgICAgICAgfSk7CgogICAgICAgIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ3Zpc2liaWxpdHljaGFuZ2UnLCAoKSA9PiB7CiAgICAgICAgICAgIGlmIChkb2N1bWVudC52aXNpYmlsaXR5U3RhdGUgIT09ICd2aXNpYmxlJykgcmV0dXJuOwogICAgICAgICAgICBzY2hlZHVsZUV4ZWN1dGlvbkdyYXBoUmVuZGVyKHsKICAgICAgICAgICAgICAgIGZvcmNlOiB0cnVlLAogICAgICAgICAgICAgICAgYWxsb3dJbmFjdGl2ZTogYWN0aXZlU3RhZ2UgIT09ICdleGVjdXRlJywKICAgICAgICAgICAgICAgIGRlbGF5czogWzAsIDEyMCwgMzYwXSwKICAgICAgICAgICAgfSk7CiAgICAgICAgfSk7CiAgICB9Cgo=';

    function initEventBridges(ctx) {
        if (!ctx) return;
        window.MAARS = window.MAARS || {};
        if (window.MAARS.__researchEventBridgesBound) return;
        window.MAARS.__researchEventBridgesBound = true;

        document.addEventListener('maars:idea-start', () => ctx.setStageStarted('refine', true));
        document.addEventListener('maars:plan-start', () => ctx.setStageStarted('plan', true));
        document.addEventListener('maars:task-start', () => {
            ctx.setStageStarted('execute', true);
            if (ctx.getActiveStage() === 'execute') {
                ctx.scheduleExecutionGraphRender({ force: true, delays: [0, 100, 320, 700] });
                ctx.renderExecuteStream();
            }
            ctx.refreshExecutionRuntimeStatus();
        });
        document.addEventListener('maars:paper-start', () => ctx.setStageStarted('paper', true));

        document.addEventListener('maars:research-stage', (e) => {
            const d = e?.detail || {};
            if (d.researchId && ctx.currentResearchId && d.researchId !== ctx.currentResearchId) return;
            const stage = String(d.stage || '').trim();
            const status = String(d.status || '').trim() || 'idle';
            const error = String(d.error || '').trim();
            if (!stage) return;

            const details = ctx.getStageStatusDetails();
            if (details?.[stage] != null) {
                if (status === 'running' || status === 'completed' || status === 'stopped' || status === 'failed') {
                    ctx.setStageStarted(stage, true);
                }
                ctx.setStageStatusDetails({
                    ...details,
                    [stage]: { status, message: error || status },
                });
                ctx.renderStageButtons(stage);
                if (status === 'running' || status === 'completed') {
                    ctx.setActiveStage(stage);
                }
            }
            document.dispatchEvent(new CustomEvent('maars:research-list-refresh'));
        });

        document.addEventListener('maars:research-list-refresh', () => {
            window.MAARS?.sidebar?.refreshResearchList?.();
        });

        document.addEventListener('maars:idea-complete', (e) => {
            const d = e?.detail || {};
            if (d.idea) ctx.stageData.originalIdea = String(d.idea || '').trim() || ctx.stageData.originalIdea;
            if (Array.isArray(d.papers)) ctx.stageData.papers = d.papers;
            if (typeof d.refined_idea === 'string') ctx.stageData.refined = d.refined_idea;
            ctx.stageData.refineThinking = '';
            ctx.renderRefinePanel();
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
            ctx.stageData.refineThinking = parts.join('\n\n');
            if (!String(ctx.stageData.refined || '').trim()) ctx.renderRefinePanel();
        });

        document.addEventListener('maars:paper-complete', (e) => {
            const d = e?.detail || {};
            if (typeof d.content === 'string') ctx.stageData.paper = d.content;
            ctx.renderPaperPanel();
        });

        document.addEventListener('maars:task-states-update', (e) => {
            const d = e?.detail || {};
            const tasks = Array.isArray(d.tasks) ? d.tasks : [];
            if (!tasks.length) return;
            tasks.forEach((t) => {
                if (!t?.task_id) return;
                const id = ctx.ensureTaskInOrder(t.task_id);
                ctx.upsertTaskMeta(t);
                if (!id) return;
                ctx.executeState.statuses.set(id, String(t.status || ''));
            });
            if (ctx.getActiveStage() === 'execute') {
                ctx.scheduleExecutionGraphRender();
                ctx.renderExecuteStream();
            }
        });

        document.addEventListener('maars:task-thinking', (e) => {
            const d = e?.detail || {};
            const taskId = String(d.taskId || d.task_id || '').trim();
            const chunk = String(d.chunk || '').trim();
            if (!taskId || !chunk) return;
            const attempt = Number(d.attempt || d?.scheduleInfo?.attempt) || ctx.getCurrentAttempt(taskId);
            const operation = String(d.operation || 'Execute').trim() || 'Execute';
            if (/^validate$/i.test(operation) || /^step-b$/i.test(operation)) return;

            ctx.ensureTaskInOrder(taskId);
            ctx.setCurrentAttempt(taskId, attempt);
            ctx.appendExecuteMessage({
                taskId,
                kind: 'assistant',
                title: `${taskId} · ${operation}`,
                body: chunk,
                attempt,
                status: ctx.executeState.statuses.get(taskId) || 'doing',
                dedupeKey: `thinking:${taskId}:${attempt}:${operation}:${chunk.slice(0, 120)}`,
            });
            if (ctx.getActiveStage() === 'execute') ctx.renderExecuteStream();
        });

        document.addEventListener('maars:task-started', (e) => {
            const d = e?.detail || {};
            const taskId = String(d.taskId || d.task_id || '').trim();
            if (!taskId) return;
            const attempt = Number(d.attempt) || ctx.getCurrentAttempt(taskId);
            ctx.ensureTaskInOrder(taskId);
            ctx.setCurrentAttempt(taskId, attempt);
            ctx.upsertTaskMeta({
                task_id: taskId,
                title: String(d.title || d.description || taskId).trim() || taskId,
                description: String(d.description || '').trim(),
                status: 'doing',
            });
            ctx.executeState.statuses.set(taskId, 'doing');
            const meta = ctx.getTaskMetaById(taskId) || {};
            ctx.appendExecuteMessage({
                taskId,
                kind: 'system',
                title: `${taskId} started · Attempt ${ctx.getCurrentAttempt(taskId)}`,
                body: meta.description || 'Task execution started',
                attempt: ctx.getCurrentAttempt(taskId),
                status: 'doing',
            });
            if (ctx.getActiveStage() === 'execute') {
                ctx.scheduleExecutionGraphRender();
                ctx.renderExecuteStream();
            }
        });

        document.addEventListener('maars:task-output', (e) => {
            const d = e?.detail || {};
            const taskId = String(d.taskId || d.task_id || '').trim();
            if (!taskId) return;
            const attempt = Number(d.attempt) || ctx.getCurrentAttempt(taskId);
            const outputText = ctx.stringifyOutput(d.output).trim();
            if (!outputText) return;
            ctx.ensureTaskInOrder(taskId);
            ctx.setCurrentAttempt(taskId, attempt);
            ctx.pushRecentOutput(taskId, outputText);
            const meta = ctx.getTaskMetaById(taskId) || {};
            ctx.appendExecuteMessage({
                taskId,
                kind: 'output',
                title: meta.title || taskId,
                body: outputText,
                attempt: ctx.getCurrentAttempt(taskId),
                status: ctx.executeState.statuses.get(taskId) || meta.status || '',
                dedupeKey: `output:${taskId}:${ctx.getCurrentAttempt(taskId)}:${outputText.slice(0, 120)}`,
            });
            if (ctx.getActiveStage() === 'execute') ctx.renderExecuteStream();
        });

        document.addEventListener('maars:task-completed', (e) => {
            const d = e?.detail || {};
            const taskId = String(d.taskId || d.task_id || '').trim();
            if (!taskId) return;
            const attempt = Number(d.attempt) || ctx.getCurrentAttempt(taskId);
            ctx.setCurrentAttempt(taskId, attempt);
            ctx.executeState.statuses.set(taskId, 'done');
            const meta = ctx.getTaskMetaById(taskId) || {};
            const validated = !d.validated;
            const body = validated
                ? ctx.buildValidationSummaryBody(taskId, d, meta, { statusLabel: 'PASS' })
                : 'Task completed successfully.';
            ctx.appendExecuteMessage({
                taskId,
                kind: 'system',
                title: `${taskId} ${validated ? 'validation summary' : 'completed'} · Attempt ${ctx.getCurrentAttempt(taskId)}`,
                body,
                attempt: ctx.getCurrentAttempt(taskId),
                status: 'done',
                dedupeKey: validated ? `validation-pass:${taskId}:${ctx.getCurrentAttempt(taskId)}` : '',
            });
            if (ctx.getActiveStage() === 'execute') {
                ctx.scheduleExecutionGraphRender();
                ctx.renderExecuteStream();
            }
        });

        document.addEventListener('maars:task-error', (e) => {
            const d = e?.detail || {};
            if (d.fatal === true) return;
            const taskId = String(d.taskId || d.task_id || '').trim();
            const errorText = String(d.error || '').trim();
            if (!taskId && !errorText) return;
            const phase = String(d.phase || '').trim();
            const attempt = Number(d.attempt) || ctx.getCurrentAttempt(taskId);
            const willRetry = d.willRetry === true;
            const messageAttempt = Number.isFinite(attempt) ? attempt : 1;
            if (taskId) ctx.setCurrentAttempt(taskId, messageAttempt);

            const meta = ctx.getTaskMetaById(taskId) || {};
            const terminalStatus = phase === 'validation' ? 'validation-failed' : 'execution-failed';
            const currentStatus = taskId ? (ctx.executeState.statuses.get(taskId) || '') : '';
            const nextStatus = willRetry ? (currentStatus || 'doing') : terminalStatus;
            const isValidationPhase = phase === 'validation';
            const body = isValidationPhase
                ? ctx.buildValidationSummaryBody(taskId, d, meta, { statusLabel: 'FAIL' })
                : (errorText || 'Unknown execution error.');

            ctx.appendExecuteMessage({
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
            if (taskId) ctx.executeState.statuses.set(taskId, nextStatus);
            if (ctx.getActiveStage() === 'execute') ctx.renderExecuteStream();
            ctx.refreshExecutionRuntimeStatus();
        });

        document.addEventListener('maars:attempt-retry', (e) => {
            const d = e?.detail || {};
            const taskId = String(d.taskId || d.task_id || '').trim();
            if (!taskId) return;
            const phase = String(d.phase || '').trim() || 'execution';
            const reason = String(d.reason || '').trim() || 'Retry requested';
            const attempt = Number(d.attempt);
            const nextAttempt = Number(d.nextAttempt);
            const failedAttempt = Number.isFinite(attempt) ? attempt : ctx.getCurrentAttempt(taskId);
            const upcomingAttempt = Number.isFinite(nextAttempt) ? nextAttempt : failedAttempt + 1;
            const validationSummary = d?.decision?.validationSummary || {};
            const directReasonRaw = String(validationSummary?.directReason || '').trim();
            const directReason = directReasonRaw || ctx.extractValidationDirectReason(reason);
            const body = phase === 'validation'
                ? `Direct reason: ${directReason}\n${reason}`
                : reason;

            ctx.appendExecuteMessage({
                taskId,
                kind: 'system',
                title: `${taskId} retrying · Attempt ${failedAttempt}`,
                body,
                attempt: failedAttempt,
                status: ctx.executeState.statuses.get(taskId) || 'execution-failed',
                dedupeKey: `retry:${taskId}:${phase}:${failedAttempt}:${upcomingAttempt}`,
            });
            ctx.setCurrentAttempt(taskId, upcomingAttempt);
            if (ctx.getActiveStage() === 'execute') ctx.renderExecuteStream();
        });

        document.addEventListener('maars:execution-sync', (e) => {
            const d = e?.detail || {};
            const tasks = Array.isArray(d.tasks) ? d.tasks : [];
            if (!tasks.length) return;
            tasks.forEach((task) => {
                ctx.upsertTaskMeta(task);
                const id = ctx.ensureTaskInOrder(task.task_id);
                if (!id) return;
                const nextStatus = String(task.status || '');
                if (nextStatus) ctx.executeState.statuses.set(id, nextStatus);
            });
            if (ctx.getActiveStage() === 'execute') {
                ctx.scheduleExecutionGraphRender();
                ctx.renderExecuteStream();
            }
            ctx.refreshExecutionRuntimeStatus();
        });

        document.addEventListener('maars:execution-layout', (e) => {
            const d = e?.detail || {};
            const treeData = Array.isArray(d?.layout?.treeData) ? d.layout.treeData : [];
            const graphLayout = d?.layout?.layout || null;
            if (!treeData.length || !graphLayout) return;
            ctx.setExecutionGraphPayload({ treeData, layout: graphLayout });
            ctx.invalidateExecutionGraphRender();
            treeData.forEach(ctx.upsertTaskMeta);
            if (ctx.getActiveStage() === 'execute') {
                ctx.scheduleExecutionGraphRender({ force: true, delays: [0, 100, 320, 700] });
                ctx.renderExecuteStream();
            }
        });

        document.addEventListener('maars:execution-runtime-status', (e) => {
            ctx.renderExecutionRuntimeStatus(e?.detail || {});
        });

        window.addEventListener('pageshow', () => {
            ctx.scheduleExecutionGraphRender({ force: true, allowInactive: true, delays: [0, 120, 360, 900] });
        });
        window.addEventListener('resize', () => {
            if (ctx.getActiveStage() !== 'execute') return;
            ctx.scheduleExecutionGraphRender({ force: true, delays: [0, 120] });
        });
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState !== 'visible') return;
            ctx.scheduleExecutionGraphRender({
                force: true,
                allowInactive: ctx.getActiveStage() !== 'execute',
                delays: [0, 120, 360],
            });
        });
    }

    window.MAARS = window.MAARS || {};
    window.MAARS.researchLargeHelpers = {
        appendExecuteMessage,
        upsertExecuteThinkingMessage,
        seedExecutionState,
        resetExecuteTimelineForNewRun,
        renderExecuteStream,
        initExecuteStreamControls,
        initEventBridges,
        loadResearch,
    };
})();
