import { fetchStatus, connectSSE } from './api.js';
import { initPipelineUI } from './pipeline-ui.js';
import { initLogViewer } from './log-viewer.js';
import { initProcessViewer } from './process-viewer.js';
import { initModal } from './modal.js';

// Initialize modules
initPipelineUI();
initLogViewer();
initProcessViewer();
initModal();

// Sync with backend state first, then connect SSE for incremental updates
fetchStatus().catch(() => {});
connectSSE();

// Docker status indicator
async function checkDocker() {
  const el = document.getElementById('docker-status');
  if (!el) return;
  try {
    const res = await fetch('/api/docker/status');
    const data = await res.json();
    el.classList.remove('docker-unknown', 'docker-connected', 'docker-disconnected');
    if (data.connected) {
      el.classList.add('docker-connected');
      el.title = 'Docker connected';
    } else {
      el.classList.add('docker-disconnected');
      el.title = `Docker: ${data.error || 'not available'}`;
    }
  } catch {
    el.classList.remove('docker-unknown', 'docker-connected', 'docker-disconnected');
    el.classList.add('docker-disconnected');
    el.title = 'Cannot check Docker status';
  }
}
checkDocker();
setInterval(checkDocker, 30000);
