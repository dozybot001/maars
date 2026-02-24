/**
 * AI Thinking area - rendering and scroll logic.
 * Receives data via appendChunk(), handles throttled render and scroll state.
 */
(function () {
    'use strict';

    const state = window.MAARS.state || {};
    state.plannerThinkingBlocks = state.plannerThinkingBlocks || [];
    state.plannerThinkingUserScrolled = state.plannerThinkingUserScrolled || false;
    state.plannerThinkingBlockUserScrolled = state.plannerThinkingBlockUserScrolled || {};
    state.plannerLastUpdatedBlockKey = state.plannerLastUpdatedBlockKey || '';
    window.MAARS.state = state;

    const RENDER_THROTTLE_MS = 120;
    const RENDER_THROTTLE_LARGE_MS = 250;
    const LARGE_CONTENT_CHARS = 6000;

    let _renderScheduled = null;

    function render(skipHighlight) {
        const el = document.getElementById('plannerThinkingContent');
        const area = document.getElementById('plannerThinkingArea');
        if (!el) return;
        const blocks = state.plannerThinkingBlocks;
        let html = '';
        for (const block of blocks) {
            const headerText = block.taskId != null ? `Task ${block.taskId} | ${block.operation || ''}` : 'Thinking';
            const raw = block.content || '';
            let blockHtml = raw ? (typeof marked !== 'undefined' ? marked.parse(raw) : raw) : '';
            if (blockHtml && typeof DOMPurify !== 'undefined') blockHtml = DOMPurify.sanitize(blockHtml);
            const safeHeader = (headerText || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            html += `<div class="planner-thinking-block" data-block-key="${(block.key || '').replace(/"/g, '&quot;')}"><div class="planner-thinking-block-header">${safeHeader}</div><div class="planner-thinking-block-body">${blockHtml}</div></div>`;
        }
        const wasNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        const savedScrollTops = {};
        el.querySelectorAll('.planner-thinking-block').forEach((blockEl) => {
            const key = blockEl.getAttribute('data-block-key') || '';
            const body = blockEl.querySelector('.planner-thinking-block-body');
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
        if (!state.plannerThinkingUserScrolled && wasNearBottom) {
            requestAnimationFrame(() => {
                requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
            });
        }
        state.plannerThinkingBlockUserScrolled = state.plannerThinkingBlockUserScrolled || {};
        const lastKey = state.plannerLastUpdatedBlockKey || '';
        el.querySelectorAll('.planner-thinking-block').forEach((blockEl) => {
            const key = blockEl.getAttribute('data-block-key') || '';
            const body = blockEl.querySelector('.planner-thinking-block-body');
            if (!body) return;
            const shouldAutoScroll = key === lastKey && !state.plannerThinkingBlockUserScrolled[key];
            if (shouldAutoScroll) {
                requestAnimationFrame(() => { body.scrollTop = body.scrollHeight; });
            } else if (savedScrollTops[key] != null) {
                body.scrollTop = savedScrollTops[key];
            }
            body.addEventListener('scroll', function onBlockScroll() {
                const nearBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 40;
                if (!nearBottom) state.plannerThinkingBlockUserScrolled[key] = true;
                else state.plannerThinkingBlockUserScrolled[key] = false;
            }, { passive: true });
        });
        if (area && blocks.length) area.classList.add('has-content');
    }

    function scheduleRender() {
        if (_renderScheduled) return;
        const totalChars = state.plannerThinkingBlocks.reduce((s, b) => s + (b.content || '').length, 0);
        const throttle = totalChars > LARGE_CONTENT_CHARS ? RENDER_THROTTLE_LARGE_MS : RENDER_THROTTLE_MS;
        _renderScheduled = setTimeout(() => {
            _renderScheduled = null;
            render(true);
        }, throttle);
    }

    function applyHighlight() {
        const el = document.getElementById('plannerThinkingContent');
        if (!el || typeof hljs === 'undefined') return;
        requestIdleCallback(() => {
            el.querySelectorAll('pre code').forEach((node) => {
                try { hljs.highlightElement(node); } catch (_) {}
            });
        }, { timeout: 500 });
    }

    function clear() {
        state.plannerThinkingBlocks = [];
        state.plannerThinkingUserScrolled = false;
        state.plannerThinkingBlockUserScrolled = {};
        state.plannerLastUpdatedBlockKey = '';
        const el = document.getElementById('plannerThinkingContent');
        const area = document.getElementById('plannerThinkingArea');
        if (el) el.innerHTML = '';
        if (area) area.classList.remove('has-content');
    }

    function appendChunk(chunk, taskId, operation) {
        const key = (taskId != null && operation != null) ? `${String(taskId)}::${String(operation)}` : '_default';
        let block = state.plannerThinkingBlocks.find(b => b.key === key);
        if (!block) {
            block = { key, taskId, operation, content: '' };
            state.plannerThinkingBlocks.push(block);
        }
        block.content += chunk;
        state.plannerLastUpdatedBlockKey = key;
        scheduleRender();
    }

    function initScrollTracking() {
        const el = document.getElementById('plannerThinkingContent');
        if (!el) return;
        el.addEventListener('scroll', () => {
            const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
            if (!nearBottom) state.plannerThinkingUserScrolled = true;
            else state.plannerThinkingUserScrolled = false;
        }, { passive: true });
    }

    function initBlockFocus() {
        const area = document.getElementById('plannerThinkingArea');
        if (!area) return;
        area.addEventListener('click', (e) => {
            const block = e.target.closest('.planner-thinking-block');
            const allBlocks = area.querySelectorAll('.planner-thinking-block');
            const wasFocused = block && block.classList.contains('is-focused');
            allBlocks.forEach((b) => b.classList.remove('is-focused'));
            if (block && !wasFocused) block.classList.add('is-focused');
        });
    }

    initScrollTracking();
    initBlockFocus();

    window.MAARS.plannerThinking = { clear, appendChunk, render, applyHighlight };
})();
