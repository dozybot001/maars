/**
 * MAARS app - main entry point, wires modules together.
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', () => {
        const cfg = window.MAARS?.config;
        const theme = window.MAARS?.theme;
        const planner = window.MAARS?.planner;
        const monitor = window.MAARS?.monitor;
        const ws = window.MAARS?.ws;

        if (theme) {
            theme.initTheme();
            document.getElementById('themeToggleBtn')?.addEventListener('click', theme.toggleTheme);
            theme.initApiConfigModal();
        }
        document.getElementById('clearDbBtn')?.addEventListener('click', async () => {
            if (!confirm('确定清理 DB？将删除所有 plan')) return;
            try {
                const api = window.MAARS?.api;
                if (!api?.clearDb) return;
                await api.clearDb();
                try { localStorage.removeItem(cfg?.PLAN_ID_KEY || 'maars-plan-id'); } catch (_) {}
                location.reload();
            } catch (e) {
                console.error('Clear DB failed:', e);
                alert('清理失败: ' + (e.message || e));
            }
        });
        if (cfg && cfg.resolvePlanId) cfg.resolvePlanId().catch(() => {});
        if (planner) planner.init();
        if (monitor) monitor.init();
        if (ws) ws.init();

        if (typeof TaskTree !== 'undefined' && TaskTree.initClickHandlers) {
            TaskTree.initClickHandlers();
        }
    });
})();
