/* Interacciones generales del layout */
(function () {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  const toggle = document.getElementById('menuToggle');

  function setOpen(open) {
    if (!sidebar) return;
    sidebar.classList.toggle('open', open);
    if (overlay) overlay.classList.toggle('show', open);
  }

  if (toggle) toggle.addEventListener('click', () => setOpen(!sidebar.classList.contains('open')));
  if (overlay) overlay.addEventListener('click', () => setOpen(false));
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') setOpen(false);
  });

  document.querySelectorAll('[data-toggle-password]').forEach((button) => {
    button.addEventListener('click', () => {
      const target = document.getElementById(button.dataset.togglePassword);
      if (!target) return;
      target.hidden = !target.hidden;
      if (!target.hidden) {
        const input = target.querySelector('input');
        if (input) input.focus();
      }
    });
  });
})();
