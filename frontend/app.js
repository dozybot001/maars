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
            theme.initTheme();
            document.getElementById('themeToggleBtn')?.addEventListener('click', theme.toggleTheme);
            theme.initApiConfigModal();
        }
        document.getElementById('restoreBtn')?.addEventListener('click', async () => {
            const api = window.MAARS?.api;
            if (!api?.restoreRecentPlan) return;
            const btn = document.getElementById('restoreBtn');
            const origTitle = btn?.title;
            if (btn) { btn.disabled = true; btn.title = 'Restoring...'; }
            try {
                await api.restoreRecentPlan();
                if (btn) btn.title = 'Restored';
                setTimeout(() => { if (btn) { btn.disabled = false; btn.title = origTitle || ''; } }, 1500);
            } catch (e) {
                console.error('Restore failed:', e);
                alert('Restore failed: ' + (e.message || e));
                if (btn) { btn.disabled = false; btn.title = origTitle || ''; }
            }
        });
        document.getElementById('clearDbBtn')?.addEventListener('click', async () => {
            if (!confirm('Clear DB? This will delete all plans.')) return;
            try {
                const api = window.MAARS?.api;
                if (!api?.clearDb) return;
                await api.clearDb();
                try { localStorage.removeItem(cfg?.PLAN_ID_KEY || 'maars-plan-id'); } catch (_) {}
                location.reload();
            } catch (e) {
                console.error('Clear DB failed:', e);
                alert('Clear failed: ' + (e.message || e));
            }
        });
        if (cfg && cfg.resolvePlanId) cfg.resolvePlanId().catch(() => {});
        if (planner) planner.init();
        if (plannerViews) plannerViews.init();
        if (ws) ws.init();

        if (typeof TaskTree !== 'undefined' && TaskTree.initClickHandlers) {
            TaskTree.initClickHandlers();
        }

        initTreeViewTabs();
        initSectionCollapse();

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

    const SECTION_COLLAPSE_KEY = 'maars-section-collapsed';

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

    function initSectionCollapse() {
        const saved = (() => {
            try {
                const s = localStorage.getItem(SECTION_COLLAPSE_KEY);
                return s ? JSON.parse(s) : {};
            } catch (_) { return {}; }
        })();

        document.querySelectorAll('.planner-section, .workers-section').forEach((section) => {
            const header = section.querySelector('.section-header');
            const sectionId = section.dataset.section;
            if (!header || !sectionId) return;

            const isCollapsed = saved[sectionId] === true;
            if (isCollapsed) {
                section.classList.add('collapsed');
                header.setAttribute('aria-expanded', 'false');
            }

            const toggle = () => {
                const collapsed = section.classList.toggle('collapsed');
                header.setAttribute('aria-expanded', String(!collapsed));
                try {
                    const state = (() => {
                        const s = localStorage.getItem(SECTION_COLLAPSE_KEY);
                        return s ? JSON.parse(s) : {};
                    })();
                    state[sectionId] = collapsed;
                    localStorage.setItem(SECTION_COLLAPSE_KEY, JSON.stringify(state));
                } catch (_) {}
            };

            header.addEventListener('click', toggle);
            header.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    toggle();
                }
            });
        });
    }
})();
