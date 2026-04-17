/* ============ MAARS docs — shared behavior ============ */

// language selection (shared with landing via localStorage key 'maars-lang')
function initLang(T) {
  const saved = localStorage.getItem('maars-lang');
  const lang = (saved === 'en' || saved === 'zh')
    ? saved
    : ((navigator.language || 'en').toLowerCase().startsWith('zh') ? 'zh' : 'en');
  applyLang(T, lang);
  document.querySelectorAll('[data-lang-btn]').forEach(b => {
    b.addEventListener('click', () => applyLang(T, b.getAttribute('data-lang-btn')));
  });
}

function applyLang(T, lang) {
  const dict = T[lang] || T.en;
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (dict[key] != null) el.innerHTML = dict[key];
  });
  document.querySelectorAll('[data-i18n-href]').forEach(el => {
    const key = el.getAttribute('data-i18n-href');
    if (dict[key] != null) el.setAttribute('href', dict[key]);
  });
  document.querySelectorAll('[data-lang-btn]').forEach(b => {
    b.classList.toggle('active', b.getAttribute('data-lang-btn') === lang);
  });
  localStorage.setItem('maars-lang', lang);
}

// click-to-copy card
function initCopy() {
  document.querySelectorAll('[data-copy-target]').forEach(card => {
    const fire = async () => {
      const code = document.getElementById(card.getAttribute('data-copy-target'));
      if (!code) return;
      const text = code.innerText
        .split('\n')
        .filter(line => !line.trim().startsWith('#') && line.trim() !== '')
        .join('\n');
      try { await navigator.clipboard.writeText(text); }
      catch (e) {
        const ta = document.createElement('textarea');
        ta.value = text; document.body.appendChild(ta);
        ta.select(); document.execCommand('copy'); ta.remove();
      }
      card.classList.add('copied');
      clearTimeout(card._resetTimer);
      card._resetTimer = setTimeout(() => card.classList.remove('copied'), 1600);
    };
    card.addEventListener('click', fire);
    card.addEventListener('keydown', ev => {
      if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); fire(); }
    });
  });
}

// scrollspy TOC
function initScrollspy() {
  const links = Array.from(document.querySelectorAll('.toc a[href^="#"]'));
  if (!links.length) return;
  const byId = new Map();
  links.forEach(a => {
    const id = a.getAttribute('href').slice(1);
    const target = document.getElementById(id);
    if (target) byId.set(id, a);
  });
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      const link = byId.get(e.target.id);
      if (!link) return;
      if (e.isIntersecting) {
        links.forEach(l => l.classList.remove('active'));
        link.classList.add('active');
      }
    });
  }, { rootMargin: '-20% 0px -70% 0px', threshold: 0 });
  byId.forEach((_, id) => {
    const t = document.getElementById(id);
    if (t) observer.observe(t);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initCopy();
  initScrollspy();
});
