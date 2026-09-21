// Arrow keys move between slides, Escape closes the filter drawer.
document.addEventListener('keydown', function (e) {
  var t = e.target;
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) { return; }
  var drawerOpen = document.querySelector('.drawer.open');
  if (drawerOpen) {
    if (e.key === 'Escape') { var c = document.getElementById('drawer-close'); if (c) { c.click(); } }
    return;
  }
  var id = e.key === 'ArrowRight' ? 'next-btn' : (e.key === 'ArrowLeft' ? 'prev-btn' : null);
  if (id) { var b = document.getElementById(id); if (b && !b.disabled) { b.click(); } }
});
