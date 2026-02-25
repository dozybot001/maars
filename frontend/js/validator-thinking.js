/**
 * Validator AI Thinking area - uses createThinkingArea factory.
 * appendChunk calls scheduleRender internally; render/scheduleRender are exposed.
 * WebSocket validator-thinking events are wired in websocket.js; streaming displays correctly.
 */
(function () {
    'use strict';

    const thinking = window.MAARS.createThinkingArea({
        prefix: 'validator',
        contentElId: 'validatorThinkingContent',
        areaElId: 'validatorThinkingArea',
        blockClass: 'validator-thinking-block',
    });

    window.MAARS.validatorThinking = { clear: thinking.clear, appendChunk: thinking.appendChunk, render: thinking.render, applyHighlight: thinking.applyHighlight };
})();
