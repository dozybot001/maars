import { connectSSE } from './api.js';
import { initPipelineUI, syncFromAPI } from './pipeline-ui.js';
import { initLogViewer } from './log-viewer.js';
import { initProcessViewer } from './process-viewer.js';
import { initModal } from './modal.js';
import { syncSystemStatus } from './shared.js';

initPipelineUI();
initLogViewer();
initProcessViewer();
initModal();

connectSSE();
syncFromAPI();

async function checkDocker() {
  const el = document.getElementById('system-status');
  if (!el) return;
  try {
    const res = await fetch('/api/docker/status');
    const data = await res.json();
    el.dataset.docker = data.connected ? 'connected' : 'disconnected';
  } catch {
    el.dataset.docker = 'disconnected';
  }
  syncSystemStatus();
}
checkDocker();
setInterval(checkDocker, 30000);
