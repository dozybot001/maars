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

    const PHASES = [
        { key: 'atomicity', label: 'Atomicity Check' },
        { key: 'decompose', label: 'Decompose' },
        { key: 'format', label: 'Format' },
        { key: 'quality', label: 'Quality Assess' },
        { key: 'execute', label: 'Execute' },
        { key: 'validate', label: 'Validate' },
    ];

    let _configState = { useMock: true, current: '', presets: {} };
    let _activePresetKey = '';

    function _generateKey(label) {
        const base = (label || 'preset').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'preset';
        let key = base;
        let i = 2;
        while (_configState.presets[key]) { key = base + '_' + i++; }
        return key;
    }

    function _truncate(str, len) {
        if (!str) return '';
        return str.length > len ? str.slice(0, len) + '…' : str;
    }

    function _escapeHtml(s) {
        if (!s) return '';
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function _renderPresetCards() {
        const container = document.getElementById('presetCards');
        if (!container) return;
        const keys = Object.keys(_configState.presets);
        let html = '';
        keys.forEach(key => {
            const p = _configState.presets[key];
            const label = _escapeHtml(p.label || key);
            const isCurrent = key === _configState.current;
            const isActive = key === _activePresetKey;
            const meta = _escapeHtml(p.model || _truncate(p.baseUrl || '', 18)) || '—';
            html += `<button type="button" class="api-preset-item${isActive ? ' active' : ''}${isCurrent ? ' current' : ''}" data-key="${key}">
                <span class="api-preset-name">${label}</span>
                <span class="api-preset-meta">${meta}</span>
            </button>`;
        });
        html += '<button type="button" class="api-preset-add" id="presetAddBtn">+ 新建</button>';
        container.innerHTML = html;

        container.querySelectorAll('.api-preset-item').forEach(card => {
            card.addEventListener('click', () => {
                _readFormIntoState();
                _activePresetKey = card.dataset.key;
                _configState.current = card.dataset.key;
                _populatePresetForm();
                _renderPresetCards();
                _updateEditPanelVisibility();
            });
        });
        document.getElementById('presetAddBtn')?.addEventListener('click', () => {
            _readFormIntoState();
            const key = _generateKey('new');
            _configState.presets[key] = { label: 'New Preset', baseUrl: '', apiKey: '', model: '' };
            _activePresetKey = key;
            _configState.current = key;
            _populatePresetForm();
            _renderPresetCards();
            _updateEditPanelVisibility();
        });
    }

    function _updateEditPanelVisibility() {
        const titleEl = document.getElementById('presetEditTitle');
        if (titleEl) {
            titleEl.textContent = _activePresetKey
                ? '编辑：' + (_configState.presets[_activePresetKey]?.label || _activePresetKey)
                : '选择预设';
        }
    }

    function _renderPhaseCards() {
        const container = document.getElementById('phaseCards');
        if (!container) return;
        const p = _configState.presets[_activePresetKey] || {};
        const phases = p.phases || {};
        let html = '';
        PHASES.forEach(({ key, label }) => {
            const ph = phases[key] || {};
            html += `<div class="api-phase-card" data-phase="${key}">
                <span class="api-phase-label">${_escapeHtml(label)}</span>
                <div class="api-phase-field">
                    <label>URL</label>
                    <input type="text" class="phase-input" data-phase="${key}" data-field="baseUrl" placeholder="继承" value="${_escapeHtml(ph.baseUrl || '')}" />
                </div>
                <div class="api-phase-field">
                    <label>Key</label>
                    <input type="password" class="phase-input" data-phase="${key}" data-field="apiKey" placeholder="继承" value="${_escapeHtml(ph.apiKey || '')}" autocomplete="off" />
                </div>
                <div class="api-phase-field">
                    <label>Model</label>
                    <input type="text" class="phase-input" data-phase="${key}" data-field="model" placeholder="继承" value="${_escapeHtml(ph.model || '')}" />
                </div>
            </div>`;
        });
        container.innerHTML = html;
    }

    function _populatePresetForm() {
        const p = _configState.presets[_activePresetKey] || {};
        document.getElementById('presetLabel').value = p.label || '';
        document.getElementById('presetBaseUrl').value = p.baseUrl || '';
        document.getElementById('presetApiKey').value = p.apiKey || '';
        document.getElementById('presetModel').value = p.model || '';
        const useMock = _configState.useMock !== false;
        document.querySelectorAll('.api-mode-seg').forEach(el => {
            el.classList.toggle('selected', (el.dataset.mode === 'mock') === useMock);
        });
        _renderPhaseCards();
        const deleteBtn = document.getElementById('presetDeleteBtn');
        if (deleteBtn) deleteBtn.style.display = Object.keys(_configState.presets).length > 1 ? '' : 'none';
    }

    function _readFormIntoState() {
        const mockSelected = document.querySelector('.api-mode-seg[data-mode="mock"].selected');
        _configState.useMock = !!mockSelected;
        if (!_activePresetKey || !_configState.presets[_activePresetKey]) return;
        const p = _configState.presets[_activePresetKey];
        const newLabel = document.getElementById('presetLabel').value.trim();
        p.label = newLabel || p.label || _activePresetKey;
        p.baseUrl = document.getElementById('presetBaseUrl').value.trim();
        p.apiKey = document.getElementById('presetApiKey').value.trim();
        p.model = document.getElementById('presetModel').value.trim();
        p.phases = p.phases || {};
        document.querySelectorAll('.phase-input').forEach(inp => {
            const phase = inp.dataset.phase;
            const field = inp.dataset.field;
            const val = inp.value.trim();
            if (!p.phases[phase]) p.phases[phase] = {};
            if (val) p.phases[phase][field] = val;
            else delete p.phases[phase][field];
        });
        Object.keys(p.phases).forEach(k => {
            if (Object.keys(p.phases[k]).length === 0) delete p.phases[k];
        });
    }

    function _loadConfig(raw) {
        raw = raw || {};
        const useMock = raw.useMock !== false && raw.use_mock !== false;
        let presets = {};
        let current = '';

        if (raw.presets && typeof raw.presets === 'object' && Object.keys(raw.presets).length > 0) {
            presets = JSON.parse(JSON.stringify(raw.presets));
            Object.keys(presets).forEach(k => { delete presets[k].useMock; });
            current = raw.current || Object.keys(presets)[0];
        } else if (raw.baseUrl || raw.apiKey || raw.model) {
            current = 'default';
            presets = { default: { label: 'Default', baseUrl: raw.baseUrl || '', apiKey: raw.apiKey || '', model: raw.model || '' } };
        } else {
            current = 'default';
            presets = { default: { label: 'Default', baseUrl: '', apiKey: '', model: '' } };
        }
        _configState = { useMock, current, presets };
        _activePresetKey = current || Object.keys(presets)[0];
    }

    function initApiConfigModal() {
        const modal = document.getElementById('apiConfigModal');
        const btn = document.getElementById('apiConfigBtn');
        const close = document.getElementById('apiConfigModalClose');
        const form = document.getElementById('apiConfigForm');
        const deleteBtn = document.getElementById('presetDeleteBtn');

        document.getElementById('apiModeMock')?.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelectorAll('.api-mode-seg').forEach(el => el.classList.toggle('selected', el.dataset.mode === 'mock'));
            _configState.useMock = true;
        });
        document.getElementById('apiModeLlm')?.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelectorAll('.api-mode-seg').forEach(el => el.classList.toggle('selected', el.dataset.mode === 'llm'));
            _configState.useMock = false;
        });

        btn?.addEventListener('click', async () => {
            try {
                const raw = await cfg.fetchApiConfig();
                _loadConfig(raw);
            } catch (e) {
                console.error('Failed to load config:', e);
                _loadConfig({});
            }
            _renderPresetCards();
            _populatePresetForm();
            _updateEditPanelVisibility();
            modal.style.display = 'block';
            document.body.style.overflow = 'hidden';
        });

        function closeModal() {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
        close?.addEventListener('click', closeModal);
        window.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

        form?.addEventListener('submit', async (e) => {
            e.preventDefault();
            _readFormIntoState();
            const presetsOut = JSON.parse(JSON.stringify(_configState.presets));
            Object.keys(presetsOut).forEach(k => { delete presetsOut[k].useMock; });
            const out = { useMock: _configState.useMock, current: _configState.current, presets: presetsOut };
            try {
                await cfg.saveApiConfig(out);
                closeModal();
            } catch (err) {
                console.error('Failed to save config:', err);
                alert('保存失败: ' + (err.message || 'Unknown error'));
            }
        });

        deleteBtn?.addEventListener('click', () => {
            const keys = Object.keys(_configState.presets);
            if (keys.length <= 1) return;
            delete _configState.presets[_activePresetKey];
            const remaining = Object.keys(_configState.presets);
            _configState.current = remaining[0];
            _activePresetKey = remaining[0];
            _renderPresetCards();
            _populatePresetForm();
            _updateEditPanelVisibility();
        });
    }

    window.MAARS.theme = { initTheme, applyTheme, toggleTheme, initApiConfigModal };
})();
