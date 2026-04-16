import { on } from './events.js';
import { startPipeline, pipelineAction, fetchStatus } from './api.js';
import { pauseTimers, resumeTimers } from './log-viewer.js';

const NODE_ORDER = ['refine', 'calibrate', 'strategy', 'decompose', 'execute', 'evaluate', 'write'];
const NODE_SET = new Set(NODE_ORDER);
const RESEARCH_PHASES = new Set(['calibrate', 'strategy', 'decompose', 'execute', 'evaluate']);
const nodeStates = {};
NODE_ORDER.forEach((n) => { nodeStates[n] = 'idle'; });
let seenNodes = new Set();
let inputEl, pauseBtn, resumeBtn;

export function initPipelineUI() {
  inputEl = document.getElementById('research-input');
  pauseBtn = document.getElementById('pause-btn');
  resumeBtn = document.getElementById('resume-btn');

  on('sse', (event) => {
    const { stage, phase, chunk, status, task_id, error } = event;
    if (!stage) return;

    const isDoneSignal = !chunk && !status && !task_id && !error;
    if (isDoneSignal) {
      if (stage === 'research' && RESEARCH_PHASES.has(phase)) {
        updateNode(phase, 'done');
        seenNodes.add(phase);
        syncButtons();
        return;
      }
      if ((stage === 'refine' || stage === 'write') && !phase) {
        updateNode(stage, 'done');
        seenNodes.add(stage);
        syncButtons();
        return;
      }
    }

    const node = (stage === 'research' && phase) ? phase : stage;
    if (!NODE_SET.has(node)) return;
    if (seenNodes.has(node)) return;
    seenNodes.add(node);
    for (const n of NODE_ORDER) {
      if (n === node) { updateNode(n, 'active'); break; }
      if (nodeStates[n] !== 'done') updateNode(n, 'done');
    }
    syncButtons();
  });

  pauseBtn.addEventListener('click', handlePause);
  resumeBtn.addEventListener('click', handleResume);
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleStart();
    if ((e.metaKey || e.ctrlKey) && e.key === 'e') {
      e.preventDefault();
      inputEl.value = 'showcase/example_idea.md';
    }
  });
  syncButtons();

  // Fallback: poll status every 3s to keep buttons in sync
  // in case SSE events are missed (reconnection gaps, etc.)
  setInterval(() => {
    const anyActive = NODE_ORDER.some((n) => nodeStates[n] === 'active');
    const anyPaused = NODE_ORDER.some((n) => nodeStates[n] === 'paused');
    if (!anyActive && !anyPaused) syncFromAPI();
  }, 3000);
}

export async function syncFromAPI() {
  const status = await fetchStatus();
  if (!status) return;
  for (const st of status.stages) {
    if (st.state === 'completed') {
      if (st.name === 'refine') { updateNode('refine', 'done'); seenNodes.add('refine'); }
      else if (st.name === 'research') { RESEARCH_PHASES.forEach((n) => { updateNode(n, 'done'); seenNodes.add(n); }); }
      else if (st.name === 'write') { updateNode('write', 'done'); seenNodes.add('write'); }
    } else if (st.state === 'running') {
      if (st.name === 'refine') { updateNode('refine', 'active'); seenNodes.add('refine'); }
      else if (st.name === 'write') { updateNode('write', 'active'); seenNodes.add('write'); }
      else if (st.name === 'research' && st.phase) {
        for (const n of ['calibrate', 'strategy', 'decompose', 'execute', 'evaluate']) {
          seenNodes.add(n);
          if (n === st.phase) { updateNode(n, 'active'); break; }
          updateNode(n, 'done');
        }
      }
    } else if (st.state === 'paused') {
      const active = NODE_ORDER.find((n) => nodeStates[n] === 'active');
      if (active) updateNode(active, 'paused');
    }
  }
  syncButtons();
}

function syncButtons() {
  const hasActive = NODE_ORDER.some((n) => nodeStates[n] === 'active');
  const hasPaused = NODE_ORDER.some((n) => nodeStates[n] === 'paused');
  pauseBtn.disabled = !hasActive;
  resumeBtn.disabled = !hasPaused;
  pauseBtn.textContent = 'Pause';
  inputEl.disabled = hasActive;
}

async function handleStart() {
  const text = inputEl.value.trim();
  if (!text) return;
  const hasActive = NODE_ORDER.some((n) => nodeStates[n] === 'active');
  const hasPaused = NODE_ORDER.some((n) => nodeStates[n] === 'paused');
  if (hasActive || hasPaused) return;
  inputEl.disabled = true;
  seenNodes.clear();
  NODE_ORDER.forEach((n) => updateNode(n, 'idle'));
  syncButtons();
  try { await startPipeline(text); }
  catch (err) {
    console.error('Failed to start pipeline:', err);
    inputEl.disabled = false;
    syncButtons();
  }
}

async function handlePause() {
  pauseBtn.disabled = true;
  pauseBtn.textContent = 'Pausing...';
  try { await pipelineAction('stop'); pauseTimers(); await syncFromAPI(); }
  catch (err) { console.error('Pause error:', err); }
}

async function handleResume() {
  try {
    resumeTimers();
    await pipelineAction('resume');
    const paused = NODE_ORDER.find((n) => nodeStates[n] === 'paused');
    if (paused) updateNode(paused, 'active');
    syncButtons();
  } catch (err) { console.error('Resume error:', err); }
}

function updateNode(name, state) {
  nodeStates[name] = state;
  const el = document.querySelector(`.progress-node[data-node="${name}"]`);
  if (el) el.dataset.state = state;
  updateLines();
}

function updateLines() {
  for (let i = 0; i < NODE_ORDER.length; i++) {
    const name = NODE_ORDER[i];
    const line = document.querySelector(`.progress-line[data-after="${name}"]`);
    if (line) line.dataset.filled = (nodeStates[name] === 'done') ? 'true' : 'false';
  }
}
