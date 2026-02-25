/**
 * Planner AI Thinking area - uses createThinkingArea factory.
 */
(function () {
    'use strict';

    const thinking = window.MAARS.createThinkingArea({
        prefix: 'planner',
        contentElId: 'plannerThinkingContent',
        areaElId: 'plannerThinkingArea',
        blockClass: 'planner-thinking-block',
    });

    window.MAARS.plannerThinking = { clear: thinking.clear, appendChunk: thinking.appendChunk, render: thinking.render, applyHighlight: thinking.applyHighlight };
})();
