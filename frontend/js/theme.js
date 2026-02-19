/**
 * MAARS theme - theme switching and API config modal.
 */
(function () {
    'use strict';
    const cfg = window.MAARS?.config;
    if (!cfg) return;

    function initTheme() {
        const saved = localStorage.getItem(cfg.THEME_STORAGE_KEY);
        const theme = saved && cfg.THEMES.includes(saved) ? saved : 'black';
        applyTheme(theme);
    }

    function applyTheme(theme) {
        if (theme === 'light') {
            document.documentElement.removeAttribute('data-theme');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
        }
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme') || 'light';
        const idx = cfg.THEMES.indexOf(current);
        const next = cfg.THEMES[(idx + 1) % cfg.THEMES.length];
        applyTheme(next);
        localStorage.setItem(cfg.THEME_STORAGE_KEY, next);
    }

    const PHASES = ['atomicity', 'decompose', 'format', 'execute', 'validate'];
    const PHASE_KEYS = ['baseUrl', 'apiKey', 'model'];

    function populateApiConfigForm(apiCfg) {
        apiCfg = apiCfg || {};
        document.getElementById('apiBaseUrl').value = apiCfg.baseUrl || '';
        document.getElementById('apiKey').value = apiCfg.apiKey || '';
        document.getElementById('apiModel').value = apiCfg.model || '';
        const phases = apiCfg.phases || {};
        PHASES.forEach(phase => {
            const p = phases[phase] || {};
            PHASE_KEYS.forEach(k => {
                const el = document.getElementById(`phase-${phase}-${k}`);
                if (el) el.value = p[k] || '';
            });
        });
        const useMock = !!apiCfg.useMock;
        document.getElementById('apiUseMock').value = useMock ? '1' : '0';
        document.querySelectorAll('.api-mode-option').forEach(el => {
            el.classList.toggle('selected', (el.dataset.mode === 'mock') === useMock);
        });
    }

    function initApiConfigModal() {
        const modal = document.getElementById('apiConfigModal');
        const btn = document.getElementById('apiConfigBtn');
        const close = document.getElementById('apiConfigModalClose');
        const form = document.getElementById('apiConfigForm');
        const resetBtn = document.getElementById('apiConfigReset');

        document.getElementById('apiModeMock')?.addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('apiUseMock').value = '1';
            document.querySelectorAll('.api-mode-option').forEach(el => el.classList.toggle('selected', el.dataset.mode === 'mock'));
        });
        document.getElementById('apiModeLlm')?.addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('apiUseMock').value = '0';
            document.querySelectorAll('.api-mode-option').forEach(el => el.classList.toggle('selected', el.dataset.mode === 'llm'));
        });

        btn?.addEventListener('click', async () => {
            try {
                const apiCfg = await cfg.fetchApiConfig();
                populateApiConfigForm(apiCfg);
            } catch (e) {
                console.error('Failed to load config:', e);
            }
            modal.style.display = 'block';
        });
        close?.addEventListener('click', () => { modal.style.display = 'none'; });
        window.addEventListener('click', (e) => { if (e.target === modal) modal.style.display = 'none'; });
        form?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const baseUrl = document.getElementById('apiBaseUrl').value.trim();
            const apiKey = document.getElementById('apiKey').value.trim();
            const model = document.getElementById('apiModel').value.trim();
            const useMock = document.getElementById('apiUseMock').value === '1';
            const phasesOut = {};
            PHASES.forEach(phase => {
                const p = {};
                PHASE_KEYS.forEach(k => {
                    const el = document.getElementById(`phase-${phase}-${k}`);
                    const v = el ? el.value.trim() : '';
                    if (v) p[k] = v;
                });
                if (Object.keys(p).length) phasesOut[phase] = p;
            });
            const out = { baseUrl: baseUrl || undefined, apiKey: apiKey || undefined, model: model || undefined, useMock };
            if (Object.keys(phasesOut).length) out.phases = phasesOut;
            try {
                await cfg.saveApiConfig(out);
                modal.style.display = 'none';
            } catch (err) {
                console.error('Failed to save config:', err);
                alert('保存失败: ' + (err.message || 'Unknown error'));
            }
        });
        resetBtn?.addEventListener('click', async () => {
            try {
                await cfg.saveApiConfig({});
                populateApiConfigForm({});
                document.getElementById('apiUseMock').value = '0';
                document.querySelectorAll('.api-mode-option').forEach(el => el.classList.toggle('selected', el.dataset.mode === 'llm'));
            } catch (err) {
                console.error('Failed to reset config:', err);
            }
        });
    }

    window.MAARS.theme = { initTheme, applyTheme, toggleTheme, initApiConfigModal };
})();
