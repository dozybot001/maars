import { on } from './events.js';
import { createAutoScroller } from './autoscroll.js';
import { STAGE_LABELS, appendSeparator } from './shared.js';

let logOutput;
let scroller;
let activeStage = null;
let callBlocks = {};      // call_id → DOM text element
let callScrollers = {};   // call_id → autoscroller for chunk block
let currentSection = null;

export function initLogViewer() {
  logOutput = document.getElementById('log-output');
  scroller = createAutoScroller(logOutput);

  document.getElementById('copy-log').addEventListener('click', () => {
    const text = logOutput.innerText;
    const btn = document.getElementById('copy-log');
    try {
      // Fallback for non-HTTPS: use textarea + execCommand
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
      // Try modern API as fallback
      navigator.clipboard.writeText(text).then(() => {
        btn.textContent = 'Copied!';
      }).catch(() => {
        btn.textContent = 'Failed';
      });
    }
    setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
  });

  on('stage:state', ({ stage, data }) => {
    // Auto-save log when pipeline finishes or a stage fails
    if ((stage === 'write' && data === 'completed') || data === 'failed') {
      saveLogToDisk();
    }

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
      currentSection = appendSeparator(logOutput, STAGE_LABELS[stage] || stage.toUpperCase(), scroller);
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

function saveLogToDisk() {
  const text = logOutput.innerText;
  if (!text.trim()) return;
  fetch('/api/pipeline/save-log', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: text }),
  }).catch(() => {});
}
