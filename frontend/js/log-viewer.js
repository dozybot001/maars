import { on } from './events.js';
import { createAutoScroller } from './autoscroll.js';
import { STAGE_LABELS, createFold, appendSeparator } from './shared.js';

let logOutput;
let scroller;
let activeStage = null;
let currentSection = null;

// Phase groups (level 2) — { label, body }
let phaseGroups = {};
let currentPhaseName = null;

// Task groups (within Execute phase) — { label, body }
let taskGroups = {};
let taskDescriptions = {};

// Chunk text blocks — call_id → DOM element
let callBlocks = {};
let callScrollers = {};

// Elapsed timer
let timerBadge = null;
let timerInterval = null;
let timerStart = null;
let totalTokens = 0;
let tokenBadge = null;

// Activity indicator
let activityBadge = null;
let lastActivityTime = null;
let activityInterval = null;

/** Current write target: task body > phase body > section. */
function currentTarget(taskId) {
  if (taskId && taskGroups[taskId]) return taskGroups[taskId].body;
  if (currentPhaseName && phaseGroups[currentPhaseName]) return phaseGroups[currentPhaseName].body;
  return currentSection;
}

export function initLogViewer() {
  logOutput = document.getElementById('log-output');
  scroller = createAutoScroller(logOutput);
  tokenBadge = document.getElementById('token-estimate');
  timerBadge = document.getElementById('elapsed-timer');
  activityBadge = document.getElementById('activity-indicator');

  wireCopyButton('copy-log', document.getElementById('log-output'));
  wireCopyButton('copy-process', document.getElementById('process-body'));

  // --- Stage transitions (level 1) ---
  on('stage:state', ({ stage, data }) => {
    if (data === 'idle') {
      logOutput.innerHTML = '';
      resetState();
      stopTimer();
      stopActivity();
      scroller.reset();
    } else if (data === 'completed' && stage === 'write') {
      stopTimer();
      stopActivity();
    } else if (data === 'failed') {
      stopTimer();
      stopActivity();
    } else if (data === 'paused' || data === 'pausing') {
      stopActivity();
    }
    if (data === 'running' && stage !== activeStage) {
      if (!timerStart) startTimer();
      if (currentSection && !currentSection.classList.contains('user-expanded')) {
        currentSection.classList.add('collapsed');
        const prevSep = currentSection.previousElementSibling;
        if (prevSep) prevSep.classList.add('is-collapsed');
      }
      activeStage = stage;
      resetPhaseState();
      currentSection = appendSeparator(logOutput, STAGE_LABELS[stage] || stage.toUpperCase(), scroller);
    }
  });

  // (Phase groups on left panel are created by level-2 chunk labels below.
  //  stage:phase is only used by the right panel and progress bar.)

  // --- Task state: auto-collapse completed/failed tasks ---
  on('task:state', ({ data }) => {
    const { task_id, status } = data;
    const group = taskGroups[task_id];
    if (!group) return;
    if ((status === 'completed' || status === 'failed') && !group.body.classList.contains('user-expanded')) {
      group.body.classList.add('collapsed');
      group.label.classList.add('is-collapsed');
    }
  });

  // --- Exec tree: capture task descriptions ---
  on('exec:tree', ({ data }) => {
    if (!data || !data.batches) return;
    for (const batch of data.batches) {
      for (const task of batch.tasks) {
        taskDescriptions[task.id] = task.description;
      }
    }
  });

  // --- Chunk streaming (+ activity tracking) ---
  on('log:chunk', ({ stage, data }) => {
    markActivity();
    const callId = data.call_id;
    const taskId = data.task_id || null;

    if (data.label && callId) {
      const level = data.level || 4;

      // Determine parent container for this level
      let parent;
      if (level <= 2) {
        if (!currentSection) return;
        parent = currentSection;
      } else {
        parent = currentTarget(taskId);
        if (!parent) return;
      }

      // Auto-collapse the last fold at the same level within this parent
      collapsePrevFold(parent);

      // Build label text (task labels get description)
      let text = data.text;
      if (level === 3 && taskId) {
        const desc = taskDescriptions[taskId];
        text = desc ? `Task [${taskId}]: ${desc}` : `Task [${taskId}]`;
      }

      // Create fold
      const fold = createFold(parent, text, level);

      // Track by level
      if (level <= 2) {
        currentPhaseName = callId;
        phaseGroups[callId] = fold;
      }
      if (level === 3 && taskId) {
        taskGroups[taskId] = fold;
      }

      // Register text block inside fold body
      const block = document.createElement('div');
      block.className = 'fold-text';
      fold.body.appendChild(block);
      callBlocks[callId] = block;
      callScrollers[callId] = createAutoScroller(block);
      scroller.scroll();
      return;
    }

    // Non-label chunk: append text to existing block
    const chunkText = data.text || data;
    let block;

    if (callId && callBlocks[callId]) {
      block = callBlocks[callId];
      // If something was inserted after this block (e.g. a tool fold),
      // create a new block at the end so text appears in chronological order.
      const parent = block.parentElement;
      if (parent && parent.lastElementChild !== block) {
        collapsePrevFold(parent);
        block = document.createElement('div');
        block.className = 'fold-text';
        parent.appendChild(block);
        callBlocks[callId] = block;
        callScrollers[callId] = createAutoScroller(block);
      }
      block.appendChild(document.createTextNode(chunkText));
    } else {
      const target = currentTarget(taskId) || logOutput;
      block = target.lastElementChild;
      if (!block || !block.classList.contains('fold-text')) {
        block = document.createElement('div');
        block.className = 'fold-text';
        target.appendChild(block);
      }
      block.appendChild(document.createTextNode(chunkText));
    }

    if (callId && callScrollers[callId]) callScrollers[callId].scroll();
    else if (block) block.scrollTop = block.scrollHeight;
    scroller.scroll();
  });

  on('log:tokens', ({ data }) => {
    markActivity();
    totalTokens += data.total || 0;
    updateTokenBadge();
  });

  on('stage:error', ({ stage, data }) => {
    const msg = data.message || data;
    const el = document.createElement('div');
    el.className = 'fold-text';
    el.style.color = 'var(--red)';
    el.textContent = `[ERROR] ${stage}: ${msg}`;
    (currentTarget(null) || logOutput).appendChild(el);
    scroller.scroll();
  });
}

