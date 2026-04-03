/**
 * Process & Output panel (right side) — state dashboard.
 *
 * Fixed layout with incremental updates:
 *   - Document cards row (calibration, strategy, evaluation — refresh, not duplicate)
 *   - Score display (updates in place)
 *   - Decomposition tree (single instance, re-rendered on each done signal)
 *   - Execution list (single instance, re-rendered on each done signal)
 */
import { on } from './events.js';
import { fetchPlanTree, fetchPlanList, fetchDocument, fetchMeta, fetchTaskOutput } from './api.js';
import { createAutoScroller } from './autoscroll.js';
import { showModal } from './modal.js';

const PHASE_DOCS = { calibrate: 'calibration', strategy: 'strategy', evaluate: 'evaluation' };

let processBody, scroller;
const documentCache = {};
const pendingStatuses = {};  // Buffer for status events that arrive before DOM nodes exist

// Fixed DOM containers (created once)
let docsRow, treeContainer, execContainer, scoreContainer;

export function initProcessViewer() {
  processBody = document.getElementById('process-body');
  scroller = createAutoScroller(processBody);
  const tokenBadge = document.getElementById('token-estimate');

  // Build fixed layout sections
  docsRow = el('div', 'po-docs-row');
  scoreContainer = el('div', 'po-score-container');
  treeContainer = el('ul', 'po-tree');
  treeContainer.id = 'tree-output';
  execContainer = el('div', 'po-exec');
  execContainer.id = 'exec-output';

  processBody.appendChild(section('Documents', docsRow));
  processBody.appendChild(section('Score', scoreContainer));
  processBody.appendChild(section('Decompose', treeContainer));
  processBody.appendChild(section('Tasks', execContainer));

  on('sse', async (event) => {
    const { stage, phase, chunk, status, task_id } = event;
    if (!stage) return;

    // Task status updates (running/verifying/retrying/etc.)
    if (status && task_id) { updateTaskStatus(task_id, status); return; }

    if (chunk) return;

    // Done signals → fetch DB and update fixed containers
    await handleDoneSignal(stage, phase, task_id);

    // Token counter
    const meta = await fetchMeta();
    if (meta && tokenBadge) {
      const total = meta.tokens_total || 0;
      if (total > 0) {
        if (total >= 1e6) tokenBadge.textContent = `${(total / 1e6).toFixed(1)}M tokens`;
        else if (total >= 1e3) tokenBadge.textContent = `${(total / 1e3).toFixed(1)}k tokens`;
        else tokenBadge.textContent = `${total} tokens`;
      }
    }
  });
}

// ------------------------------------------------------------------
// Done signal handler
// ------------------------------------------------------------------

async function handleDoneSignal(stage, phase, taskId) {
  // Task completion → make clickable to show full output
  if (taskId) {
    const node = processBody.querySelector(`.exec-node[data-task-id="${taskId}"]`);
    if (node) {
      updateTaskStatus(taskId, 'completed');
      node.style.cursor = 'pointer';
      node.onclick = async () => {
        const data = await fetchTaskOutput(taskId);
        showModal(`Task ${taskId}`, data ? data.content : '(no output)');
      };
    }
    return;
  }

  // Document cards (calibration, strategy, evaluation)
  if (phase && PHASE_DOCS[phase]) {
    const docName = PHASE_DOCS[phase];
    const doc = await fetchDocument(docName);
    if (doc && doc.content) {
      documentCache[docName] = doc.content;
      ensureDocCard(docName);
    }
  }

  // Decomposition tree
  if (phase === 'decompose' || !phase) {
    const tree = await fetchPlanTree();
    if (tree && tree.id) renderTree(tree);
  }

  // Execution list
  if (phase === 'execute') {
    const tasks = await fetchPlanList();
    if (tasks && tasks.length > 0) renderExecList(tasks);
  }

  // Score
  if (phase === 'evaluate') {
    const meta = await fetchMeta();
    if (meta && meta.current_score != null) renderScore(meta);
  }

  // Refine / Write stage docs
  if (!phase) {
    if (stage === 'refine') {
      const doc = await fetchDocument('refined_idea');
      if (doc && doc.content) {
        documentCache['refined_idea'] = doc.content;
        ensureDocCard('refined_idea');
      }
    } else if (stage === 'write') {
      const doc = await fetchDocument('paper');
      if (doc && doc.content) {
        documentCache['paper'] = doc.content;
        ensureDocCard('paper');
      }
    }
  }
}

// ------------------------------------------------------------------
// Document cards (horizontal row, refresh in place)
// ------------------------------------------------------------------

function ensureDocCard(name) {
  let card = docsRow.querySelector(`[data-doc-name="${name}"]`);
  if (card) {
    // Refresh click handler with latest content
    card.onclick = () => showModal(name, documentCache[name] || '');
    return;
  }
  card = el('div', 'po-file-item');
  card.dataset.docName = name;
  card.textContent = '\uD83D\uDCC4 ' + name;
  card.onclick = () => showModal(name, documentCache[name] || '');
  docsRow.appendChild(card);
}

// ------------------------------------------------------------------
// Score (single element, updated in place)
// ------------------------------------------------------------------

