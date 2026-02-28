/**
 * MAARS app - main entry point, wires modules together.
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', () => {
        const cfg = window.MAARS?.config;
        const theme = window.MAARS?.theme;
        const planner = window.MAARS?.planner;
        const plannerViews = window.MAARS?.plannerViews;
        const ws = window.MAARS?.ws;

        if (theme) {
            theme.initTheme().catch(() => {});
            theme.initSettingsModal();
        }
        if (cfg && cfg.resolvePlanId) cfg.resolvePlanId().catch(() => {});
        if (planner) planner.init();
        if (plannerViews) plannerViews.init();
        if (ws) ws.init();

        if (typeof TaskTree !== 'undefined' && TaskTree.initClickHandlers) {
            TaskTree.initClickHandlers();
        }

        initTreeViewTabs();

        (async () => {
            const api = window.MAARS?.api;
            if (!api?.restoreRecentPlan) return;
            try {
                await api.restoreRecentPlan();
            } catch (_) {
                /* 无 plan 时静默忽略 */
            }
        })();
    });

    function initTreeViewTabs() {
        const tabs = document.querySelectorAll('.tree-view-tab');
        const panels = document.querySelectorAll('.tree-view-panel');
        tabs.forEach((tab) => {
            tab.addEventListener('click', () => {
                const view = tab.getAttribute('data-view');
                tabs.forEach((t) => {
                    t.classList.toggle('active', t === tab);
                    t.setAttribute('aria-pressed', t === tab ? 'true' : 'false');
                });
                panels.forEach((p) => {
                    const match = p.getAttribute('data-view-panel') === view;
                    p.classList.toggle('active', match);
                });
            });
        });
    }
})();
