/**
 * Shared constants and DOM helpers used by multiple viewer modules.
 */

export const STAGE_LABELS = {
  refine: 'REFINE',
  research: 'RESEARCH',
  write: 'WRITE',
};

/**
 * Safely parse JSON from an SSE event, returning null on failure.
 */
export function safeParse(e) {
  try {
    return JSON.parse(e.data);
  } catch {
    console.warn('[SSE] Failed to parse event data:', e.data);
    return null;
  }
}

/**
 * Create a fold group (label + body) inside a parent container.
 * Used for all collapsible levels: phase, task, tool calls.
 * Returns { label, body }.
 */
export function createFold(parent, labelText) {
  const label = document.createElement('div');
  label.className = 'fold-label';
  label.textContent = labelText;

  const body = document.createElement('div');
  body.className = 'fold-body';

  label.addEventListener('click', () => {
    const collapsed = body.classList.toggle('collapsed');
    label.classList.toggle('is-collapsed');
    if (collapsed) body.classList.remove('user-expanded');
    else body.classList.add('user-expanded');
  });

  parent.appendChild(label);
  parent.appendChild(body);
  return { label, body };
}

/**
 * Append a collapsible separator + section to a container.
 * Returns the new section element.
 */
export function appendSeparator(container, label, scroller) {
  const sep = document.createElement('div');
  sep.className = 'log-separator';
  sep.textContent = `── ${label} ──`;
  sep.addEventListener('click', () => {
    const section = sep.nextElementSibling;
    if (section && section.classList.contains('log-section')) {
      const nowCollapsed = section.classList.toggle('collapsed');
      sep.classList.toggle('is-collapsed');
      if (nowCollapsed) {
        section.classList.remove('user-expanded');
      } else {
        section.classList.add('user-expanded');
      }
    }
  });
  container.appendChild(sep);

  const section = document.createElement('div');
  section.className = 'log-section';
  container.appendChild(section);
  scroller.scroll();
  return section;
}
