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

    let _configState = { aiMode: 'mock', current: '', presets: {} };
    let _activePresetKey = '';

    const MODE_LABELS = { mock: 'Mock', llm: 'LLM', 'llm-agent': 'LLM + Agent' };

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

    const _escapeHtml = (() => {
        const u = window.MAARS?.utils;
        return (s) => (u?.escapeHtml ? u.escapeHtml(s) : (s ? String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') : ''));
    })();
    const _escapeHtmlAttr = (() => {
        const u = window.MAARS?.utils;
        return (s) => (u?.escapeHtmlAttr ? u.escapeHtmlAttr(s) : (s ? String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;') : ''));
    })();

    function _renderPresetMenuItems() {
        const container = document.getElementById('apiPresetMenuList');
        if (!container) return;
        const keys = Object.keys(_configState.presets);
        let html = '';
        keys.forEach(key => {
            const p = _configState.presets[key];
            const label = _escapeHtml(p.label || key);
            const isActive = _configState.current === key;
            const meta = _escapeHtml(p.model || _truncate(p.baseUrl || '', 18)) || '—';
            html += `<button type="button" class="api-menu-item${isActive ? ' active' : ''}" data-item="preset:${key}">
                <span class="api-menu-item-name">${label}</span>
                <span class="api-menu-item-meta">${meta}</span>
            </button>`;
        });
        container.innerHTML = html;
    }

    function _syncModeActive() {
        document.querySelectorAll('#apiModeMenuList .api-menu-item').forEach(el => {
            el.classList.toggle('active', el.dataset.item === _configState.aiMode);
        });
    }

    function _selectItem(itemId) {
        _readFormIntoState();
        const isPreset = itemId.startsWith('preset:');
        const presetKey = isPreset ? itemId.slice(7) : '';
        if (isPreset) {
            _activePresetKey = presetKey;
            _configState.current = presetKey;
            _populatePresetForm();
            _updateEditPanelVisibility();
            document.querySelectorAll('#apiPresetMenuList .api-menu-item').forEach(el => {
                el.classList.toggle('active', el.dataset.item === itemId);
            });
            document.getElementById('apiPanelMode')?.classList.remove('active');
            document.getElementById('presetEditPanel')?.classList.add('active');
        } else {
            _configState.aiMode = itemId;
            _syncModeActive();
            document.getElementById('apiPanelMode')?.classList.add('active');
            document.getElementById('presetEditPanel')?.classList.remove('active');
            const titleEl = document.getElementById('apiModePanelTitle');
            if (titleEl) titleEl.textContent = MODE_LABELS[itemId] + ' 配置';
        }
        _renderPresetMenuItems();
    }

    function _renderAllMenuItems() {
        _renderPresetMenuItems();
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
                    <input type="text" class="phase-input" data-phase="${key}" data-field="baseUrl" placeholder="继承" value="${_escapeHtmlAttr(ph.baseUrl || '')}" />
                </div>
                <div class="api-phase-field">
                    <label>Key</label>
                    <input type="password" class="phase-input" data-phase="${key}" data-field="apiKey" placeholder="继承" value="${_escapeHtmlAttr(ph.apiKey || '')}" autocomplete="off" />
                </div>
                <div class="api-phase-field">
                    <label>Model</label>
                    <input type="text" class="phase-input" data-phase="${key}" data-field="model" placeholder="继承" value="${_escapeHtmlAttr(ph.model || '')}" />
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
        _renderPhaseCards();
        const deleteBtn = document.getElementById('presetDeleteBtn');
        if (deleteBtn) deleteBtn.style.display = Object.keys(_configState.presets).length > 1 ? '' : 'none';
    }

    function _readFormIntoState() {
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
        let aiMode = raw.aiMode || raw.ai_mode;
        if (!aiMode && ('useMock' in raw || 'use_mock' in raw)) {
            aiMode = raw.useMock !== false && raw.use_mock !== false ? 'mock'
                : (raw.executorAgentMode || raw.executor_agent_mode ? 'llm-agent' : 'llm');
        }
        aiMode = aiMode || 'mock';

        let presets = {};
        let current = '';
        if (raw.presets && typeof raw.presets === 'object' && Object.keys(raw.presets).length > 0) {
            presets = JSON.parse(JSON.stringify(raw.presets));
            current = raw.current || Object.keys(presets)[0];
        } else if (raw.baseUrl || raw.apiKey || raw.model) {
            current = 'default';
            presets = { default: { label: 'Default', baseUrl: raw.baseUrl || '', apiKey: raw.apiKey || '', model: raw.model || '' } };
        } else {
            current = 'default';
            presets = { default: { label: 'Default', baseUrl: '', apiKey: '', model: '' } };
        }
        _configState = { aiMode, current, presets };
        _activePresetKey = current || Object.keys(presets)[0];
    }

    function initApiConfigModal() {
        const modal = document.getElementById('apiConfigModal');
        const btn = document.getElementById('apiConfigBtn');
        const close = document.getElementById('apiConfigModalClose');
        const deleteBtn = document.getElementById('presetDeleteBtn');
        const sidebar = document.querySelector('.api-sidebar-menu');

        sidebar?.addEventListener('click', (e) => {
            const item = e.target.closest('.api-menu-item');
            if (item?.dataset?.item) {
                e.preventDefault();
                _selectItem(item.dataset.item);
            }
        });

        document.getElementById('presetAddBtn')?.addEventListener('click', (e) => {
            e.preventDefault();
            _readFormIntoState();
            const key = _generateKey('new');
            _configState.presets[key] = { label: 'New Preset', baseUrl: '', apiKey: '', model: '' };
            _configState.current = key;
            _selectItem('preset:' + key);
        });

        btn?.addEventListener('click', async () => {
            let raw;
            try {
                raw = await cfg.fetchApiConfig();
            } catch (e) {
                console.error('Failed to load config:', e);
                alert('无法读取配置：请确保后端已启动（如 uvicorn main:asgi_app），并刷新页面重试。');
                return;
            }
            _loadConfig(raw);
            _renderAllMenuItems();
            _syncModeActive();
            const keys = Object.keys(_configState.presets);
            const current = _configState.current && keys.includes(_configState.current)
                ? _configState.current
                : keys[0];
            if (current) {
                _activePresetKey = current;
                _configState.current = current;
                _populatePresetForm();
                _updateEditPanelVisibility();
                document.querySelectorAll('#apiPresetMenuList .api-menu-item').forEach(el => {
                    el.classList.toggle('active', el.dataset.item === 'preset:' + current);
                });
            }
            document.getElementById('presetEditPanel')?.classList.add('active');
            document.getElementById('apiPanelMode')?.classList.remove('active');
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        });

        function closeModal() {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
        close?.addEventListener('click', closeModal);
        window.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

        document.getElementById('apiGlobalSaveBtn')?.addEventListener('click', async () => {
            _readFormIntoState();
            try {
                await cfg.saveApiConfig(_configState);
                closeModal();
            } catch (err) {
                console.error('Save config:', err);
                alert('保存失败: ' + (err.message || 'Unknown error'));
            }
        });

        deleteBtn?.addEventListener('click', () => {
            const keys = Object.keys(_configState.presets);
            if (keys.length <= 1) return;
            delete _configState.presets[_activePresetKey];
            const remaining = Object.keys(_configState.presets);
            _configState.current = remaining[0];
            _selectItem('preset:' + remaining[0]);
        });
    }

    window.MAARS.theme = { initTheme, applyTheme, toggleTheme, initApiConfigModal };
})();
