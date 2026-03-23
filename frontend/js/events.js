/**
 * Custom event bus for MAARS frontend.
 * All events are namespaced under "maars:" prefix.
 */

export function emit(name, detail) {
  document.dispatchEvent(new CustomEvent(`maars:${name}`, { detail }));
}

export function on(name, handler) {
  document.addEventListener(`maars:${name}`, (e) => handler(e.detail));
}
