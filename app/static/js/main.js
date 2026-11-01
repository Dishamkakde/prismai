/* PRISM AI — Main JavaScript */

// ── Mobile nav ──
function toggleMenu() {
  const links = document.getElementById('navLinks');
  if (links) links.classList.toggle('mobile-open');
}

// ── Password toggle ──
function togglePassword(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  input.type = input.type === 'password' ? 'text' : 'password';
  const icon = btn.querySelector('i');
  if (icon) { icon.classList.toggle('fa-eye'); icon.classList.toggle('fa-eye-slash'); }
}

// ── Animated counters ──
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('[data-count]').forEach(el => {
    const target = parseInt(el.dataset.count) || 0;
    const dur = 1400;
    const start = performance.now();
    function tick(now) {
      const p = Math.min((now - start) / dur, 1);
      el.textContent = Math.round(p * target);
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  });

  // Auto-dismiss flash messages
  setTimeout(() => {
    document.querySelectorAll('.flash').forEach(f => {
      f.style.transition = 'opacity 0.4s';
      f.style.opacity = '0';
      setTimeout(() => f.remove(), 400);
    });
  }, 5000);
});

// ── Navbar shadow on scroll ──
window.addEventListener('scroll', () => {
  const nav = document.getElementById('navbar');
  if (nav) nav.style.boxShadow = window.scrollY > 10
    ? '0 2px 12px rgba(32,42,58,0.08)'
    : '0 1px 2px rgba(0,0,0,0.05)';
});
