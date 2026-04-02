/**
 * Process & Output panel (right side) — state dashboard.
 *
 * Fixed layout with incremental updates:
 *   - Round indicator (updates in place)
 *   - Document cards row (calibration, strategy, evaluation — refresh, not duplicate)
 *   - Decomposition tree (single instance, re-rendered on each done signal)
 *   - Execution list (single instance, re-rendered on each done signal)
 *   - Score display (updates in place)
 */
import { on } from './events.js';
import { fetchPlanTree, fetchPlanList, fetchDocument, fetchMeta } from './api.js';
import { createAutoScroller } from './autoscroll.js';
import { showModal } from './modal.js';

const PHASE_DOCS = { calibrate: 'calibration', strategy: 'strategy', evaluate: 'evaluation' };

let processBody, scroller;
const documentCache = {}, taskSummaryCache = {};

// Fixed DOM containers (created once)
let roundBadge, docsRow, treeContainer, execContainer, scoreContainer;

export function initProcessViewer() {
  processBody = document.getElementById('process-body');
  scroller = createAutoScroller(processBody);
  const tokenBadge = document.getElementById('token-estimate');

  // Build fixed layout
  roundBadge = el('div', 'po-round-badge', '');
  docsRow = el('div', 'po-docs-row');
  treeContainer = el('ul', 'po-tree');
  treeContainer.id = 'tree-output';
  execContainer = el('div', 'po-exec');
  execContainer.id = 'exec-output';
  scoreContainer = el('div', 'po-score-container');

  processBody.appendChild(roundBadge);
  processBody.appendChild(docsRow);
  processBody.appendChild(scoreContainer);
  processBody.appendChild(treeContainer);
  processBody.appendChild(execContainer);

  on('sse', async (event) => {
    const { stage, phase, chunk, status, task_id } = event;
    if (!stage) return;

    // Task status updates (running/verifying/retrying/etc.)
    if (status && task_id) { updateTaskStatus(task_id, status); return; }

    // Label chunks → update round badge
    if (chunk) {
      if (chunk.label && chunk.level <= 2 && chunk.text) {
        updateRoundBadge(chunk.text);
      }
      return;
    }

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
// Round badge
// ------------------------------------------------------------------

function updateRoundBadge(text) {
  roundBadge.textContent = text;
  roundBadge.classList.add('po-round-active');
}

// ------------------------------------------------------------------
// Done signal handler
// ------------------------------------------------------------------

async function handleDoneSignal(stage, phase, taskId) {
  // Task completion → update exec node with summary
  if (taskId) {
    const tasks = await fetchPlanList();
    if (tasks) {
      const task = tasks.find(t => t.id === taskId);
      if (task && task.status === 'completed' && task.summary) {
        taskSummaryCache[taskId] = task.summary;
        const node = processBody.querySelector(`.exec-node[data-task-id="${taskId}"]`);
        if (node) {
          updateTaskStatus(taskId, 'completed');
          node.style.cursor = 'pointer';
          node.onclick = () => showModal(`Task ${taskId}`, taskSummaryCache[taskId]);
        }
      }
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
  if (!node) return;
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
        if (task.summary) {
          taskSummaryCache[task.id] = task.summary;
          node.style.cursor = 'pointer';
          node.onclick = () => showModal(`Task ${task.id}`, taskSummaryCache[task.id]);
        }
        batchDiv.appendChild(node);
      }
    }
    fragment.appendChild(batchDiv);
  }
  execContainer.innerHTML = '';
  execContainer.appendChild(fragment);
  scroller.scroll();
}

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text) e.textContent = text;
  return e;
}
