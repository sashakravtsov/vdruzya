/* Django frontend — no third-party realtime vendors */
(() => {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {});
  }
  document.addEventListener('click', (e) => {
    const b = e.target.closest('.share-btn');
    if (!b) return;
    const u = b.getAttribute('data-url') || location.href;
    if (navigator.clipboard) navigator.clipboard.writeText(u).catch(() => prompt('Ссылка', u));
    else prompt('Ссылка', u);
    b.textContent = 'Ссылка скопирована';
  });
})();
