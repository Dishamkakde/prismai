/* PRISM AI — Portal JavaScript */

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  if (sidebar) sidebar.classList.toggle('open');
  if (overlay) overlay.classList.toggle('visible');
}

document.addEventListener('DOMContentLoaded', function () {
  // Auto-dismiss portal flash messages
  setTimeout(() => {
    document.querySelectorAll('.portal-flash .flash').forEach(f => {
      f.style.transition = 'opacity 0.4s';
      f.style.opacity = '0';
      setTimeout(() => f.remove(), 400);
    });
  }, 5000);
});
