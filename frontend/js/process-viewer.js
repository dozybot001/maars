/**
 * Process & Output panel (right side).
 * Renders structured data: document cards, decomposition tree,
 * execution graph with clickable tasks, and score indicators.
 *
 * Uses the same fold system as the left panel:
 *   Stage section (── RESEARCH ──)       ← level 1
 *     ▾ Phase (Calibrate / Execute ...)  ← level 2 (fold-label + fold-body)
 *       [structured content]
 */
import { on } from './events.js';
import { createAutoScroller } from './autoscroll.js';
import { STAGE_LABELS, createFold, appendSeparator } from './shared.js';
import { showModal } from './modal.js';

const PHASE_LABELS = {
  calibrate: 'Calibrate',
  strategy: 'Strategy',
  decompose: 'Decompose',
  execute: 'Execute',
  evaluate: 'Evaluate',
};

let processBody;
let scroller;
let activeStage = null;
let currentSection = null;

// Phase groups — { label, body }
let phaseGroups = {};
let currentPhaseName = null;

// Caches for modal content
const documentCache = {};
const taskSummaryCache = {};

/** Current write target: phase body or section. */
function target() {
  if (currentPhaseName && phaseGroups[currentPhaseName]) return phaseGroups[currentPhaseName].body;
  return currentSection;
}

