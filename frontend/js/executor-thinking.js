/**
 * Executor AI Thinking area - rendering and scroll logic.
 * Receives data via appendChunk(), handles throttled render and scroll state.
 * Right panel (executor output) displays final extracted output per task.
 */
(function () {
    'use strict';

    const state = window.MAARS.state || {};
    state.executorThinkingBlocks = state.executorThinkingBlocks || [];
    state.executorThinkingUserScrolled = state.executorThinkingUserScrolled || false;
    state.executorThinkingBlockUserScrolled = state.executorThinkingBlockUserScrolled || {};
    state.executorLastUpdatedBlockKey = state.executorLastUpdatedBlockKey || '';
    state.executorOutputs = state.executorOutputs || {};
    window.MAARS.state = state;

    const RENDER_THROTTLE_MS = 120;
    const RENDER_THROTTLE_LARGE_MS = 250;
    const LARGE_CONTENT_CHARS = 6000;

    let _renderScheduled = null;

    function render(skipHighlight) {
        const el = document.getElementById('executorThinkingContent');
        const area = document.getElementById('executorThinkingArea');
        if (!el) return;
        const blocks = state.executorThinkingBlocks;
        let html = '';
        for (const block of blocks) {
            const headerText = block.taskId != null ? `Task ${block.taskId} | ${block.operation || ''}` : 'Thinking';
            const raw = block.content || '';
            let blockHtml = raw ? (typeof marked !== 'undefined' ? marked.parse(raw) : raw) : '';
            if (blockHtml && typeof DOMPurify !== 'undefined') blockHtml = DOMPurify.sanitize(blockHtml);
            const safeHeader = (headerText || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            html += `<div class="executor-thinking-block" data-block-key="${(block.key || '').replace(/"/g, '&quot;')}"><div class="executor-thinking-block-header">${safeHeader}</div><div class="executor-thinking-block-body">${blockHtml}</div></div>`;
        }
        const wasNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        const savedScrollTops = {};
        el.querySelectorAll('.executor-thinking-block').forEach((blockEl) => {
            const key = blockEl.getAttribute('data-block-key') || '';
            const body = blockEl.querySelector('.executor-thinking-block-body');
            if (body) savedScrollTops[key] = body.scrollTop;
        });
        try {
            el.innerHTML = html || '';
            if (!skipHighlight && typeof hljs !== 'undefined') {
                const codeBlocks = el.querySelectorAll('pre code');
                if (codeBlocks.length > 0 && codeBlocks.length <= 15) {
                    codeBlocks.forEach((node) => { try { hljs.highlightElement(node); } catch (_) {} });
                }
            }
        } catch (_) {
            el.textContent = blocks.map(b => b.content || '').join('\n\n');
        }
        if (!state.executorThinkingUserScrolled && wasNearBottom) {
            requestAnimationFrame(() => {
                requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
            });
        }
        state.executorThinkingBlockUserScrolled = state.executorThinkingBlockUserScrolled || {};
        const lastKey = state.executorLastUpdatedBlockKey || '';
        el.querySelectorAll('.executor-thinking-block').forEach((blockEl) => {
            const key = blockEl.getAttribute('data-block-key') || '';
            const body = blockEl.querySelector('.executor-thinking-block-body');
            if (!body) return;
            const shouldAutoScroll = key === lastKey && !state.executorThinkingBlockUserScrolled[key];
            if (shouldAutoScroll) {
                requestAnimationFrame(() => { body.scrollTop = body.scrollHeight; });
            } else if (savedScrollTops[key] != null) {
                body.scrollTop = savedScrollTops[key];
            }
            body.addEventListener('scroll', function onBlockScroll() {
                const nearBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 40;
                if (!nearBottom) state.executorThinkingBlockUserScrolled[key] = true;
                else state.executorThinkingBlockUserScrolled[key] = false;
            }, { passive: true });
        });
        if (area && blocks.length) area.classList.add('has-content');
    }

    function scheduleRender() {
        if (_renderScheduled) return;
        const totalChars = state.executorThinkingBlocks.reduce((s, b) => s + (b.content || '').length, 0);
        const throttle = totalChars > LARGE_CONTENT_CHARS ? RENDER_THROTTLE_LARGE_MS : RENDER_THROTTLE_MS;
        _renderScheduled = setTimeout(() => {
            _renderScheduled = null;
            render(true);
        }, throttle);
    }

    function applyHighlight() {
        const el = document.getElementById('executorThinkingContent');
        if (!el || typeof hljs === 'undefined') return;
        requestIdleCallback(() => {
            el.querySelectorAll('pre code').forEach((node) => {
                try { hljs.highlightElement(node); } catch (_) {}
            });
        }, { timeout: 500 });
    }

    function clear() {
        state.executorThinkingBlocks = [];
        state.executorThinkingUserScrolled = false;
        state.executorThinkingBlockUserScrolled = {};
        state.executorLastUpdatedBlockKey = '';
        state.executorOutputs = {};
        const el = document.getElementById('executorThinkingContent');
        const area = document.getElementById('executorThinkingArea');
        if (el) el.innerHTML = '';
        if (area) area.classList.remove('has-content');
        renderOutput();
    }

    function appendChunk(chunk, taskId, operation) {
        const key = (taskId != null && operation != null) ? `${String(taskId)}::${String(operation)}` : '_default';
        let block = state.executorThinkingBlocks.find(b => b.key === key);
        if (!block) {
            block = { key, taskId, operation, content: '' };
            state.executorThinkingBlocks.push(block);
        }
        block.content += chunk;
        state.executorLastUpdatedBlockKey = key;
        scheduleRender();
    }

    function setTaskOutput(taskId, output) {
        if (!taskId) return;
        state.executorOutputs[taskId] = output;
        renderOutput();
    }

    function renderOutput() {
        const el = document.getElementById('executorOutputContent');
        const area = document.getElementById('executorOutputArea');
        if (!el || !area) return;
        const outputs = state.executorOutputs;
        const keys = Object.keys(outputs).sort();
        if (keys.length === 0) {
            el.innerHTML = '';
            area.classList.remove('has-content');
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
            const safeTaskId = (taskId || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            html += `<div class="executor-output-block" data-task-id="${safeTaskId}"><div class="executor-output-block-header">Task ${safeTaskId}</div><div class="executor-output-block-body">${content}</div></div>`;
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
            el.textContent = keys.map(k => `Task ${k}: ${outputs[k]}`).join('\n\n');
        }
        area.classList.add('has-content');
    }

    function initScrollTracking() {
        const el = document.getElementById('executorThinkingContent');
        if (!el) return;
        el.addEventListener('scroll', () => {
            const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
            if (!nearBottom) state.executorThinkingUserScrolled = true;
            else state.executorThinkingUserScrolled = false;
        }, { passive: true });
    }

    function initBlockFocus() {
        const area = document.getElementById('executorThinkingArea');
        if (!area) return;
        area.addEventListener('click', (e) => {
            const block = e.target.closest('.executor-thinking-block');
            const allBlocks = area.querySelectorAll('.executor-thinking-block');
            const wasFocused = block && block.classList.contains('is-focused');
            allBlocks.forEach((b) => b.classList.remove('is-focused'));
            if (block && !wasFocused) block.classList.add('is-focused');
        });
    }

    function initOutputBlockFocus() {
        const area = document.getElementById('executorOutputArea');
        if (!area) return;
        area.addEventListener('click', (e) => {
            const block = e.target.closest('.executor-output-block');
            const allBlocks = area.querySelectorAll('.executor-output-block');
            const wasFocused = block && block.classList.contains('is-focused');
            allBlocks.forEach((b) => b.classList.remove('is-focused'));
            if (block && !wasFocused) block.classList.add('is-focused');
        });
    }

    initScrollTracking();
    initBlockFocus();
    initOutputBlockFocus();

    window.MAARS.executorThinking = { clear, appendChunk, render, applyHighlight, setTaskOutput, renderOutput };
})();
