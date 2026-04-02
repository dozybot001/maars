/**
 * Process & Output panel (right side).
 * Done signals → fetch DB → render structured content.
 */
import { on } from './events.js';
import { fetchPlanTree, fetchPlanList, fetchDocument, fetchMeta } from './api.js';
import { createAutoScroller } from './autoscroll.js';
import { STAGE_LABELS, createFold, appendSeparator } from './shared.js';
import { showModal } from './modal.js';

const PHASE_DOCS = { calibrate: 'calibration', strategy: 'strategy', evaluate: 'evaluation' };

let processBody, scroller;
let activeStage = null, currentSection = null;
let phaseGroups = {}, currentPhaseName = null;
const documentCache = {}, taskSummaryCache = {};

function target() {
  if (currentPhaseName && phaseGroups[currentPhaseName]) return phaseGroups[currentPhaseName].body;
  return currentSection;
}

export function initProcessViewer() {
  processBody = document.getElementById('process-body');
  scroller = createAutoScroller(processBody);
  const tokenBadge = document.getElementById('token-estimate');

  on('sse', async (event) => {
    const { stage, phase, chunk, status, task_id } = event;
    if (!stage) return;

    ensureProcessSection(stage);

    if (status && task_id) { updateTaskStatus(task_id, status); return; }
    if (chunk) {
      // Level-2 label chunks create/update phase groups with the actual label text
      if (chunk.label && chunk.level <= 2 && chunk.text && phase) {
        ensurePhase(phase, chunk.text);
      }
      return;
    }
    // Done signals: select existing phase group (no label override)
    if (phase) ensurePhase(phase);

    const container = target();
    await handleDoneSignal(stage, phase, task_id, container);

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

function ensureProcessSection(stage) {
  if (activeStage === stage && currentSection) return;
  if (currentSection) {
    currentSection.classList.add('collapsed');
    const prevSep = currentSection.previousElementSibling;
    if (prevSep) prevSep.classList.add('is-collapsed');
  }
  activeStage = stage;
  phaseGroups = {}; currentPhaseName = null;
  currentSection = appendSeparator(processBody, STAGE_LABELS[stage] || stage.toUpperCase(), scroller);
}

function ensurePhase(phase, displayText) {
  if (phaseGroups[phase]) {
    // Update display text if a new label arrives (e.g. round change)
    if (displayText && phaseGroups[phase].label) {
      phaseGroups[phase].label.textContent = displayText;
    }
    currentPhaseName = phase;
    return;
  }
  currentPhaseName = phase;
  phaseGroups[phase] = createFold(currentSection, displayText || phase);
  scroller.scroll();
}

async function handleDoneSignal(stage, phase, taskId, container) {
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

  if (phase && PHASE_DOCS[phase]) {
    const doc = await fetchDocument(PHASE_DOCS[phase]);
    if (doc && doc.content) {
      documentCache[PHASE_DOCS[phase]] = doc.content;
      const group = phaseGroups[phase];
      const displayName = (group && group.label) ? group.label.textContent : phase;
      appendDocCard(PHASE_DOCS[phase], displayName, container);
    }
  }

  if (phase === 'decompose' || !phase) {
    const tree = await fetchPlanTree();
    if (tree && tree.id) renderTree(tree, container);
  }

  if (phase === 'execute') {
    const tasks = await fetchPlanList();
    if (tasks && tasks.length > 0) renderExecList(tasks, container);
  }

  if (phase === 'evaluate') {
    const meta = await fetchMeta();
    if (meta && meta.current_score != null) appendScoreElement(meta, container);
  }

  if (!phase) {
    if (stage === 'refine') {
      const doc = await fetchDocument('refined_idea');
      if (doc && doc.content) {
        documentCache['refined_idea'] = doc.content;
        appendDocCard('refined_idea', 'Refined Idea', container);
      }
    } else if (stage === 'write') {
      const doc = await fetchDocument('paper');
      if (doc && doc.content) {
        documentCache['paper'] = doc.content;
        appendDocCard('paper', 'Paper', container);
      }
    }
  }
}

function updateTaskStatus(taskId, status) {
  const node = processBody.querySelector(`.exec-node[data-task-id="${taskId}"]`);
  if (!node) return;
  node.classList.remove('exec-pending', 'exec-running', 'exec-verifying',
    'exec-retrying', 'exec-decomposing', 'exec-completed', 'exec-failed');
  node.classList.add(`exec-${status}`);
}

function renderTree(data, parent) {
  const t = parent || target();
  if (!t) return;
  let container = processBody.querySelector('#tree-output');
  if (!container) {
    container = document.createElement('ul');
    container.id = 'tree-output';
    container.className = 'po-tree';
    t.appendChild(container);
  }
  container.innerHTML = '';
  container.appendChild(renderDecompNode(data, true));
  scroller.scroll();
}

function renderExecList(tasks, parent) {
  const t = parent || target();
  if (!t) return;
  let container = processBody.querySelector('#exec-output');
  if (!container) {
    container = document.createElement('div');
    container.id = 'exec-output';
    container.className = 'po-exec';
    t.appendChild(container);
  }

  // Group tasks by batch number (from plan_list.json)
  const batches = {};
  for (const task of tasks) {
    const b = task.batch || 1;
    if (!batches[b]) batches[b] = [];
    batches[b].push(task);
  }

  const existingNodes = {};
  container.querySelectorAll('.exec-node').forEach(n => { existingNodes[n.dataset.taskId] = n; });

  const fragment = document.createDocumentFragment();
  for (const batchNum of Object.keys(batches).sort((a, b) => a - b)) {
    const batchDiv = document.createElement('div');
    batchDiv.className = 'exec-batch';
    const label = document.createElement('div');
    label.className = 'exec-batch-label';
    label.textContent = `Batch ${batchNum}`;
    batchDiv.appendChild(label);

    for (const task of batches[batchNum]) {
      const existing = existingNodes[task.id];
      if (existing) {
        updateTaskStatus(task.id, task.status || 'pending');
        batchDiv.appendChild(existing);
        delete existingNodes[task.id];
      } else {
        const node = document.createElement('div');
        node.className = `exec-node exec-${task.status || 'pending'}`;
        node.dataset.taskId = task.id;
        const id = document.createElement('span');
        id.className = 'tree-id'; id.textContent = task.id;
        const desc = document.createElement('span');
        desc.className = 'exec-desc'; desc.textContent = task.description;
        node.appendChild(id); node.appendChild(desc);
        batchDiv.appendChild(node);
      }
    }
    fragment.appendChild(batchDiv);
  }
  container.innerHTML = '';
  container.appendChild(fragment);
  scroller.scroll();
}

function appendDocCard(name, label, parent) {
  const t = parent || target();
  if (!t) return;
  if (t.querySelector(`[data-doc-name="${name}"]`)) return;
  const item = document.createElement('div');
  item.className = 'po-file-item'; item.dataset.docName = name;
  item.appendChild(document.createTextNode('\uD83D\uDCC4 '));
  const span = document.createElement('span');
  span.textContent = label; item.appendChild(span);
  item.addEventListener('click', () => showModal(label, documentCache[name] || ''));
  t.appendChild(item); scroller.scroll();
}

function appendScoreElement(meta, parent) {
  const t = parent || target();
  if (!t) return;
  const row = document.createElement('div'); row.className = 'po-eval-row';
  t.appendChild(row);
  const el = document.createElement('div'); el.className = 'po-score';
  const current = meta.current_score != null ? meta.current_score.toFixed(5) : '\u2014';
  const prev = meta.previous_score != null ? meta.previous_score.toFixed(5) : 'N/A';
  const improved = meta.improved;
  el.classList.add(improved ? 'po-score-improved' : 'po-score-declined');
  el.innerHTML = `<span class="po-score-label">Score</span><span class="po-score-current">${current}</span><span class="po-score-arrow">${improved ? '\u2191' : '\u2192'}</span><span class="po-score-prev">${prev}</span>`;
  row.appendChild(el); scroller.scroll();
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
