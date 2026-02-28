/**
 * Executor - Thinking merges into Planner; Task Output in Planner Output view.
 * Uses createThinkingArea (shared with planner). Output blocks: click expand opens modal.
 */
(function () {
    'use strict';

    const state = window.MAARS.state || {};
    state.executorOutputs = state.executorOutputs || {};
    state.executorOutputUserScrolled = state.executorOutputUserScrolled ?? false;
    state.executorOutputBlockUserScrolled = state.executorOutputBlockUserScrolled || {};
    state.executorOutputLastUpdatedKey = state.executorOutputLastUpdatedKey || '';
    window.MAARS.state = state;

    const escapeHtml = (window.MAARS?.utils?.escapeHtml) || ((s) => (s == null ? '' : String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')));
    /* Executor thinking merges into Planner thinking area (same DOM, shared blocks) */
    const thinking = window.MAARS.createThinkingArea({
        prefix: 'planner',
        contentElId: 'plannerThinkingContent',
        areaElId: 'plannerThinkingArea',
        blockClass: 'planner-thinking-block',
        onClear: () => {
            state.executorOutputs = {};
            state.executorOutputUserScrolled = false;
            state.executorOutputBlockUserScrolled = {};
            state.executorOutputLastUpdatedKey = '';
            renderOutput();
        },
    });

    function renderOutput() {
        const el = document.getElementById('executorOutputContent');
        const area = document.getElementById('executorOutputArea');
        if (!el || !area) return;
        const outputs = state.executorOutputs;
        const keys = Object.keys(outputs).sort();
        const wasNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        const savedScrollTops = {};
        el.querySelectorAll('.executor-output-block').forEach((blockEl) => {
            const key = blockEl.getAttribute('data-task-id') || '';
            const body = blockEl.querySelector('.executor-output-block-body');
            if (body) savedScrollTops[key] = body.scrollTop;
        });
        if (keys.length === 0) {
            el.innerHTML = '';
            return;
        }
        let html = '';
        for (const taskId of keys) {
            const raw = outputs[taskId];
            let content = '';
            if (typeof raw === 'object') {
                const str = JSON.stringify(raw, null, 2);
                content = typeof marked !== 'undefined' ? marked.parse('```json\n' + str + '\n```') : '<pre>' + str + '</pre>';
            } else {
                content = (raw || '') ? (typeof marked !== 'undefined' ? marked.parse(String(raw)) : String(raw)) : '';
            }
            if (content && typeof DOMPurify !== 'undefined') content = DOMPurify.sanitize(content);
            const safeTaskId = escapeHtml(taskId || '');
            html += `<div class="executor-output-block" data-task-id="${safeTaskId}"><div class="executor-output-block-header">Task ${safeTaskId}<button type="button" class="executor-output-block-expand" aria-label="Expand" title="Expand">⤢</button></div><div class="executor-output-block-body">${content}</div></div>`;
        }
        try {
            el.innerHTML = html || '';
            if (typeof hljs !== 'undefined') {
                requestIdleCallback(() => {
                    el.querySelectorAll('pre code').forEach((node) => {
                        try { hljs.highlightElement(node); } catch (_) {}
                    });
                }, { timeout: 100 });
            }
        } catch (_) {
            el.textContent = keys.map((k) => `Task ${k}: ${outputs[k]}`).join('\n\n');
        }
        if (!state.executorOutputUserScrolled && wasNearBottom) {
            requestAnimationFrame(() => {
                requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
            });
        }
        state.executorOutputBlockUserScrolled = state.executorOutputBlockUserScrolled || {};
        const lastKey = state.executorOutputLastUpdatedKey || '';
        el.querySelectorAll('.executor-output-block').forEach((blockEl) => {
            const key = blockEl.getAttribute('data-task-id') || '';
            const body = blockEl.querySelector('.executor-output-block-body');
            if (!body) return;
            const shouldAutoScroll = key === lastKey && !state.executorOutputBlockUserScrolled[key];
            if (shouldAutoScroll) {
                requestAnimationFrame(() => { body.scrollTop = body.scrollHeight; });
            } else if (savedScrollTops[key] != null) {
                body.scrollTop = savedScrollTops[key];
            }
            body.addEventListener('scroll', function onBlockScroll() {
                const nearBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 40;
                if (!nearBottom) state.executorOutputBlockUserScrolled[key] = true;
                else state.executorOutputBlockUserScrolled[key] = false;
            }, { passive: true });
        });
    }

    function initOutputScrollTracking() {
        const el = document.getElementById('executorOutputContent');
        if (!el) return;
        el.addEventListener('scroll', () => {
            const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
            if (!nearBottom) state.executorOutputUserScrolled = true;
            else state.executorOutputUserScrolled = false;
        }, { passive: true });
    }

    function setTaskOutput(taskId, output) {
        if (!taskId) return;
        state.executorOutputs[taskId] = output;
        state.executorOutputLastUpdatedKey = String(taskId);
        renderOutput();
    }

    let _outputModalOpen = false;
    function openOutputModal(taskId, contentHtml, scrollTop) {
        const modal = document.getElementById('executorOutputModal');
        const titleEl = document.getElementById('executorOutputModalTitle');
        const bodyEl = document.getElementById('executorOutputModalBody');
        const closeBtn = document.getElementById('executorOutputModalClose');
        const backdrop = modal?.querySelector('.executor-output-modal-backdrop');
        if (!modal || !bodyEl) return;
        if (_outputModalOpen) return;
        _outputModalOpen = true;
        modal.setAttribute('data-current-task-id', taskId || '');
        titleEl.textContent = taskId ? `Task ${taskId}` : 'Task Output';
        bodyEl.innerHTML = contentHtml || '';
        bodyEl.scrollTop = scrollTop || 0;
        if (typeof hljs !== 'undefined') {
            requestAnimationFrame(() => {
                bodyEl.querySelectorAll('pre code').forEach((node) => {
                    try { hljs.highlightElement(node); } catch (_) {}
                });
            });
        }
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        function closeModal() {
            _outputModalOpen = false;
            modal.classList.remove('is-open');
            modal.setAttribute('aria-hidden', 'true');
            document.body.style.overflow = '';
        }
        closeBtn?.addEventListener('click', closeModal, { once: true });
        backdrop?.addEventListener('click', closeModal, { once: true });
        document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') closeModal(); }, { once: true });
    }

    function applyOutputHighlight() {
        const el = document.getElementById('executorOutputContent');
        if (!el || typeof hljs === 'undefined') return;
        requestIdleCallback(() => {
            el.querySelectorAll('pre code').forEach((node) => {
                try { hljs.highlightElement(node); } catch (_) {}
            });
        }, { timeout: 500 });
    }

    function getDownloadContent(taskId) {
        const raw = state.executorOutputs[taskId];
        if (raw == null) return { text: '', ext: 'txt' };
        if (typeof raw === 'string') return { text: raw, ext: 'md' };
        if (typeof raw === 'object' && raw !== null && 'content' in raw && typeof raw.content === 'string') {
            return { text: raw.content, ext: 'md' };
        }
        return { text: JSON.stringify(raw, null, 2), ext: 'json' };
    }

    function downloadTaskOutput(taskId) {
        const { text, ext } = getDownloadContent(taskId);
        const filename = `task-${(taskId || 'output').replace(/[^a-zA-Z0-9_-]/g, '_')}.${ext}`;
        const blob = new Blob([text], { type: ext === 'json' ? 'application/json' : 'text/markdown' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
        URL.revokeObjectURL(a.href);
    }

    function initOutputAreaClick() {
        const area = document.getElementById('executorOutputArea');
        if (!area) return;
        area.addEventListener('click', (e) => {
            const expandBtn = e.target.closest('.executor-output-block-expand');
            if (expandBtn) {
                e.stopPropagation();
                const block = expandBtn.closest('.executor-output-block');
                if (block) {
                    const bodyEl = block.querySelector('.executor-output-block-body');
                    openOutputModal(block.getAttribute('data-task-id') || '', bodyEl?.innerHTML || '', bodyEl?.scrollTop || 0);
                }
                return;
            }
            const block = e.target.closest('.executor-output-block');
            if (!block) return;
            const allBlocks = area.querySelectorAll('.executor-output-block');
            const wasFocused = block.classList.contains('is-focused');
            allBlocks.forEach((b) => b.classList.remove('is-focused'));
            if (!wasFocused) block.classList.add('is-focused');
        });
    }

    function initOutputModalDownload() {
        const downloadBtn = document.getElementById('executorOutputModalDownload');
        const modal = document.getElementById('executorOutputModal');
        if (!downloadBtn || !modal) return;
        downloadBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const tid = modal.getAttribute('data-current-task-id') || '';
            downloadTaskOutput(tid);
        });
    }

    initOutputAreaClick();
    initOutputScrollTracking();
    initOutputModalDownload();

    window.MAARS.executorThinking = {
        clear: thinking.clear,
        appendChunk: thinking.appendChunk,
        applyOutputHighlight,
        setTaskOutput,
        renderOutput,
    };
})();
