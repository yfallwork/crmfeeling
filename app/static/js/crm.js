/* ══════════════════════════════════════════════════════
   CRM Feeling Experience — JS principal
   ══════════════════════════════════════════════════════ */

/* ── CSRF: adjuntar el token a toda petición fetch() de escritura ── */
(function () {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (!meta) return;
  const token = meta.content;
  const UNSAFE_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE'];
  const originalFetch = window.fetch;
  window.fetch = function (input, init) {
    init = init || {};
    const method = (init.method || 'GET').toUpperCase();
    if (UNSAFE_METHODS.includes(method)) {
      init.headers = new Headers(init.headers || {});
      if (!init.headers.has('X-CSRFToken')) {
        init.headers.set('X-CSRFToken', token);
      }
    }
    return originalFetch(input, init);
  };
})();

/* ── SIDEBAR MOBILE TOGGLE ───────────────────────────── */
function toggleSidebar() {
  const sidebar   = document.getElementById('sidebar');
  const backdrop  = document.getElementById('sidebarBackdrop');
  if (!sidebar) return;
  const isOpen = sidebar.classList.toggle('open');
  backdrop?.classList.toggle('show', isOpen);
  document.body.style.overflow = isOpen ? 'hidden' : '';
}

function closeSidebar() {
  const sidebar  = document.getElementById('sidebar');
  const backdrop = document.getElementById('sidebarBackdrop');
  sidebar?.classList.remove('open');
  backdrop?.classList.remove('show');
  document.body.style.overflow = '';
}

document.addEventListener('click', function (e) {
  const sidebar = document.getElementById('sidebar');
  const toggles = document.querySelectorAll('.sidebar-toggle');
  const clickedToggle = [...toggles].some(t => t.contains(e.target));
  if (sidebar?.classList.contains('open') && !sidebar.contains(e.target) && !clickedToggle) {
    closeSidebar();
  }
});


/* ── CONTADORES ANIMADOS ─────────────────────────────── */
function animarContadores() {
  document.querySelectorAll('[data-count-to]').forEach(el => {
    const target   = parseFloat(el.dataset.countTo) || 0;
    const suffix   = el.dataset.suffix   ?? '';
    const prefix   = el.dataset.prefix   ?? '';
    const decimals = parseInt(el.dataset.decimals ?? '0', 10);
    const duration = 850;
    const startTs  = performance.now();

    // Formatear número con separador de miles en español
    function fmt(n) {
      if (decimals > 0) return n.toFixed(decimals);
      return Math.round(n).toLocaleString('es-ES');
    }

    function tick(now) {
      const progress = Math.min((now - startTs) / duration, 1);
      // Ease-out cubic
      const eased   = 1 - Math.pow(1 - progress, 3);
      el.textContent = prefix + fmt(target * eased) + suffix;
      if (progress < 1) requestAnimationFrame(tick);
    }

    // Empezar desde 0
    el.textContent = prefix + fmt(0) + suffix;
    requestAnimationFrame(tick);
  });
}

document.addEventListener('DOMContentLoaded', animarContadores);


