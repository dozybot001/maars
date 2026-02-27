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
        { key: 'execute', label: 'Executor Execute' },
        { key: 'validate', label: 'Executor Validate' },
    ];

    let _configState = { aiMode: 'mock', current: '', presets: {} };
    let _activePresetKey = '';

    const MODE_LABELS = { mock: 'Mock', llm: 'LLM', agent: 'Agent' };

    const MODE_DESCRIPTIONS = {
        mock: {
            title: 'Mock config',
            desc: 'Use mock data, no API key required. Planner and Executor return preset results for quick flow and UI testing.',
        },
        llm: {
            title: 'LLM config',
            desc: 'Planner and Executor both use LLM calls (single-turn). Planner decomposes tasks; Executor generates output once and validates. Select or create API config in Preset on the left.',
            presetNote: true,
        },
        agent: {
            title: 'Agent config',
            desc: 'Planner and Executor both use Agent mode (ReAct-style with tools). Planner: CheckAtomicity, Decompose, FormatTask, AddTasks, etc. Executor: ReadArtifact, ReadFile, WriteFile, Finish, ListSkills, LoadSkill. Each task runs in an isolated sandbox.',
            presetNote: true,
        },
    };

    const MODE_PARAMS = {
        mock: [
            { key: 'executionPassProbability', label: 'Execution pass rate', type: 'number', min: 0, max: 1, step: 0.05, default: 0.95, section: 'Mock', tip: 'Random pass probability for mock execution' },
            { key: 'validationPassProbability', label: 'Validation pass rate', type: 'number', min: 0, max: 1, step: 0.05, default: 0.95, section: 'Mock', tip: 'Random pass probability for mock validation' },
            { key: 'maxFailures', label: 'Max retries', type: 'number', min: 1, max: 10, default: 3, section: 'Mock', tip: 'Max retries after task failure' },
        ],
        llm: [
            { key: 'plannerLlmTemperature', label: 'Planner Temperature', type: 'number', min: 0, max: 2, step: 0.1, default: 0.3, section: 'Planner', tip: 'Temperature for Planner LLM calls (atomicity/decompose/format)' },
            { key: 'executorLlmTemperature', label: 'Executor Temperature', type: 'number', min: 0, max: 2, step: 0.1, default: 0.3, section: 'Executor', tip: 'Temperature for Executor single LLM output' },
            { key: 'maxFailures', label: 'Max retries', type: 'number', min: 1, max: 10, default: 3, section: 'Executor', tip: 'Max retries after execution/validation failure' },
        ],
        agent: [
            { key: 'plannerAgentMaxTurns', label: 'Planner max turns', type: 'number', min: 1, max: 50, default: 30, section: 'Planner Agent', tip: 'Max turns for Planner Agent loop' },
            { key: 'plannerLlmTemperature', label: 'Planner Temperature', type: 'number', min: 0, max: 2, step: 0.1, default: 0.3, section: 'Planner Agent', tip: 'Temperature for Planner Agent LLM' },
            { key: 'executorLlmTemperature', label: 'Executor Temperature', type: 'number', min: 0, max: 2, step: 0.1, default: 0.3, section: 'Executor Agent', tip: 'Temperature for Executor Agent LLM' },
            { key: 'executorAgentMaxTurns', label: 'Executor max turns', type: 'number', min: 1, max: 30, default: 15, section: 'Executor Agent', tip: 'Max turns for Executor Agent loop (incl. tool calls)' },
            { key: 'maxFailures', label: 'Max retries', type: 'number', min: 1, max: 10, default: 3, section: 'Executor Agent', tip: 'Max retries after execution/validation failure' },
        ],
    };

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
        let html = '';
        Object.keys(_configState.presets).forEach(key => {
            const preset = _configState.presets[key];
            const label = _escapeHtml(preset.label || key);
            const isActive = _configState.current === key;
            const meta = _escapeHtml(preset.model || _truncate(preset.baseUrl || '', 18)) || '—';
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

    function _getModeConfig(mode) {
        _configState.modeConfig = _configState.modeConfig || {};
        const defaults = {};
        (MODE_PARAMS[mode] || []).forEach(p => { defaults[p.key] = p.default; });
        const cfg = { ...defaults, ...(_configState.modeConfig[mode] || {}) };
        _configState.modeConfig[mode] = cfg;
        return cfg;
    }

    function _renderModePanel() {
        const container = document.getElementById('apiModeContent');
        const titleEl = document.getElementById('apiModePanelTitle');
        if (!container) return;
        const mode = _configState.aiMode || 'mock';
        const meta = MODE_DESCRIPTIONS[mode] || MODE_DESCRIPTIONS.mock;
        if (titleEl) titleEl.textContent = meta.title;

        const params = MODE_PARAMS[mode] || [];
        const cfg = _getModeConfig(mode);

        let html = `<div class="api-mode-desc">${_escapeHtml(meta.desc)}</div>`;
        if (params.length > 0) {
            const bySection = {};
            const sectionOrder = [];
            params.forEach(param => {
                const sec = param.section || '';
                if (!bySection[sec]) {
                    bySection[sec] = [];
                    if (sec) sectionOrder.push(sec);
                }
                bySection[sec].push(param);
            });
            sectionOrder.forEach(sec => {
                html += `<div class="api-mode-section"><h4 class="api-mode-section-title">${_escapeHtml(sec)}</h4><div class="api-mode-params">`;
                bySection[sec].forEach(param => {
                    const val = cfg[param.key] !== undefined ? cfg[param.key] : param.default;
                    const attrs = `data-mode="${_escapeHtmlAttr(mode)}" data-key="${_escapeHtmlAttr(param.key)}"`;
                    const tipAttr = param.tip ? ` title="${_escapeHtmlAttr(param.tip)}"` : '';
                    if (param.type === 'checkbox') {
                        const checked = val === true || val === 'true' || val === 1;
                        html += `<div class="api-field api-mode-field api-mode-field-checkbox"${tipAttr}>
                            <label for="mode-${param.key}">
                                <input type="checkbox" id="mode-${param.key}" ${attrs} ${checked ? 'checked' : ''} />
                                ${_escapeHtml(param.label)}
                            </label>
                            ${param.tip ? `<span class="api-mode-param-tip">${_escapeHtml(param.tip)}</span>` : ''}
                        </div>`;
                    } else {
                        const step = param.step !== undefined ? ` step="${param.step}"` : '';
                        const min = param.min !== undefined ? ` min="${param.min}"` : '';
                        const max = param.max !== undefined ? ` max="${param.max}"` : '';
                        html += `<div class="api-field api-mode-field"${tipAttr}>
                            <label for="mode-${param.key}">${_escapeHtml(param.label)}</label>
                            <input type="${param.type}" id="mode-${param.key}" ${attrs}${min}${max}${step} value="${_escapeHtmlAttr(String(val))}" />
                            ${param.tip ? `<span class="api-mode-param-tip">${_escapeHtml(param.tip)}</span>` : ''}
                        </div>`;
                    }
                });
                html += '</div></div>';
            });
        }
        if (meta.presetNote) {
            const currentKey = _configState.current;
            const preset = currentKey ? _configState.presets[currentKey] : null;
            const presetLabel = preset ? (preset.label || currentKey) : '—';
            const presetModel = preset ? (preset.model || '') : '';
            html += `<div class="api-mode-preset-info">
                <span class="api-mode-preset-label">Current preset</span>
                <div class="api-mode-preset-value">
                    <strong>${_escapeHtml(presetLabel)}</strong>
                    ${presetModel ? `<span class="api-mode-preset-model">${_escapeHtml(presetModel)}</span>` : ''}
                </div>
                <p class="api-mode-preset-hint">Switch or edit API config in Preset on the left</p>
                ${currentKey ? `<button type="button" class="api-btn-ghost api-mode-edit-preset" data-preset="${_escapeHtmlAttr(currentKey)}">Edit this preset</button>` : ''}
            </div>`;
        }
        container.innerHTML = html;
    }

    function _readModeFormIntoState() {
        _configState.modeConfig = _configState.modeConfig || {};
        document.querySelectorAll('.api-mode-field input').forEach(inp => {
            const mode = inp.dataset.mode;
            const key = inp.dataset.key;
            if (!mode || !key) return;
            if (!_configState.modeConfig[mode]) _configState.modeConfig[mode] = {};
            const param = (MODE_PARAMS[mode] || []).find(x => x.key === key);
            const defaultVal = param ? param.default : 0;
            if (param?.type === 'checkbox') {
                _configState.modeConfig[mode][key] = inp.checked;
            } else {
                const raw = inp.value.trim();
                if (param?.type === 'number') {
                    const num = parseFloat(raw);
                    _configState.modeConfig[mode][key] = isNaN(num) ? defaultVal : num;
                } else {
                    _configState.modeConfig[mode][key] = raw || defaultVal;
                }
            }
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
            _renderModePanel();
        }
        _renderPresetMenuItems();
    }

    function _updateEditPanelVisibility() {
        const titleEl = document.getElementById('presetEditTitle');
        if (titleEl) {
            titleEl.textContent = _activePresetKey
                ? 'Edit: ' + (_configState.presets[_activePresetKey]?.label || _activePresetKey)
                : 'Select preset';
        }
    }

    function _renderPhaseCards() {
        const container = document.getElementById('phaseCards');
        if (!container) return;
        const preset = _configState.presets[_activePresetKey] || {};
        const phases = preset.phases || {};
        let html = '';
        PHASES.forEach(({ key, label }) => {
            const phaseCfg = phases[key] || {};
            html += `<div class="api-phase-card" data-phase="${key}">
                <span class="api-phase-label">${_escapeHtml(label)}</span>
                <div class="api-phase-field">
                    <label>URL</label>
                    <input type="text" class="phase-input" data-phase="${key}" data-field="baseUrl" placeholder="Inherit" value="${_escapeHtmlAttr(phaseCfg.baseUrl || '')}" />
                </div>
                <div class="api-phase-field">
                    <label>Key</label>
                    <input type="password" class="phase-input" data-phase="${key}" data-field="apiKey" placeholder="Inherit" value="${_escapeHtmlAttr(phaseCfg.apiKey || '')}" autocomplete="off" />
                </div>
                <div class="api-phase-field">
                    <label>Model</label>
                    <input type="text" class="phase-input" data-phase="${key}" data-field="model" placeholder="Inherit" value="${_escapeHtmlAttr(phaseCfg.model || '')}" />
                </div>
            </div>`;
        });
        container.innerHTML = html;
    }

    function _populatePresetForm() {
        const preset = _configState.presets[_activePresetKey] || {};
        document.getElementById('presetLabel').value = preset.label || '';
        document.getElementById('presetBaseUrl').value = preset.baseUrl || '';
        document.getElementById('presetApiKey').value = preset.apiKey || '';
        document.getElementById('presetModel').value = preset.model || '';
        _renderPhaseCards();
        const deleteBtn = document.getElementById('presetDeleteBtn');
        if (deleteBtn) deleteBtn.style.display = Object.keys(_configState.presets).length > 1 ? '' : 'none';
    }

    function _readFormIntoState() {
        if (!_activePresetKey || !_configState.presets[_activePresetKey]) return;
        const preset = _configState.presets[_activePresetKey];
        preset.label = document.getElementById('presetLabel').value.trim() || preset.label || _activePresetKey;
        preset.baseUrl = document.getElementById('presetBaseUrl').value.trim();
        preset.apiKey = document.getElementById('presetApiKey').value.trim();
        preset.model = document.getElementById('presetModel').value.trim();
        preset.phases = preset.phases || {};
        document.querySelectorAll('.phase-input').forEach(inp => {
            const phase = inp.dataset.phase;
            const field = inp.dataset.field;
            const val = inp.value.trim();
            if (!preset.phases[phase]) preset.phases[phase] = {};
            if (val) preset.phases[phase][field] = val;
            else delete preset.phases[phase][field];
        });
        Object.keys(preset.phases).forEach(k => {
            if (Object.keys(preset.phases[k]).length === 0) delete preset.phases[k];
        });
    }

    function _loadConfig(raw) {
        raw = raw || {};
        const aiMode = raw.aiMode || 'mock';

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
        const modeConfig = raw.modeConfig && typeof raw.modeConfig === 'object'
            ? JSON.parse(JSON.stringify(raw.modeConfig))
            : {};
        _configState = { aiMode, current, presets, modeConfig };
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

        document.getElementById('apiConfigMain')?.addEventListener('click', (e) => {
            const editBtn = e.target.closest('.api-mode-edit-preset');
            if (editBtn?.dataset?.preset) {
                e.preventDefault();
                _selectItem('preset:' + editBtn.dataset.preset);
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
                alert('Failed to load config: ensure backend is running (e.g. uvicorn main:asgi_app) and refresh the page.');
                return;
            }
            _loadConfig(raw);
            _renderPresetMenuItems();
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
            _readModeFormIntoState();
            try {
                await cfg.saveApiConfig(_configState);
                closeModal();
            } catch (err) {
                console.error('Save config:', err);
                alert('Save failed: ' + (err.message || 'Unknown error'));
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
