/**
 * Simple modal for displaying document content.
 */

let overlay, title, content;

export function initModal() {
  overlay = document.getElementById('modal-overlay');
  title = document.getElementById('modal-title');
  content = document.getElementById('modal-content');

  document.getElementById('modal-close').addEventListener('click', hideModal);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) hideModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !overlay.classList.contains('hidden')) hideModal();
  });
}

export function showModal(titleText, bodyText) {
  title.textContent = titleText;
  if (typeof marked !== 'undefined' && marked.parse) {
    content.innerHTML = marked.parse(bodyText || '');
    content.classList.remove('plain-text');
  } else {
    content.textContent = bodyText;
    content.classList.add('plain-text');
  }
  overlay.classList.remove('hidden');
}

export function hideModal() {
  overlay.classList.add('hidden');
}
