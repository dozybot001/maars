/**
 * Auto-scroll manager for panel-body elements.
 * Scrolls to bottom on new content.
 * Unlocks ONLY on user wheel/touch scroll, not on programmatic scroll.
 * Re-locks when user scrolls back to bottom.
 */
export function createAutoScroller(el) {
  let locked = true;

  // Only real user input (wheel/touch) can unlock
  el.addEventListener('wheel', () => {
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
    locked = atBottom;
  }, { passive: true });

  el.addEventListener('touchmove', () => {
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
    locked = atBottom;
  }, { passive: true });

  return {
    scroll() {
      if (locked) {
        el.scrollTop = el.scrollHeight;
      }
    },
    reset() {
      locked = true;
      el.scrollTop = el.scrollHeight;
    },
  };
}
