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

export function initLogViewer() {
  logOutput = document.getElementById('log-output');
  scroller = createAutoScroller(logOutput);
  tokenBadge = document.getElementById('token-estimate');

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
    if (data === 'idle') {
      logOutput.innerHTML = '';
      activeStage = null;
      callBlocks = {};
      callScrollers = {};
      currentSection = null;
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
      currentSection = appendSeparator(logOutput, STAGE_LABELS[stage] || stage.toUpperCase(), scroller);
    }
  });

  on('log:chunk', ({ stage, data }) => {
    const callId = data.call_id;

    if (data.label && callId) {
      // Auto-fold previous blocks, but respect user-expanded ones
      if (currentSection) {
        currentSection.querySelectorAll('.log-text:not(.folded):not(.user-expanded)').forEach(el => {
          el.classList.add('folded');
          const prev = el.previousElementSibling;
          if (prev && prev.classList.contains('log-label')) prev.classList.add('is-collapsed');
        });
      }

      const label = document.createElement('div');
      label.className = 'log-label';
      label.textContent = data.text;
      currentSection.appendChild(label);

      const block = document.createElement('div');
      block.className = 'log-text';
      currentSection.appendChild(block);

      label.addEventListener('click', () => {
        const nowFolded = block.classList.toggle('folded');
        label.classList.toggle('is-collapsed');
        if (nowFolded) {
          block.classList.remove('user-expanded');
        } else {
          // User expanding — protect from auto-fold
          block.classList.add('user-expanded');
        }
      });

      callBlocks[callId] = block;
      callScrollers[callId] = createAutoScroller(block);
      scroller.scroll();
      return;
    }

    const chunkText = data.text || data;

    let block;
    if (callId && callBlocks[callId]) {
      block = callBlocks[callId];
      block.appendChild(document.createTextNode(chunkText));
    } else {
      block = currentSection
        ? currentSection.lastElementChild
        : logOutput.lastElementChild;
      if (!block || !block.classList.contains('log-text')) {
        block = document.createElement('div');
        block.className = 'log-text';
        (currentSection || logOutput).appendChild(block);
      }
      block.appendChild(document.createTextNode(chunkText));
    }
    if (callId && callScrollers[callId]) {
      callScrollers[callId].scroll();
    } else {
      block.scrollTop = block.scrollHeight;
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

function updateTokenBadge() {
  if (!tokenBadge) return;
  if (totalTokens === 0) {
    tokenBadge.textContent = '';
    return;
  }
  const display = totalTokens >= 1000
    ? `${(totalTokens / 1000).toFixed(1)}k tokens`
    : `${totalTokens} tokens`;
  tokenBadge.textContent = display;
}
