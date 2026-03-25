import { on } from './events.js';
import { stageAction } from './api.js';

const STAGE_ORDER = ['refine', 'plan', 'execute', 'write'];

/**
 * Declarative button enable/disable rules per state.
 * No "run" — START is the only pipeline entry point.
 */
const BUTTON_RULES = {
  idle:      { stop: false, resume: false, retry: false },
  running:   { stop: true,  resume: false, retry: true  },
  paused:    { stop: false, resume: true,  retry: true  },
  completed: { stop: false, resume: false, retry: true  },
  failed:    { stop: false, resume: false, retry: true  },
};

// Track each stage's current state
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
  STAGE_ORDER.forEach((stageName) => {
    const card = document.querySelector(`[data-stage="${stageName}"]`);
    if (!card) return;

    const state = stageStates[stageName];

    // Update badge
    const badge = card.querySelector('.stage-badge');
    badge.textContent = state;
    badge.dataset.status = state;

    // Update active border
    card.dataset.active = (state === 'running') ? 'true' : 'false';

    // Button rules
    const rules = BUTTON_RULES[state];
    if (!rules) return;

    for (const [action, enabled] of Object.entries(rules)) {
      const btn = card.querySelector(`[data-action="${action}"]`);
      if (btn) btn.disabled = !enabled;
    }
  });
}
