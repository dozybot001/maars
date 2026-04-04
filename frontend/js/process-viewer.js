/**
 * Process & Output panel (right side) — state dashboard.
 *
 * Layout by pipeline stage:
 *   - Refine: proposals, critiques, refined_idea
 *   - Research: documents (calibration/strategy/evaluation), score
 *   - Decompose: tree
 *   - Tasks: execution list
 *   - Write: paper
 */
import { on } from './events.js';
import { fetchPlanTree, fetchPlanList, fetchDocument, fetchMeta, fetchTaskOutput, listDocuments } from './api.js';
import { createAutoScroller } from './autoscroll.js';
import { showModal } from './modal.js';

let processBody, scroller;
const documentCache = {};
const pendingStatuses = {};

// Fixed DOM containers (created once per section)
let refineSection, refineProposals, refineCritiques, refineFinal;
let researchSection, researchCalibration, researchStrategies, researchEvaluations, scoreContainer;
let treeSection, treeContainer;
let taskSection, execContainer;
let writeSection, writeFinal;

export function initProcessViewer() {
  processBody = document.getElementById('process-body');
  scroller = createAutoScroller(processBody);
  const tokenBadge = document.getElementById('token-estimate');

  // Refine section
  refineProposals = el('div', 'po-docs-row');
  refineCritiques = el('div', 'po-docs-row');
  refineFinal = el('div', 'po-docs-row');
  refineSection = stageSection('Refine', [
    subRow('Proposals', refineProposals),
    subRow('Critiques', refineCritiques),
    subRow('Final', refineFinal),
  ]);

  // Research section
  researchCalibration = el('div', 'po-docs-row');
  researchStrategies = el('div', 'po-docs-row');
  researchEvaluations = el('div', 'po-docs-row');
  scoreContainer = el('div', 'po-score-container');
  researchSection = stageSection('Research', [
    subRow('Calibration', researchCalibration),
    subRow('Strategies', researchStrategies),
    subRow('Evaluations', researchEvaluations),
    subRow('Score', scoreContainer),
  ]);

  // Decompose section
  treeContainer = el('ul', 'po-tree');
  treeContainer.id = 'tree-output';
  treeSection = stageSection('Decompose', [treeContainer]);

  // Tasks section
  execContainer = el('div', 'po-exec');
  execContainer.id = 'exec-output';
  taskSection = stageSection('Tasks', [execContainer]);

  // Write section
  writeFinal = el('div', 'po-docs-row');
  writeSection = stageSection('Write', [
    subRow('Final', writeFinal),
  ]);

  for (const s of [refineSection, researchSection, treeSection, taskSection, writeSection]) {
    processBody.appendChild(s);
  }

  // DEBUG: test doc cards overflow
  for (let i = 1; i <= 8; i++) {
    refineProposals.appendChild(el('div', 'po-file-item', `\uD83D\uDCC4 proposals/round_${i}`));
    refineCritiques.appendChild(el('div', 'po-file-item', `\uD83D\uDCC4 critiques/round_${i}`));
  }
  researchCalibration.appendChild(el('div', 'po-file-item', '\uD83D\uDCC4 calibration'));
  for (let i = 1; i <= 4; i++) {
    researchStrategies.appendChild(el('div', 'po-file-item', `\uD83D\uDCC4 strategy/round_${i}`));
    researchEvaluations.appendChild(el('div', 'po-file-item', `\uD83D\uDCC4 evaluations/round_${i}`));
  }

  on('sse', async (event) => {
    const { stage, phase, chunk, status, task_id } = event;
    if (!stage) return;

    if (status && task_id) { updateTaskStatus(task_id, status); return; }
    if (chunk) return;

    await handleDoneSignal(stage, phase, task_id);

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
  // Task completion
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

  // --- Refine stage ---
  if (stage === 'refine') {


    if (phase === 'proposal') {
      await loadDocCards('proposals', refineProposals);
    } else if (phase === 'critique') {
      await loadDocCards('critiques', refineCritiques);
    } else if (!phase) {
      // Final done signal
      const doc = await fetchDocument('refined_idea');
      if (doc && doc.content) {
        documentCache['refined_idea'] = doc.content;
        ensureDocCard('refined_idea', refineFinal);
      }
    }
    return;
  }

  // --- Research stage ---
  if (stage === 'research') {
    if (phase === 'calibrate') {
      await loadDocCards('calibration', researchCalibration);
    } else if (phase === 'strategy') {
      await loadDocCards('strategy', researchStrategies);
    } else if (phase === 'evaluate') {
      await loadDocCards('evaluations', researchEvaluations);
      const meta = await fetchMeta();
      if (meta && meta.current_score != null) appendScore(meta);
    }

    if (phase === 'decompose' || !phase) {
      const tree = await fetchPlanTree();
      if (tree && tree.id) { renderTree(tree); }
    }

    if (phase === 'execute') {
      const tasks = await fetchPlanList();
      if (tasks && tasks.length > 0) { renderExecList(tasks); }
    }
    return;
  }

  // --- Write stage ---
  if (stage === 'write') {

    if (phase === 'proposal') {
      // Future: write proposals
    } else if (phase === 'critique') {
      // Future: write critiques
    } else if (!phase) {
      const doc = await fetchDocument('paper');
      if (doc && doc.content) {
        documentCache['paper'] = doc.content;
        ensureDocCard('paper', writeFinal);
      }
    }
    return;
  }
}

// ------------------------------------------------------------------
// Document cards
// ------------------------------------------------------------------

async function loadDocCards(prefix, container) {
  const versions = await listDocuments(prefix);
  if (versions.length > 0) {
    for (const docName of versions) {
      const doc = await fetchDocument(docName);
      if (doc && doc.content) {
        documentCache[docName] = doc.content;
        ensureDocCard(docName, container);
      }
    }
  } else {
    const doc = await fetchDocument(prefix);
    if (doc && doc.content) {
      documentCache[prefix] = doc.content;
      ensureDocCard(prefix, container);
    }
  }
}

function ensureDocCard(name, container) {
  let card = container.querySelector(`[data-doc-name="${name}"]`);
  if (card) {
    card.onclick = () => showModal(name, documentCache[name] || '');
    return;
  }
  card = el('div', 'po-file-item');
  card.dataset.docName = name;
  card.textContent = '\uD83D\uDCC4 ' + name;
  card.onclick = () => showModal(name, documentCache[name] || '');
  container.appendChild(card);
}

// ------------------------------------------------------------------
// Score
// ------------------------------------------------------------------

function appendScore(meta) {
  const score = el('div', 'po-score');
  const current = meta.current_score != null ? meta.current_score.toFixed(5) : '\u2014';
  const prev = meta.previous_score != null ? meta.previous_score.toFixed(5) : 'N/A';
  const improved = meta.improved;
  score.classList.add(improved ? 'po-score-improved' : 'po-score-declined');
  score.innerHTML =
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
    pendingStatuses[taskId] = status;
    return;
  }
  node.classList.remove('exec-pending', 'exec-running', 'exec-verifying',
    'exec-retrying', 'exec-decomposing', 'exec-completed', 'exec-failed');
  node.classList.add(`exec-${status}`);
}

// ------------------------------------------------------------------
// Decomposition tree
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
// Execution list
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

  for (const [tid, status] of Object.entries(pendingStatuses)) {
    updateTaskStatus(tid, status);
  }
  for (const key of Object.keys(pendingStatuses)) delete pendingStatuses[key];

  scroller.scroll();
}

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------

function stageSection(label, children) {
  const wrapper = el('div', 'po-stage-section');
  const header = el('div', 'po-stage-label', label);
  wrapper.appendChild(header);
  for (const child of children) wrapper.appendChild(child);
  return wrapper;
}

function subRow(label, content) {
  const wrapper = el('div', 'po-sub-row');
  const header = el('span', 'po-sub-label', label);
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
