import { startPipeline, fetchStatus, connectSSE } from './api.js';
import { initPipelineUI } from './pipeline-ui.js';
import { initLogViewer } from './log-viewer.js';
import { initProcessViewer } from './process-viewer.js';

// Initialize modules
initPipelineUI();
initLogViewer();
initProcessViewer();

// Sync with backend state first, then connect SSE for incremental updates
fetchStatus().catch(() => {});
connectSSE();

// Input handling
const input = document.getElementById('research-input');
const startBtn = document.getElementById('start-btn');

async function handleStart() {
  const text = input.value.trim();
  if (!text) return;

  startBtn.disabled = true;
  input.disabled = true;

  try {
    await startPipeline(text);
  } catch (err) {
    console.error('Failed to start pipeline:', err);
    alert('Failed to start pipeline. Check console for details.');
  } finally {
    startBtn.disabled = false;
    input.disabled = false;
  }
}

input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') handleStart();
});

startBtn.addEventListener('click', handleStart);
