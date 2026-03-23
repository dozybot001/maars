import { on } from './events.js';
import { createAutoScroller } from './autoscroll.js';

const STAGE_LABELS = {
  refine: 'REFINE',
  plan: 'PLAN',
  execute: 'EXECUTE',
  write: 'WRITE',
};

let logOutput;
let scroller;
let activeStage = null;
let callBlocks = {};      // call_id → DOM text element
let callScrollers = {};   // call_id → autoscroller for chunk block
let currentSection = null;

export function initLogViewer() {
  logOutput = document.getElementById('log-output');
  scroller = createAutoScroller(logOutput);

  on('stage:state', ({ stage, data }) => {
    if (data === 'idle') {
      logOutput.innerHTML = '';
      activeStage = null;
      callBlocks = {};
      callScrollers = {};
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
      callBlocks = {};
      callScrollers = {};
      appendSeparator(STAGE_LABELS[stage] || stage.toUpperCase());
    }
  });

  on('log:chunk', ({ stage, data }) => {
    const callId = data.call_id;

    if (data.label && callId) {
      const label = document.createElement('div');
      label.className = 'log-label';
      label.textContent = data.text;
      currentSection.appendChild(label);

      const block = document.createElement('div');
      block.className = 'log-text';
      currentSection.appendChild(block);
      callBlocks[callId] = block;
      callScrollers[callId] = createAutoScroller(block);
      scroller.scroll();
      return;
    }

    let block;
    if (callId && callBlocks[callId]) {
      block = callBlocks[callId];
      block.appendChild(document.createTextNode(data.text));
    } else {
      block = currentSection
        ? currentSection.lastElementChild
        : logOutput.lastElementChild;
      if (!block || !block.classList.contains('log-text')) {
        block = document.createElement('div');
        block.className = 'log-text';
        (currentSection || logOutput).appendChild(block);
      }
      const text = data.text || data;
      block.appendChild(document.createTextNode(text));
    }
    if (callId && callScrollers[callId]) {
      callScrollers[callId].scroll();
    } else {
      block.scrollTop = block.scrollHeight;
    }
    scroller.scroll();
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

function appendSeparator(label) {
  const sep = document.createElement('div');
  sep.className = 'log-separator';
  sep.textContent = `── ${label} ──`;
  sep.addEventListener('click', () => {
    const section = sep.nextElementSibling;
    if (section && section.classList.contains('log-section')) {
      section.classList.toggle('collapsed');
      sep.classList.toggle('is-collapsed');
    }
  });
  logOutput.appendChild(sep);

  currentSection = document.createElement('div');
  currentSection.className = 'log-section';
  logOutput.appendChild(currentSection);
  scroller.scroll();
}