function renderScore(meta) {
  scoreContainer.innerHTML = '';
  const score = el('div', 'po-score');
  const current = meta.current_score != null ? meta.current_score.toFixed(5) : '\u2014';
  const prev = meta.previous_score != null ? meta.previous_score.toFixed(5) : 'N/A';
  const improved = meta.improved;
  score.classList.add(improved ? 'po-score-improved' : 'po-score-declined');
  score.innerHTML =
    `<span class="po-score-label">Score</span>` +
    `<span class="po-score-current">${current}</span>` +
    `<span class="po-score-arrow">${improved ? '\u2191' : '\u2192'}</span>` +
    `<span class="po-score-prev">${prev}</span>`;
  scoreContainer.appendChild(score);
}

// ------------------------------------------------------------------
// Task status
// ------------------------------------------------------------------

function updateTaskStatus(taskId, status) {
  const node = processBody.querySelector(`.exec-node[data-task-id="${taskId}"]`);
  if (!node) {
    // DOM not ready yet — buffer for renderExecList to apply later
    pendingStatuses[taskId] = status;
    return;
  }
  node.classList.remove('exec-pending', 'exec-running', 'exec-verifying',
    'exec-retrying', 'exec-decomposing', 'exec-completed', 'exec-failed');
  node.classList.add(`exec-${status}`);
}

// ------------------------------------------------------------------
// Decomposition tree (single instance, full re-render)
// ------------------------------------------------------------------

function renderTree(data) {
  treeContainer.innerHTML = '';
  treeContainer.appendChild(renderDecompNode(data, true));
  scroller.scroll();
}

function renderDecompNode(node, isRoot) {
  const li = document.createElement('li');
  const span = document.createElement('span');
  span.className = 'tree-node';
  if (isRoot) { span.classList.add('tree-root'); span.textContent = 'Idea'; }
  else {
    if (node.is_atomic === true) span.classList.add('tree-atomic');
    else if (node.is_atomic === false) span.classList.add('tree-decomposed');
    else span.classList.add('tree-pending');
    const id = document.createElement('span');
    id.className = 'tree-id'; id.textContent = node.id;
    const desc = document.createElement('span');
    desc.className = 'tree-desc'; desc.textContent = node.description;
    span.appendChild(id); span.appendChild(desc);
    if (node.dependencies && node.dependencies.length > 0) {
      const deps = document.createElement('span');
      deps.className = 'tree-deps'; deps.textContent = `\u2192 ${node.dependencies.join(', ')}`;
      span.appendChild(deps);
    }
  }
  li.appendChild(span);
  if (node.children && node.children.length > 0) {
    const ul = document.createElement('ul');
    for (const child of node.children) { if (child) ul.appendChild(renderDecompNode(child, false)); }
    li.appendChild(ul);
  }
  return li;
}

// ------------------------------------------------------------------
// Execution list (single instance, full re-render preserving status)
// ------------------------------------------------------------------

function renderExecList(tasks) {
  const batches = {};
  for (const task of tasks) {
    const b = task.batch || 1;
    if (!batches[b]) batches[b] = [];
    batches[b].push(task);
  }

  const existingNodes = {};
  execContainer.querySelectorAll('.exec-node').forEach(n => { existingNodes[n.dataset.taskId] = n; });

  const fragment = document.createDocumentFragment();
  for (const batchNum of Object.keys(batches).sort((a, b) => a - b)) {
    const batchDiv = el('div', 'exec-batch');
    const label = el('div', 'exec-batch-label', `Batch ${batchNum}`);
    batchDiv.appendChild(label);

    for (const task of batches[batchNum]) {
      const existing = existingNodes[task.id];
      if (existing) {
        updateTaskStatus(task.id, task.status || 'pending');
        batchDiv.appendChild(existing);
        delete existingNodes[task.id];
      } else {
        const node = el('div', `exec-node exec-${task.status || 'pending'}`);
        node.dataset.taskId = task.id;
        const id = el('span', 'tree-id', task.id);
        const desc = el('span', 'exec-desc', task.description);
        node.appendChild(id); node.appendChild(desc);
        if (task.status === 'completed') {
          node.style.cursor = 'pointer';
          node.onclick = async () => {
            const data = await fetchTaskOutput(task.id);
            showModal(`Task ${task.id}`, data ? data.content : '(no output)');
          };
        }
        batchDiv.appendChild(node);
      }
    }
    fragment.appendChild(batchDiv);
  }
  execContainer.innerHTML = '';
  execContainer.appendChild(fragment);

  // Apply buffered status events that arrived before DOM was ready
  for (const [tid, status] of Object.entries(pendingStatuses)) {
    updateTaskStatus(tid, status);
  }
  for (const key of Object.keys(pendingStatuses)) delete pendingStatuses[key];

  scroller.scroll();
}

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------

function section(label, content) {
  const wrapper = el('div', 'po-section');
  const header = el('div', 'po-section-label', label);
  wrapper.appendChild(header);
  wrapper.appendChild(content);
  return wrapper;
}

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text) e.textContent = text;
  return e;
}