// --- Fold helpers ---

function collapsePrevFold(parent) {
  // Find the last fold-body in this parent and collapse it (unless user expanded).
  const bodies = parent.querySelectorAll(':scope > .fold-body');
  if (bodies.length === 0) return;
  const last = bodies[bodies.length - 1];
  if (last.classList.contains('user-expanded')) return;
  last.classList.add('collapsed');
  const label = last.previousElementSibling;
  if (label && label.classList.contains('fold-label')) {
    label.classList.add('is-collapsed');
  }
}

function resetPhaseState() {
  callBlocks = {};
  callScrollers = {};
  phaseGroups = {};
  currentPhaseName = null;
  taskGroups = {};
}

function resetState() {
  activeStage = null;
  currentSection = null;
  resetPhaseState();
  taskDescriptions = {};
  totalTokens = 0;
  updateTokenBadge();
}

// --- Timer ---

// --- Activity indicator ---

function markActivity() {
  lastActivityTime = Date.now();
  if (!activityInterval) {
    activityInterval = setInterval(updateActivityBadge, 1000);
  }
  updateActivityBadge();
}

function stopActivity() {
  if (activityInterval) clearInterval(activityInterval);
  activityInterval = null;
  lastActivityTime = null;
  if (activityBadge) {
    activityBadge.classList.add('hidden');
    activityBadge.textContent = '';
  }
}

function updateActivityBadge() {
  if (!activityBadge || !lastActivityTime) return;
  activityBadge.classList.remove('hidden');
  const idle = Math.floor((Date.now() - lastActivityTime) / 1000);
  if (idle < 5) {
    activityBadge.textContent = 'Active';
    activityBadge.dataset.state = 'active';
  } else if (idle < 60) {
    activityBadge.textContent = `Waiting ${idle}s`;
    activityBadge.dataset.state = 'waiting';
  } else {
    const m = Math.floor(idle / 60);
    const s = idle % 60;
    activityBadge.textContent = `No output ${m}m${s}s`;
    activityBadge.dataset.state = 'stale';
  }
}

// --- Elapsed timer ---

function startTimer() {
  timerStart = Date.now();
  updateTimerBadge();
  timerInterval = setInterval(updateTimerBadge, 1000);
}

function stopTimer() {
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = null;
  timerStart = null;
  if (timerBadge) timerBadge.textContent = '';
}

function updateTimerBadge() {
  if (!timerBadge || !timerStart) return;
  const elapsed = Math.floor((Date.now() - timerStart) / 1000);
  const m = Math.floor(elapsed / 60);
  const s = elapsed % 60;
  timerBadge.textContent = m > 0 ? `${m}m ${s}s` : `${s}s`;
}

// --- Utilities ---

function wireCopyButton(btnId, sourceEl) {
  const btn = document.getElementById(btnId);
  if (!btn || !sourceEl) return;
  btn.addEventListener('click', () => {
    const text = sourceEl.innerText;
    try {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.cssText = 'position:fixed;opacity:0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      btn.textContent = 'Copied!';
    } catch {
      navigator.clipboard.writeText(text).then(() => {
        btn.textContent = 'Copied!';
      }).catch(() => {
        btn.textContent = 'Failed';
      });
    }
    setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
  });
}

function updateTokenBadge() {
  if (!tokenBadge) return;
  if (totalTokens === 0) {
    tokenBadge.textContent = '';
    return;
  }
  let display;
  if (totalTokens >= 1e9)      display = `${(totalTokens / 1e9).toFixed(1)}B tokens`;
  else if (totalTokens >= 1e6) display = `${(totalTokens / 1e6).toFixed(1)}M tokens`;
  else if (totalTokens >= 1e3) display = `${(totalTokens / 1e3).toFixed(1)}k tokens`;
  else                         display = `${totalTokens} tokens`;
  tokenBadge.textContent = display;
}
