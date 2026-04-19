import { on } from './events.js';
import { createAutoScroller } from './autoscroll.js';
import { createFold, appendSeparator } from './shared.js';

let logOutput, scroller;
let activeStage = null, currentSection = null;
let phaseGroups = {}, currentPhaseName = null;
let taskGroups = {}, taskDescriptions = {};
let callBlocks = {}, callScrollers = {};
let timerBadge = null, timerInterval = null, timerStart = null;
let activityBadge = null, lastActivityTime = null, activityInterval = null;
let pausedAt = null;

function currentTarget(taskId) {
  if (taskId && taskGroups[taskId]) return taskGroups[taskId].body;
  if (currentPhaseName && phaseGroups[currentPhaseName]) return phaseGroups[currentPhaseName].body;
  return currentSection;
}

export function initLogViewer() {
  logOutput = document.getElementById('log-output');
  scroller = createAutoScroller(logOutput);
  timerBadge = document.getElementById('elapsed-timer');
  activityBadge = document.getElementById('activity-indicator');

  on('sse', (event) => {
    const { stage, chunk, task_id, status, description } = event;
    if (!stage) return;
    ensureSection(stage);
    if (status && task_id && description) {
      taskDescriptions[task_id] = description;
    }
    if (chunk) {
      markActivity();
      renderChunk(chunk, task_id);
    }
  });
}

function ensureSection(stage) {
  if (activeStage === stage && currentSection) return;
  if (!timerStart) startTimer();
  if (currentSection && !currentSection.classList.contains('user-expanded')) {
    currentSection.classList.add('collapsed');
    const prevSep = currentSection.previousElementSibling;
    if (prevSep) prevSep.classList.add('is-collapsed');
  }
  activeStage = stage;
  resetPhaseState();
  currentSection = appendSeparator(logOutput, stage.toUpperCase(), scroller);
}

function renderChunk(data, taskId) {
  const callId = data.call_id;
  if (data.label && callId) {
    const level = data.level || 4;
    let parent;
    if (level <= 2) {
      if (!currentSection) return;
      parent = currentSection;
    } else {
      parent = currentTarget(taskId);
      if (!parent) return;
    }
    collapsePrevFold(parent);
    let text = data.text;
    if (level === 3 && taskId) {
      const desc = taskDescriptions[taskId];
      text = desc ? `Task [${taskId}]: ${desc}` : `Task [${taskId}]`;
    }
    const fold = createFold(parent, text, level);
    if (level <= 2) {
      currentPhaseName = callId;
      phaseGroups[callId] = fold;
    }
    if (level === 3 && taskId) {
      taskGroups[taskId] = fold;
    }
    const block = document.createElement('div');
    block.className = 'fold-text';
    fold.body.appendChild(block);
    callBlocks[callId] = block;
    callScrollers[callId] = createAutoScroller(block);
    scroller.scroll();
    return;
  }
  const chunkText = data.text || '';
  let block;
  if (callId && callBlocks[callId]) {
    block = callBlocks[callId];
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
}

function collapsePrevFold(parent) {
  const bodies = parent.querySelectorAll(':scope > .fold-body');
  if (bodies.length === 0) return;
  const last = bodies[bodies.length - 1];
  if (last.classList.contains('user-expanded')) return;
  last.classList.add('collapsed');
  const label = last.previousElementSibling;
  if (label && label.classList.contains('fold-label')) label.classList.add('is-collapsed');
}

function resetPhaseState() {
  callBlocks = {}; callScrollers = {};
  phaseGroups = {}; currentPhaseName = null;
  taskGroups = {};
}

function markActivity() {
  lastActivityTime = Date.now();
  if (!activityInterval) activityInterval = setInterval(updateActivityBadge, 1000);
  updateActivityBadge();
}

function startTimer() {
  timerStart = Date.now();
  updateTimerBadge();
  timerInterval = setInterval(updateTimerBadge, 1000);
}

function updateTimerBadge() {
  if (!timerBadge || !timerStart) return;
  const elapsed = Math.floor((Date.now() - timerStart) / 1000);
  const m = Math.floor(elapsed / 60), s = elapsed % 60;
  timerBadge.textContent = m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function updateActivityBadge() {
  if (!activityBadge || !lastActivityTime) return;
  const idle = Math.floor((Date.now() - lastActivityTime) / 1000);
  if (idle < 5) { activityBadge.textContent = 'Active'; activityBadge.dataset.state = 'active'; }
  else if (idle < 60) { activityBadge.textContent = `Waiting ${idle}s`; activityBadge.dataset.state = 'waiting'; }
  else { const m = Math.floor(idle / 60), s = idle % 60; activityBadge.textContent = `No output ${m}m${s}s`; activityBadge.dataset.state = 'stale'; }
}

export function pauseTimers() {
  pausedAt = Date.now();
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
  if (activityInterval) { clearInterval(activityInterval); activityInterval = null; }
  if (activityBadge) { activityBadge.textContent = 'Paused'; activityBadge.dataset.state = 'paused'; }
}

export function stopTimers() {
  const wasRunning = !!timerInterval;
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
  if (activityInterval) { clearInterval(activityInterval); activityInterval = null; }
  if (wasRunning && activityBadge) { activityBadge.textContent = 'Done'; activityBadge.dataset.state = 'done'; }
}

export function resumeTimers() {
  if (pausedAt) {
    const paused = Date.now() - pausedAt;
    if (timerStart) timerStart += paused;
    if (lastActivityTime) lastActivityTime += paused;
    pausedAt = null;
  }
  if (timerStart && !timerInterval) {
    timerInterval = setInterval(updateTimerBadge, 1000);
    updateTimerBadge();
  }
  if (lastActivityTime && !activityInterval) {
    activityInterval = setInterval(updateActivityBadge, 1000);
    updateActivityBadge();
  }
}