export function initProcessViewer() {
  processBody = document.getElementById('process-body');
  scroller = createAutoScroller(processBody);

  // --- Stage lifecycle (level 1) ---
  on('stage:state', ({ stage, data }) => {
    if (data === 'idle') {
      processBody.innerHTML = '';
      activeStage = null;
      currentSection = null;
      phaseGroups = {};
      currentPhaseName = null;
      scroller.reset();
    } else if (data === 'running' && stage !== activeStage) {
      if (currentSection) {
        currentSection.classList.add('collapsed');
        const prevSep = currentSection.previousElementSibling;
        if (prevSep) prevSep.classList.add('is-collapsed');
      }
      activeStage = stage;
      phaseGroups = {};
      currentPhaseName = null;
      currentSection = appendSeparator(processBody, STAGE_LABELS[stage] || stage.toUpperCase(), scroller);
    }
  });

  // --- Phase transitions (level 2) ---
  on('stage:phase', ({ data }) => {
    if (!currentSection) return;
    // Collapse previous phase
    if (currentPhaseName && phaseGroups[currentPhaseName]) {
      const g = phaseGroups[currentPhaseName];
      if (g.body && !g.body.classList.contains('user-expanded')) {
        g.body.classList.add('collapsed');
        g.label.classList.add('is-collapsed');
      }
    }
    const label = PHASE_LABELS[data] || data;
    currentPhaseName = label;
    phaseGroups[label] = createFold(currentSection, label);
    scroller.scroll();
  });

  // --- Document cards ---
  on('doc:ready', ({ data }) => {
    if (!data || !data.name || !target()) return;
    documentCache[data.name] = data.content || '';
    appendDocCard(data.name, data.label || data.name);
  });

  // --- Score indicator ---
  on('score:update', ({ data }) => {
    if (!data || !target()) return;
    appendScoreElement(data);
  });

  // --- Plan: decomposition tree ---
  on('plan:tree', ({ data }) => {
    if (!data || !data.id || !target()) return;
    const t = target();
    let container = t.querySelector('#tree-output');
    if (!container) {
      container = document.createElement('ul');
      container.id = 'tree-output';
      container.className = 'po-tree';
      t.appendChild(container);
    }
    container.innerHTML = '';
    container.appendChild(renderDecompNode(data, true));
    scroller.scroll();
  });

  // --- Execute: task batch list ---
  on('exec:tree', ({ data }) => {
    if (!data || !data.batches || !target()) return;
    const t = target();
    let container = t.querySelector('#exec-output');
    if (!container) {
      container = document.createElement('div');
      container.id = 'exec-output';
      container.className = 'po-exec';
      t.appendChild(container);
    }

    const existingNodes = {};
    container.querySelectorAll('.exec-node').forEach(node => {
      existingNodes[node.dataset.taskId] = node;
    });

    const fragment = document.createDocumentFragment();
    for (const batch of data.batches) {
      const batchDiv = document.createElement('div');
      batchDiv.className = 'exec-batch';

      const label = document.createElement('div');
      label.className = 'exec-batch-label';
      label.textContent = `Batch ${batch.batch}`;
      batchDiv.appendChild(label);

      for (const task of batch.tasks) {
        const existing = existingNodes[task.id];
        if (existing) {
          batchDiv.appendChild(existing);
          delete existingNodes[task.id];
        } else {
          const node = document.createElement('div');
          node.className = 'exec-node exec-pending';
          node.dataset.taskId = task.id;

          const id = document.createElement('span');
          id.className = 'tree-id';
          id.textContent = task.id;

          const desc = document.createElement('span');
          desc.className = 'exec-desc';
          desc.textContent = task.description;

          node.appendChild(id);
          node.appendChild(desc);
          batchDiv.appendChild(node);
        }
      }
      fragment.appendChild(batchDiv);
    }
    container.innerHTML = '';
    container.appendChild(fragment);
    scroller.scroll();
  });

  // --- Task status updates ---
  on('task:state', ({ data }) => {
    const { task_id, status, summary } = data;
    const node = processBody.querySelector(`.exec-node[data-task-id="${task_id}"]`);
    if (!node) return;
    node.classList.remove(
      'exec-pending', 'exec-running', 'exec-verifying',
      'exec-retrying', 'exec-decomposing', 'exec-completed', 'exec-failed',
    );
    node.classList.add(`exec-${status}`);

    if (status === 'completed' && summary) {
      taskSummaryCache[task_id] = summary;
      node.style.cursor = 'pointer';
      node.addEventListener('click', () => {
        showModal(`Task ${task_id}`, taskSummaryCache[task_id]);
      }, { once: false });
    }

    const batch = node.closest('.exec-batch');
    if (batch && scroller.isLocked()) {
      batch.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  });
}

// --- Helpers ---

function appendDocCard(name, label) {
  const t = target();
  if (!t) return;
  const item = document.createElement('div');
  item.className = 'po-file-item';

  const icon = document.createTextNode('\uD83D\uDCC4 ');
  const span = document.createElement('span');
  span.textContent = label;

  item.appendChild(icon);
  item.appendChild(span);
  item.addEventListener('click', () => showModal(label, documentCache[name] || ''));

  t.appendChild(item);
  scroller.scroll();
}

function appendScoreElement(data) {
  const t = target();
  if (!t) return;
  const el = document.createElement('div');
  el.className = 'po-score';

  const current = data.current != null ? data.current.toFixed(5) : '\u2014';
  const prev = data.previous != null ? data.previous.toFixed(5) : 'N/A';
  const improved = data.improved;

  el.classList.add(improved ? 'po-score-improved' : 'po-score-declined');
  el.innerHTML =
    `<span class="po-score-label">Score</span>` +
    `<span class="po-score-current">${current}</span>` +
    `<span class="po-score-arrow">${improved ? '\u2191' : '\u2192'}</span>` +
    `<span class="po-score-prev">${prev}</span>`;

  t.appendChild(el);
  scroller.scroll();
}

// --- Decomposition tree renderer ---

function renderDecompNode(node, isRoot) {
  const li = document.createElement('li');
  const span = document.createElement('span');
  span.className = 'tree-node';

  if (isRoot) {
    span.classList.add('tree-root');
    span.textContent = 'Idea';
  } else {
    if (node.is_atomic === true) span.classList.add('tree-atomic');
    else if (node.is_atomic === false) span.classList.add('tree-decomposed');
    else span.classList.add('tree-pending');

    const id = document.createElement('span');
    id.className = 'tree-id';
    id.textContent = node.id;

    const desc = document.createElement('span');
    desc.className = 'tree-desc';
    desc.textContent = node.description;

    span.appendChild(id);
    span.appendChild(desc);

    if (node.dependencies && node.dependencies.length > 0) {
      const deps = document.createElement('span');
      deps.className = 'tree-deps';
      deps.textContent = `\u2192 ${node.dependencies.join(', ')}`;
      span.appendChild(deps);
    }
  }

  li.appendChild(span);

  if (node.children && node.children.length > 0) {
    const ul = document.createElement('ul');
    for (const child of node.children) {
      if (child) ul.appendChild(renderDecompNode(child, false));
    }
    li.appendChild(ul);
  }

  return li;
}
