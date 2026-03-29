import { on } from './events.js';
import { startPipeline, stageAction } from './api.js';

/**
 * Progress bar + command palette button state machine.
 *
 * Pipeline states: idle → running → (paused | completed | failed)
 * Button rules: at most ONE button enabled at any time.
 *   idle:      Start enabled (only if input non-empty)
 *   running:   Pause enabled
 *   paused:    Resume enabled
 *   completed: Start enabled (for new run)
 *   failed:    Start enabled (for retry)
 */

const NODE_ORDER = ['refine', 'calibrate', 'strategy', 'decompose', 'execute', 'evaluate', 'write'];
const RESEARCH_PHASES = new Set(['calibrate', 'strategy', 'decompose', 'execute', 'evaluate']);

const nodeStates = {};
NODE_ORDER.forEach((n) => { nodeStates[n] = 'idle'; });

const stageStates = { refine: 'idle', research: 'idle', write: 'idle' };

let inputEl, startBtn, pauseBtn, resumeBtn, overlay;

export function initPipelineUI() {
  inputEl = document.getElementById('research-input');
  startBtn = document.getElementById('start-btn');
  pauseBtn = document.getElementById('pause-btn');
  resumeBtn = document.getElementById('resume-btn');
  overlay = document.getElementById('cmd-overlay');

  // --- Stage state events ---
  on('stage:state', ({ stage, data }) => {
    stageStates[stage] = data;

    if (stage === 'refine') {
      updateNode('refine', stageToNodeState(data));
    } else if (stage === 'write') {
      updateNode('write', stageToNodeState(data));
    } else if (stage === 'research') {
      if (data === 'completed') {
        RESEARCH_PHASES.forEach((n) => updateNode(n, 'done'));
      } else if (data === 'failed') {
        const active = [...RESEARCH_PHASES].find((n) => nodeStates[n] === 'active');
        if (active) updateNode(active, 'failed');
      } else if (data === 'paused') {
        const active = [...RESEARCH_PHASES].find((n) => nodeStates[n] === 'active');
        if (active) updateNode(active, 'paused');
      } else if (data === 'idle') {
        RESEARCH_PHASES.forEach((n) => updateNode(n, 'idle'));
      }
    }
    syncButtons();
  });

  // --- Research sub-phase events ---
  on('stage:phase', ({ data }) => {
    const phase = data;
    if (!RESEARCH_PHASES.has(phase)) return;
    for (const n of RESEARCH_PHASES) {
      if (n === phase) {
        updateNode(n, 'active');
        break;
      }
      if (nodeStates[n] === 'active' || nodeStates[n] === 'idle') {
        updateNode(n, 'done');
      }
    }
  });

  // --- Button handlers ---
  startBtn.addEventListener('click', handleStart);
  pauseBtn.addEventListener('click', handlePause);
  resumeBtn.addEventListener('click', handleResume);
  inputEl.addEventListener('input', syncButtons);
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleStart();
  });

  // --- Command palette (Cmd+K / Ctrl+K) ---
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      overlay.classList.toggle('hidden');
      if (!overlay.classList.contains('hidden')) inputEl.focus();
    }
    if (e.key === 'Escape' && !overlay.classList.contains('hidden')) {
      overlay.classList.add('hidden');
    }
  });

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) overlay.classList.add('hidden');
  });

  syncButtons();
}

// --- Button state machine ---

function getPipelineState() {
  if (Object.values(stageStates).some((s) => s === 'running')) return 'running';
  if (Object.values(stageStates).some((s) => s === 'paused')) return 'paused';
  return 'idle'; // idle, completed, or failed — all allow Start
}

function syncButtons() {
  const state = getPipelineState();
  const hasInput = inputEl && inputEl.value.trim().length > 0;

  startBtn.disabled = !(state !== 'running' && state !== 'paused' && hasInput);
  pauseBtn.disabled = state !== 'running';
  resumeBtn.disabled = state !== 'paused';
}

async function handleStart() {
  const text = inputEl.value.trim();
  if (!text) return;

  overlay.classList.add('hidden');
  try {
    await startPipeline(text);
  } catch (err) {
    console.error('Failed to start pipeline:', err);
  }
}

async function handlePause() {
  const running = Object.keys(stageStates).find((s) => stageStates[s] === 'running');
  if (!running) return;
  try { await stageAction(running, 'stop'); }
  catch (err) { console.error('Pause error:', err); }
}

async function handleResume() {
  const paused = Object.keys(stageStates).find((s) => stageStates[s] === 'paused');
  if (!paused) return;
  try { await stageAction(paused, 'resume'); }
  catch (err) { console.error('Resume error:', err); }
}

// --- Progress bar helpers ---

function stageToNodeState(state) {
  if (state === 'running') return 'active';
  if (state === 'completed') return 'done';
  return state;
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
    if (line) {
      line.dataset.filled = (nodeStates[name] === 'done') ? 'true' : 'false';
    }
  }
}
