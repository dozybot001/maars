import { emit } from './events.js';

const BASE = '/api';

export async function startPipeline(input) {
  const res = await fetch(`${BASE}/pipeline/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input }),
  });
  if (!res.ok) throw new Error(`Start failed: ${res.status}`);
  return res.json();
}

export async function fetchStatus() {
  const res = await fetch(`${BASE}/pipeline/status`);
  if (!res.ok) throw new Error(`Status fetch failed: ${res.status}`);
  const status = await res.json();
  // Emit state events to sync UI with backend reality
  for (const stage of status.stages) {
    emit('stage:state', { stage: stage.name, data: stage.state });
  }
  return status;
}

export async function stageAction(stageName, action) {
  const res = await fetch(`${BASE}/stage/${stageName}/${action}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`${action} failed: ${res.status}`);
  return res.json();
}

export function connectSSE() {
  const source = new EventSource(`${BASE}/events`);

  source.addEventListener('state', (e) => {
    const data = JSON.parse(e.data);
    emit('stage:state', data);
  });

  source.addEventListener('chunk', (e) => {
    const data = JSON.parse(e.data);
    emit('log:chunk', data);
  });

  source.addEventListener('task_state', (e) => {
    const data = JSON.parse(e.data);
    emit('task:state', data);
  });

  source.addEventListener('exec_tree', (e) => {
    const data = JSON.parse(e.data);
    emit('exec:tree', data);
  });

  source.addEventListener('tree', (e) => {
    const data = JSON.parse(e.data);
    emit('plan:tree', data);
  });

  source.addEventListener('error', (e) => {
    // SSE native error (connection lost)
    if (e.data) {
      const data = JSON.parse(e.data);
      emit('stage:error', data);
    }
  });

  source.onerror = () => {
    // EventSource will auto-reconnect
    console.warn('[SSE] Connection lost, reconnecting...');
  };

  return source;
}
