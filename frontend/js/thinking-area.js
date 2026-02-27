/**
 * Thinking Area Factory - unified implementation for planner/executor/validator AI thinking.
 * Creates render, appendChunk, clear, applyHighlight with throttled render and scroll logic.
 */
(function () {
    'use strict';

    const C = window.MAARS?.constants || {};
    const escapeHtml = (window.MAARS?.utils?.escapeHtml) || ((s) => (s == null ? '' : String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')));
    const RENDER_THROTTLE_MS = C.RENDER_THROTTLE_MS ?? 120;
    const RENDER_THROTTLE_LARGE_MS = C.RENDER_THROTTLE_LARGE_MS ?? 250;
    const LARGE_CONTENT_CHARS = C.LARGE_CONTENT_CHARS ?? 6000;

    function createThinkingArea(config) {
        const { prefix, contentElId, areaElId, blockClass, onClear } = config;
        const blocksKey = `${prefix}ThinkingBlocks`;
        const userScrolledKey = `${prefix}ThinkingUserScrolled`;
        const blockUserScrolledKey = `${prefix}ThinkingBlockUserScrolled`;
        const lastUpdatedKey = `${prefix}LastUpdatedBlockKey`;

        const scheduleCounterKey = `${prefix}ScheduleCounter`;
        const planCounterKey = `${prefix}PlanCounter`;
        const planStreamingKey = `${prefix}PlanStreamingKey`;
        const state = window.MAARS.state || {};
        state[blocksKey] = state[blocksKey] || [];
        state[userScrolledKey] = state[userScrolledKey] ?? false;
        state[blockUserScrolledKey] = state[blockUserScrolledKey] || {};
        state[lastUpdatedKey] = state[lastUpdatedKey] || '';
        state[scheduleCounterKey] = state[scheduleCounterKey] ?? 0;
        state[planCounterKey] = state[planCounterKey] ?? 0;
        state[planStreamingKey] = state[planStreamingKey] ?? '';
        window.MAARS.state = state;

        let _renderScheduled = null;

        function render(skipHighlight) {
            const el = document.getElementById(contentElId);
            const area = document.getElementById(areaElId);
            if (!el) return;
            const blocks = state[blocksKey];
            let html = '';
            for (const block of blocks) {
                if (block.blockType === 'schedule') {
                    const si = block.scheduleInfo || {};
                    const parts = [];
                    if (si.turn != null) parts.push(`Turn ${si.turn}${si.max_turns != null ? `/${si.max_turns}` : ''}`);
                    if (si.tool_name) parts.push(si.tool_name + (si.tool_args ? '(...)' : ''));
                    const scheduleText = parts.length ? parts.join(' | ') : 'Scheduling';
                    const safeText = escapeHtml(scheduleText);
                    html += `<div class="${blockClass} ${blockClass}--schedule" data-block-key="${(block.key || '').replace(/"/g, '&quot;')}"><div class="${blockClass}-schedule-text">${safeText}</div></div>`;
                    continue;
                }
                let headerText = block.taskId != null ? `Task ${block.taskId} | ${block.operation || ''}` : (block.operation || 'Thinking');
                const si = block.scheduleInfo;
                if (si) {
                    const parts = [];
                    if (si.turn != null) parts.push(`Turn ${si.turn}${si.max_turns != null ? `/${si.max_turns}` : ''}`);
                    if (si.tool_name) parts.push(si.tool_name + (si.tool_args ? '(...)' : ''));
                    if (parts.length) headerText += ' | ' + parts.join(' | ');
                }
                const raw = block.content || '';
                let blockHtml = raw ? (typeof marked !== 'undefined' ? marked.parse(raw) : raw) : '';
                if (blockHtml && typeof DOMPurify !== 'undefined') blockHtml = DOMPurify.sanitize(blockHtml);
                const safeHeader = escapeHtml(headerText || '');
                html += `<div class="${blockClass}" data-block-key="${(block.key || '').replace(/"/g, '&quot;')}"><div class="${blockClass}-header">${safeHeader}</div><div class="${blockClass}-body">${blockHtml}</div></div>`;
            }
            const wasNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
            const savedScrollTops = {};
            el.querySelectorAll(`.${blockClass}`).forEach((blockEl) => {
                const key = blockEl.getAttribute('data-block-key') || '';
                const body = blockEl.querySelector(`.${blockClass}-body`);
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
                el.textContent = blocks.map((b) => b.content || '').join('\n\n');
            }
            if (!state[userScrolledKey] && wasNearBottom) {
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
                });
            }
            state[blockUserScrolledKey] = state[blockUserScrolledKey] || {};
            const lastKey = state[lastUpdatedKey] || '';
            el.querySelectorAll(`.${blockClass}`).forEach((blockEl) => {
                const key = blockEl.getAttribute('data-block-key') || '';
                const body = blockEl.querySelector(`.${blockClass}-body`);
                if (!body) return;
                const shouldAutoScroll = key === lastKey && !state[blockUserScrolledKey][key];
                if (shouldAutoScroll) {
                    requestAnimationFrame(() => { body.scrollTop = body.scrollHeight; });
                } else if (savedScrollTops[key] != null) {
                    body.scrollTop = savedScrollTops[key];
                }
                body.addEventListener('scroll', function onBlockScroll() {
                    const nearBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 40;
                    if (!nearBottom) state[blockUserScrolledKey][key] = true;
                    else state[blockUserScrolledKey][key] = false;
                }, { passive: true });
            });
            if (area && blocks.length) area.classList.add('has-content');
        }

        function scheduleRender() {
            if (_renderScheduled) return;
            const totalChars = state[blocksKey].reduce((s, b) => s + (b.content || '').length, 0);
            const throttle = totalChars > LARGE_CONTENT_CHARS ? RENDER_THROTTLE_LARGE_MS : RENDER_THROTTLE_MS;
            _renderScheduled = setTimeout(() => {
                _renderScheduled = null;
                render(true);
            }, throttle);
        }

        function applyHighlight() {
            const el = document.getElementById(contentElId);
            if (!el || typeof hljs === 'undefined') return;
            requestIdleCallback(() => {
                el.querySelectorAll('pre code').forEach((node) => {
                    try { hljs.highlightElement(node); } catch (_) {}
                });
            }, { timeout: 500 });
        }

        function clear() {
            state[blocksKey] = [];
            state[userScrolledKey] = false;
            state[blockUserScrolledKey] = {};
            state[lastUpdatedKey] = '';
            state[scheduleCounterKey] = 0;
            state[planCounterKey] = 0;
            state[planStreamingKey] = '';
            const el = document.getElementById(contentElId);
            const area = document.getElementById(areaElId);
            if (el) el.innerHTML = '';
            if (area) area.classList.remove('has-content');
            if (typeof onClear === 'function') onClear();
        }

        function appendChunk(chunk, taskId, operation, scheduleInfo) {
            if (!chunk && scheduleInfo != null) {
                state[planStreamingKey] = '';
                if (scheduleInfo.tool_name) {
                    state[scheduleCounterKey] = (state[scheduleCounterKey] || 0) + 1;
                    const key = `schedule_${state[scheduleCounterKey]}`;
                    const block = { key, blockType: 'schedule', scheduleInfo };
                    state[blocksKey].push(block);
                    state[lastUpdatedKey] = key;
                    scheduleRender();
                }
                return;
            }
            if (taskId == null && chunk) {
                let block = state[planStreamingKey] ? state[blocksKey].find((b) => b.key === state[planStreamingKey]) : null;
                if (block) {
                    block.content += chunk;
                    if (scheduleInfo != null) block.scheduleInfo = scheduleInfo;
                    state[lastUpdatedKey] = block.key;
                } else {
                    state[planCounterKey] = (state[planCounterKey] || 0) + 1;
                    const key = `plan_${state[planCounterKey]}`;
                    block = { key, taskId: null, operation: operation || 'Plan', content: chunk, scheduleInfo: scheduleInfo || null };
                    state[blocksKey].push(block);
                    state[planStreamingKey] = key;
                    state[lastUpdatedKey] = key;
                }
                scheduleRender();
                return;
            }
            state[planStreamingKey] = '';
            const key = (taskId != null && operation != null) ? `${String(taskId)}::${String(operation)}` : '_default';
            let block = state[blocksKey].find((b) => b.key === key);
            if (!block) {
                block = { key, taskId, operation, content: '', scheduleInfo: null };
                state[blocksKey].push(block);
            }
            if (chunk) block.content += chunk;
            if (scheduleInfo != null) block.scheduleInfo = scheduleInfo;
            state[lastUpdatedKey] = key;
            scheduleRender();
        }

        function initScrollTracking() {
            const el = document.getElementById(contentElId);
            if (!el) return;
            el.addEventListener('scroll', () => {
                const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
                if (!nearBottom) state[userScrolledKey] = true;
                else state[userScrolledKey] = false;
            }, { passive: true });
        }

        function initBlockFocus() {
            const area = document.getElementById(areaElId);
            if (!area) return;
            const scheduleModifier = `${blockClass}--schedule`;
            area.addEventListener('click', (e) => {
                const block = e.target.closest(`.${blockClass}`);
                if (!block || block.classList.contains(scheduleModifier)) return;
                const allBlocks = area.querySelectorAll(`.${blockClass}:not(.${scheduleModifier})`);
                const wasFocused = block.classList.contains('is-focused');
                allBlocks.forEach((b) => b.classList.remove('is-focused'));
                if (!wasFocused) block.classList.add('is-focused');
            });
        }

        initScrollTracking();
        initBlockFocus();

        return { clear, appendChunk, render, applyHighlight, scheduleRender };
    }

    window.MAARS.createThinkingArea = createThinkingArea;
})();
