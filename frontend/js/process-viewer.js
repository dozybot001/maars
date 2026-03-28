/**
 * Process & Output panel (right side).
 * Mirrors the left panel's structure: separator → collapsible section.
 */
import { on } from './events.js';
import { createAutoScroller } from './autoscroll.js';
import { STAGE_LABELS, appendSeparator } from './shared.js';

let processBody;
let scroller;
let activeStage = null;
let currentSection = null;

export function initProcessViewer() {
  processBody = document.getElementById('process-body');
  scroller = createAutoScroller(processBody);

  on('stage:state', ({ stage, data }) => {
    if (data === 'idle') {
      processBody.innerHTML = '';
      activeStage = null;
      currentSection = null;
      scroller.reset();
    } else if (data === 'running' && stage !== activeStage) {
      // Collapse previous section
      if (currentSection) {
        currentSection.classList.add('collapsed');
        const prevSep = currentSection.previousElementSibling;
        if (prevSep) prevSep.classList.add('is-collapsed');
      }
      activeStage = stage;
      currentSection = appendSeparator(processBody, STAGE_LABELS[stage] || stage.toUpperCase(), scroller);
    } else if (data === 'completed' && (stage === 'refine' || stage === 'write' || stage === 'research')) {
      appendFileItem(stage);
    }
  });

  // --- Plan: decomposition tree ---
  on('plan:tree', ({ data }) => {
    if (!data || !data.id || !currentSection) return;
    let container = currentSection.querySelector('#tree-output');
    if (!container) {
      container = document.createElement('ul');
      container.id = 'tree-output';
      container.className = 'po-tree';
      currentSection.appendChild(container);
    }
    container.innerHTML = '';
    container.appendChild(renderDecompNode(data, true));
    scroller.scroll();
  });

  // --- Replan: append new branch to existing tree ---
  on('plan:replan', ({ data }) => {
    if (!data || !data.id || !currentSection) return;
    let container = currentSection.querySelector('#tree-output');
    if (!container) {
      container = document.createElement('ul');
      container.id = 'tree-output';
      container.className = 'po-tree';
      currentSection.appendChild(container);
    }
    // Append as a new branch (sibling of root's children)
    const rootLi = container.querySelector(':scope > li');
    let rootUl = rootLi ? rootLi.querySelector(':scope > ul') : null;
    if (!rootUl && rootLi) {
      rootUl = document.createElement('ul');
      rootLi.appendChild(rootUl);
    }
    const target = rootUl || container;
    target.appendChild(renderDecompNode(data, false));
    scroller.scroll();
  });

  // --- Execute: task list (incremental — preserves existing nodes on redecompose) ---
  on('exec:tree', ({ data }) => {
    if (!data || !data.batches || !currentSection) return;
    let container = currentSection.querySelector('#exec-output');
    if (!container) {
      container = document.createElement('div');
      container.id = 'exec-output';
      container.className = 'po-exec';
      currentSection.appendChild(container);
    }

    // Collect existing task nodes to preserve their state
    const existingNodes = {};
    container.querySelectorAll('.exec-node').forEach(node => {
      existingNodes[node.dataset.taskId] = node;
    });

    // Rebuild batch structure, reusing existing nodes
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
          // Reuse existing node (preserves completed/failed/running state)
          batchDiv.appendChild(existing);
          delete existingNodes[task.id];
        } else {
          // New task (from redecompose) — create fresh
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

  // --- Execute: task status updates ---
  on('task:state', ({ data }) => {
    const { task_id, status } = data;
    const node = processBody.querySelector(`.exec-node[data-task-id="${task_id}"]`);
    if (!node) return;
    node.classList.remove(
      'exec-pending', 'exec-running', 'exec-verifying',
      'exec-retrying', 'exec-decomposing', 'exec-completed', 'exec-failed',
    );
    node.classList.add(`exec-${status}`);

    // Scroll to the batch containing this task (not bottom)
    const batch = node.closest('.exec-batch');
    if (batch && scroller.isLocked()) {
      batch.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  });
}

// --- Helpers ---

function appendFileItem(stageName) {
  if (!currentSection) return;
  const item = document.createElement('div');
  item.className = 'po-file-item';
  item.dataset.stage = stageName;

  const icon = document.createTextNode('\uD83D\uDCC4 ');
  const label = document.createElement('span');
  const labels = { refine: 'Refined Idea', research: 'Research Results', write: 'Paper' };
  label.textContent = labels[stageName] || stageName;

  item.appendChild(icon);
  item.appendChild(label);

  item.addEventListener('click', () => viewOutput(stageName));
  currentSection.appendChild(item);
  scroller.scroll();
}

async function viewOutput(stageName) {
  try {
    const res = await fetch(`/api/stage/${stageName}/output`);
    if (!res.ok) return;
    const data = await res.json();
    const win = window.open('', '_blank', 'width=800,height=600');
    win.document.write(`<pre style="white-space:pre-wrap;font-family:monospace;padding:20px;">${escapeHtml(data.output)}</pre>`);
    win.document.title = stageName === 'refine' ? 'Refined Idea' : 'Paper';
  } catch (err) {
    console.error(`Failed to fetch ${stageName} output:`, err);
  }
}

function escapeHtml(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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
