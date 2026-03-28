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
