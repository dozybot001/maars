/**
 * MAARS WebSocket - Socket.io 连接，仅转发后端事件为前端 maars:* 事件。
 * 各模块自行监听事件处理，websocket 不直接调用业务模块。
 */
(function () {
    'use strict';
    const cfg = window.MAARS?.config;
    if (!cfg) return;

    const state = window.MAARS.state || {};
    state.socket = state.socket ?? null;
    window.MAARS.state = state;

    async function syncExecutionStateOnConnect() {
        if (!cfg?.resolvePlanIds) return;
        try {
            const { ideaId, planId } = await cfg.resolvePlanIds();
            const res = await cfg.fetchWithSession(`${cfg.API_BASE_URL}/execution/status?ideaId=${encodeURIComponent(ideaId)}&planId=${encodeURIComponent(planId)}`);
            const data = await res.json();
            if (!data.tasks?.length) return;
            document.dispatchEvent(new CustomEvent('maars:execution-sync', { detail: data }));
        } catch (_) {
            /* ignore sync errors */
        }
    }

    function bindSocketEvents(socket) {
        socket.on('connect', () => {
            console.log('WebSocket connected');
            syncExecutionStateOnConnect();
        });
        socket.on('disconnect', () => console.log('WebSocket disconnected'));

        socket.on('plan-start', () => {});
        socket.on('idea-start', () => {});

        socket.on('idea-error', (data) => {
            document.dispatchEvent(new CustomEvent('maars:idea-error', { detail: { error: data?.error } }));
        });
        socket.on('idea-complete', (data) => {
            document.dispatchEvent(new CustomEvent('maars:idea-complete', { detail: data }));
        });

        window.MAARS?.wsHandlers?.thinking?.register(socket);

        socket.on('plan-tree-update', (data) => {
            document.dispatchEvent(new CustomEvent('maars:plan-tree-update', { detail: data }));
        });

        socket.on('plan-complete', (data) => {
            document.dispatchEvent(new CustomEvent('maars:plan-complete', { detail: data }));
        });

        socket.on('plan-error', (data) => {
            document.dispatchEvent(new CustomEvent('maars:plan-error', { detail: { error: data?.error } }));
        });

        socket.on('paper-start', () => {});
        socket.on('paper-complete', (data) => {
            document.dispatchEvent(new CustomEvent('maars:paper-complete', { detail: data }));
        });
        socket.on('paper-error', (data) => {
            document.dispatchEvent(new CustomEvent('maars:paper-error', { detail: { error: data?.error } }));
        });

        socket.on('execution-layout', (data) => {
            document.dispatchEvent(new CustomEvent('maars:execution-layout', { detail: data }));
        });

        socket.on('task-start', () => {});

        socket.on('task-states-update', (data) => {
            document.dispatchEvent(new CustomEvent('maars:task-states-update', { detail: data }));
        });

        socket.on('task-output', (data) => {
            document.dispatchEvent(new CustomEvent('maars:task-output', { detail: data }));
        });

        socket.on('task-error', (data) => {
            document.dispatchEvent(new CustomEvent('maars:task-error', { detail: data }));
        });

        socket.on('task-complete', (data) => {
            console.log(`Execution complete: ${data.completed}/${data.total} tasks completed`);
            document.dispatchEvent(new CustomEvent('maars:task-complete', { detail: data }));
        });
    }

    async function init() {
        if (state.socket && state.socket.connected) return;
        const creds = await cfg.ensureSession?.();
        state.socket = io(cfg.WS_URL, {
            reconnection: true,
            reconnectionAttempts: 10,
            reconnectionDelay: 1000,
            auth: {
                sessionId: creds?.sessionId || cfg.getSessionId?.(),
                sessionToken: creds?.sessionToken || cfg.getSessionToken?.(),
            },
        });
        bindSocketEvents(state.socket);
    }

    async function ensureConnected(timeoutMs = 4000) {
        if (state.socket && state.socket.connected) return state.socket;
        await init();
        const startedAt = Date.now();
        while (Date.now() - startedAt < timeoutMs) {
            if (state.socket && state.socket.connected) return state.socket;
            await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return state.socket;
    }

    async function requireConnected(timeoutMs = 4000) {
        const socket = await ensureConnected(timeoutMs);
        if (socket && socket.connected) return socket;
        alert('WebSocket not connected. Please wait and try again.');
        return null;
    }

    window.MAARS.ws = { init, ensureConnected, requireConnected };
})();
