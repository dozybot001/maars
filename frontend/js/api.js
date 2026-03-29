import { emit } from './events.js';
import { safeParse } from './shared.js';

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

  for (const [event, signal] of [
    ['state', 'stage:state'],
    ['phase', 'stage:phase'],
    ['chunk', 'log:chunk'],
    ['task_state', 'task:state'],
    ['exec_tree', 'exec:tree'],
    ['tree', 'plan:tree'],
    ['tokens', 'log:tokens'],
    ['document', 'doc:ready'],
    ['score', 'score:update'],
  ]) {
    source.addEventListener(event, (e) => {
      const data = safeParse(e);
      if (data) emit(signal, data);
    });
  }

  source.addEventListener('error', (e) => {
    if (e.data) {
      const data = safeParse(e);
      if (data) emit('stage:error', data);
    }
  });

  source.onerror = () => {
    // EventSource will auto-reconnect
    console.warn('[SSE] Connection lost, reconnecting...');
  };

  return source;
}
