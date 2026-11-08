(() => {
  const toggle = document.querySelector('[data-toggle-sidebar]');
  const close = () => {
    document.body.classList.remove('sidebar-open');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
  };
  if (toggle) {
    toggle.addEventListener('click', () => {
      const opening = !document.body.classList.contains('sidebar-open');
      document.body.classList.toggle('sidebar-open', opening);
      toggle.setAttribute('aria-expanded', String(opening));
    });
  }
  document.querySelectorAll('[data-close-sidebar], .side-link[href]').forEach(el => el.addEventListener('click', close));
  document.addEventListener('keydown', event => { if (event.key === 'Escape') close(); });
})();
