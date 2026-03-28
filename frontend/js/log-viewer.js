import { on } from './events.js';
import { createAutoScroller } from './autoscroll.js';
import { STAGE_LABELS, appendSeparator } from './shared.js';

let logOutput;
let scroller;
let activeStage = null;
let callBlocks = {};      // call_id → DOM text element
let callScrollers = {};   // call_id → autoscroller for chunk block
let currentSection = null;
let totalTokens = 0;
let tokenBadge = null;

// Task grouping for Research stage
let taskGroups = {};      // task_id → DOM container element
let taskDescriptions = {}; // task_id → description (from exec_tree)
let taskBodyScrollers = {}; // task_id → autoscroller for task group body

export function initLogViewer() {
  logOutput = document.getElementById('log-output');
  scroller = createAutoScroller(logOutput);
  tokenBadge = document.getElementById('token-estimate');

  document.getElementById('copy-log').addEventListener('click', () => {
    const text = logOutput.innerText;
    const btn = document.getElementById('copy-log');
    try {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      btn.textContent = 'Copied!';
    } catch (e) {
      navigator.clipboard.writeText(text).then(() => {
        btn.textContent = 'Copied!';
      }).catch(() => {
        btn.textContent = 'Failed';
      });
    }
    setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
  });

  // --- Stage transitions ---
  on('stage:state', ({ stage, data }) => {
    if (data === 'idle') {
      logOutput.innerHTML = '';
      activeStage = null;
      callBlocks = {};
      callScrollers = {};
      currentSection = null;
      taskGroups = {};
      taskDescriptions = {};
      totalTokens = 0;
      updateTokenBadge();
      scroller.reset();
    } else if (data === 'running' && stage !== activeStage) {
      // Collapse previous section (respect user-expanded)
      if (currentSection && !currentSection.classList.contains('user-expanded')) {
        currentSection.classList.add('collapsed');
        const prevSep = currentSection.previousElementSibling;
        if (prevSep) prevSep.classList.add('is-collapsed');
      }
      activeStage = stage;
      callBlocks = {};
      callScrollers = {};
      taskGroups = {};
      taskBodyScrollers = {};
      currentSection = appendSeparator(logOutput, STAGE_LABELS[stage] || stage.toUpperCase(), scroller);
    }
  });

  // --- Task state: auto-collapse completed tasks ---
  on('task:state', ({ data }) => {
    const { task_id, status } = data;
    if ((status === 'completed' || status === 'failed') && taskGroups[task_id]) {
      const group = taskGroups[task_id];
      const body = group.querySelector('.task-group-body');
      const header = group.querySelector('.task-group-header');
      if (body && !body.classList.contains('user-expanded')) {
        body.classList.add('collapsed');
        if (header) header.classList.add('is-collapsed');
      }
    }
  });

  // --- Exec tree: capture task descriptions for group headers ---
  on('exec:tree', ({ data }) => {
    if (!data || !data.batches) return;
    for (const batch of data.batches) {
      for (const task of batch.tasks) {
        taskDescriptions[task.id] = task.description;
      }
    }
  });

  // --- Chunk streaming ---
  on('log:chunk', ({ stage, data }) => {
    const callId = data.call_id;
    const taskId = data.task_id || null;

    // Determine target container: task group or section
    const target = taskId ? getOrCreateTaskGroup(taskId) : currentSection;

    if (data.label && callId) {
      // Inside task groups: fold ALL previous blocks (keep everything collapsed)
      // Outside task groups: fold previous blocks as before
      if (target) {
        target.querySelectorAll('.log-text:not(.folded):not(.user-expanded)').forEach(el => {
          el.classList.add('folded');
          const prev = el.previousElementSibling;
          if (prev && prev.classList.contains('log-label')) prev.classList.add('is-collapsed');
        });
      }

      const label = document.createElement('div');
      label.className = 'log-label';
      label.textContent = data.text;

      // For task groups, use the inner body container
      const appendTarget = taskId ? getTaskGroupBody(taskId) : target;
      if (appendTarget) appendTarget.appendChild(label);

      const block = document.createElement('div');
      block.className = 'log-text';
      if (appendTarget) appendTarget.appendChild(block);

      label.addEventListener('click', () => {
        const nowFolded = block.classList.toggle('folded');
        label.classList.toggle('is-collapsed');
        if (nowFolded) {
          block.classList.remove('user-expanded');
        } else {
          block.classList.add('user-expanded');
        }
      });

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
      block.appendChild(document.createTextNode(chunkText));
    } else {
      // Fallback: append to last block in target
      const fallback = taskId ? getTaskGroupBody(taskId) : (currentSection || logOutput);
      block = fallback ? fallback.lastElementChild : null;
      if (!block || !block.classList.contains('log-text')) {
        block = document.createElement('div');
        block.className = 'log-text';
        if (fallback) fallback.appendChild(block);
      }
      block.appendChild(document.createTextNode(chunkText));
    }
    if (callId && callScrollers[callId]) {
      callScrollers[callId].scroll();
    } else if (block) {
      block.scrollTop = block.scrollHeight;
    }
    // Scroll task body container if within a task group
    if (taskId && taskBodyScrollers[taskId]) {
      taskBodyScrollers[taskId].scroll();
    }
    scroller.scroll();
  });

  on('log:tokens', ({ data }) => {
    totalTokens += data.total || 0;
    updateTokenBadge();
  });

  on('stage:error', ({ stage, data }) => {
    const msg = data.message || data;
    const el = document.createElement('div');
    el.className = 'log-text';
    el.style.color = 'var(--red)';
    el.textContent = `[ERROR] ${stage}: ${msg}`;
    (currentSection || logOutput).appendChild(el);
    scroller.scroll();
  });
}

// --- Task group helpers ---

function getOrCreateTaskGroup(taskId) {
  if (taskGroups[taskId]) return taskGroups[taskId];
  if (!currentSection) return null;

  // Fold any open top-level blocks in the section (e.g., Replan, Calibrate)
  currentSection.querySelectorAll(':scope > .log-text:not(.folded):not(.user-expanded)').forEach(el => {
    el.classList.add('folded');
    const prev = el.previousElementSibling;
    if (prev && prev.classList.contains('log-label')) prev.classList.add('is-collapsed');
  });

  const group = document.createElement('div');
  group.className = 'task-group';
  group.dataset.taskId = taskId;

  const header = document.createElement('div');
  header.className = 'task-group-header';
  const desc = taskDescriptions[taskId];
  header.textContent = desc ? `Task [${taskId}]: ${desc}` : `Task [${taskId}]`;

  const body = document.createElement('div');
  body.className = 'task-group-body';

  // Auto-scroller for the task body (same logic as global panels)
  taskBodyScrollers[taskId] = createAutoScroller(body);

  // Click header to collapse/expand body
  header.addEventListener('click', () => {
    const nowCollapsed = body.classList.toggle('collapsed');
    header.classList.toggle('is-collapsed');
    if (nowCollapsed) {
      body.classList.remove('user-expanded');
    } else {
      body.classList.add('user-expanded');
    }
  });

  group.appendChild(header);
  group.appendChild(body);
  currentSection.appendChild(group);

  taskGroups[taskId] = group;
  scroller.scroll();
  return group;
}

function getTaskGroupBody(taskId) {
  const group = taskGroups[taskId];
  if (!group) return currentSection;
  return group.querySelector('.task-group-body') || currentSection;
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
