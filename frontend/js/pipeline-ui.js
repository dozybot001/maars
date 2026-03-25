import { on } from './events.js';
import { stageAction } from './api.js';

const STAGE_ORDER = ['refine', 'plan', 'execute', 'write'];

/**
 * Declarative button enable/disable rules per state.
 */
const BUTTON_RULES = {
  idle:      { run: true,  stop: false, resume: false, retry: false },
  running:   { run: false, stop: true,  resume: false, retry: true  },
  paused:    { run: false, stop: false, resume: true,  retry: true  },
  completed: { run: false, stop: false, resume: false, retry: true  },
  failed:    { run: false, stop: false, resume: false, retry: true  },
};

// Track each stage's current state for cross-stage checks
const stageStates = {};
STAGE_ORDER.forEach((name) => { stageStates[name] = 'idle'; });

/**
 * Initialize pipeline UI: wire up buttons and listen for state events.
 */
export function initPipelineUI() {
  document.querySelectorAll('.stage-card').forEach((card) => {
    const stageName = card.dataset.stage;

    card.querySelectorAll('.stage-controls button').forEach((btn) => {
      const action = btn.dataset.action;
      btn.addEventListener('click', async () => {
        try {
          await stageAction(stageName, action);
        } catch (err) {
          console.error(`[${stageName}] ${action} error:`, err);
        }
      });
    });
  });

  on('stage:state', ({ stage, data }) => {
    stageStates[stage] = data;
    updateAllCards();
  });
}

function updateAllCards() {
  STAGE_ORDER.forEach((stageName, idx) => {
    const card = document.querySelector(`[data-stage="${stageName}"]`);
    if (!card) return;

    const state = stageStates[stageName];

    // Update badge
    const badge = card.querySelector('.stage-badge');
    badge.textContent = state;
    badge.dataset.status = state;

    // Update active border
    card.dataset.active = (state === 'running') ? 'true' : 'false';

    // Button rules for this stage's own state
    const rules = BUTTON_RULES[state];
    if (!rules) return;

    // Check if previous stage is completed
    const prevCompleted = idx > 0 && stageStates[STAGE_ORDER[idx - 1]] === 'completed';

    for (const [action, enabled] of Object.entries(rules)) {
      const btn = card.querySelector(`[data-action="${action}"]`);
      if (!btn) continue;

      if (action === 'run') {
        btn.disabled = !(enabled && prevCompleted);
      } else {
        btn.disabled = !enabled;
      }
    }
  });
}