/* ── CMD+K BÚSQUEDA GLOBAL ──────────────────────────── */
(function () {
  let timer    = null;
  let selected = -1;

  /* — Abrir / cerrar — */
  function openSearch() {
    const overlay = document.getElementById('searchOverlay');
    const input   = document.getElementById('searchInput');
    if (!overlay) return;
    overlay.classList.add('open');
    selected = -1;
    showHint();
    setTimeout(() => input?.focus(), 60);
  }

  function closeSearch() {
    const overlay = document.getElementById('searchOverlay');
    const input   = document.getElementById('searchInput');
    overlay?.classList.remove('open');
    if (input) input.value = '';
    showHint();
    selected = -1;
  }

  window.openSearch  = openSearch;
  window.closeSearch = closeSearch;

  /* — Atajos de teclado — */
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      const overlay = document.getElementById('searchOverlay');
      overlay?.classList.contains('open') ? closeSearch() : openSearch();
      return;
    }
    const overlay = document.getElementById('searchOverlay');
    if (!overlay?.classList.contains('open')) return;

    const items = [...document.querySelectorAll('.search-item')];

    if (e.key === 'Escape') { closeSearch(); return; }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selected = Math.min(selected + 1, items.length - 1);
      highlight(items);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selected = Math.max(selected - 1, 0);
      highlight(items);
    } else if (e.key === 'Enter' && selected >= 0) {
      items[selected]?.click();
    }
  });

  function highlight(items) {
    items.forEach((el, i) => {
      el.classList.toggle('active', i === selected);
      if (i === selected) el.scrollIntoView({ block: 'nearest' });
    });
  }

  /* — Input con debounce — */
  document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('searchInput')?.addEventListener('input', function () {
      clearTimeout(timer);
      const q = this.value.trim();
      selected = -1;
      if (q.length < 2) { showHint(); return; }
      timer = setTimeout(() => buscar(q), 180);
    });

    // Cerrar al hacer clic en el overlay (fuera del modal)
    document.getElementById('searchOverlay')?.addEventListener('click', function (e) {
      if (e.target === this) closeSearch();
    });
  });

  /* — Fetch — */
  function buscar(q) {
    fetch(`/api/buscar?q=${encodeURIComponent(q)}`)
      .then(r => r.json())
      .then(data => renderResults(data, q))
      .catch(() => showEmpty('Error de red'));
  }

  /* — Renderizado — */
  function showHint() {
    setResults(`
      <div class="search-hint">
        <i class="bi bi-arrow-up-short"></i>
        <i class="bi bi-arrow-down-short"></i> navegar &nbsp;
        <kbd>Enter</kbd> abrir &nbsp;
        <kbd>Esc</kbd> cerrar
      </div>`);
  }

  function showEmpty(msg) {
    setResults(`<div class="search-empty">
      <i class="bi bi-search"></i>${msg}</div>`);
  }

  function setResults(html) {
    const el = document.getElementById('searchResults');
    if (el) el.innerHTML = html;
  }

  function hl(text, q) {
    if (!text || !q) return text || '';
    const re = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return String(text).replace(re, '<mark class="hl">$1</mark>');
  }

  function renderResults(data, q) {
    let html = '';

    if (data.clientes?.length) {
      html += '<div class="search-section-label">Clientes</div>';
      data.clientes.forEach(c => {
        html += `<a href="${c.url}" class="search-item" onclick="closeSearch()">
          <div class="search-item-icon bg-primary-soft">
            <i class="bi bi-person" style="color:var(--red-dark)"></i>
          </div>
          <div class="min-w-0 flex-1">
            <div class="search-item-title">${hl(c.nombre, q)}</div>
            <div class="search-item-sub">
              ${c.email ? hl(c.email, q) : ''}
              ${c.telefono ? ' · ' + hl(c.telefono, q) : ''}
            </div>
          </div>
          <i class="bi bi-arrow-right search-item-arrow"></i>
        </a>`;
      });
    }

    if (data.reservas?.length) {
      html += '<div class="search-section-label">Reservas</div>';
      data.reservas.forEach(r => {
        html += `<a href="${r.url}" class="search-item" onclick="closeSearch()">
          <div class="search-item-icon bg-warning-soft">
            <i class="bi bi-calendar-check" style="color:#B45309"></i>
          </div>
          <div class="min-w-0 flex-1">
            <div class="search-item-title">${hl(r.cliente, q)}</div>
            <div class="search-item-sub">
              ${r.experiencia} · ${r.fecha}
              &nbsp;<span class="badge estado-${r.estado}" style="font-size:.63rem">${r.estado}</span>
            </div>
          </div>
          <i class="bi bi-arrow-right search-item-arrow"></i>
        </a>`;
      });
    }

    if (!html) {
      html = `<div class="search-empty">
        <i class="bi bi-search"></i>
        Sin resultados para <strong>"${q}"</strong>
      </div>`;
    }

    setResults(html);
    selected = -1;
  }
})();


/* ── AUTO-DISMISS ALERTS ─────────────────────────────── */
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.alert-dismissible').forEach(function (alert) {
    setTimeout(function () {
      bootstrap.Alert.getOrCreateInstance(alert)?.close();
    }, 5000);
  });
});
