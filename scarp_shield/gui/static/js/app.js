/* ═══════════════════════════════════════════════════════════════
   ScarpShield Core UI JavaScript
   CounterScarp.io — The Outer Wall of Defense
   ═══════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  /* ── API Helper ─────────────────────────────────────────────── */
  async function api(method, path, body = null) {
    const opts = {
      method: method.toUpperCase(),
      headers: { 'Accept': 'application/json' }
    };

    if (body !== null) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(path, opts);
      const data = await response.json().catch(() => null);

      if (!response.ok) {
        const err = new Error(data?.error || `HTTP ${response.status}`);
        err.status = response.status;
        err.data = data;
        throw err;
      }

      return data;
    } catch (err) {
      if (err.name === 'TypeError' && err.message.includes('fetch')) {
        showToast('Network error. Check your connection.', 'error');
      }
      throw err;
    }
  }

  /* ── Toast Notification System ──────────────────────────────── */
  function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = {
      success: '&#10003;',
      error: '&#10007;',
      warning: '&#9888;',
      info: '&#9432;'
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
      <span class="toast-icon">${icons[type] || icons.info}</span>
      <span class="toast-message">${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
      requestAnimationFrame(() => toast.classList.add('show'));
    });

    // Auto remove
    setTimeout(() => {
      toast.classList.add('toast-exit');
      toast.addEventListener('transitionend', () => toast.remove(), { once: true });
      // Fallback removal
      setTimeout(() => toast.remove(), 500);
    }, 4500);
  }

  /* ── SSE Connection Manager ─────────────────────────────────── */
  let sseConnection = null;

  function connectSSE() {
    if (sseConnection) {
      sseConnection.close();
    }

    try {
      sseConnection = new EventSource('/api/events/stream');

      sseConnection.onopen = () => {
        updateConnectionStatus(true);
      };

      sseConnection.onerror = () => {
        updateConnectionStatus(false);
      };

      sseConnection.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          dispatchCustomEvent('sse-message', data);
        } catch {
          dispatchCustomEvent('sse-message', { raw: event.data });
        }
      };

      // Listen for specific event types
      sseConnection.addEventListener('alert', (e) => {
        dispatchCustomEvent('sse-alert', JSON.parse(e.data));
      });

      sseConnection.addEventListener('contract', (e) => {
        dispatchCustomEvent('sse-contract', JSON.parse(e.data));
      });

      sseConnection.addEventListener('status', (e) => {
        dispatchCustomEvent('sse-status', JSON.parse(e.data));
      });
    } catch (err) {
      console.warn('[ScarpShield] SSE not available:', err);
      updateConnectionStatus(false);
    }
  }

  function disconnectSSE() {
    if (sseConnection) {
      sseConnection.close();
      sseConnection = null;
    }
  }

  function dispatchCustomEvent(name, detail) {
    window.dispatchEvent(new CustomEvent(name, { detail }));
  }

  function updateConnectionStatus(connected) {
    const dot = document.getElementById('conn-dot');
    const text = document.getElementById('conn-text');
    if (!dot || !text) return;

    if (connected) {
      dot.className = 'status-dot status-dot-active status-dot-pulse';
      text.textContent = 'Connected';
      text.style.color = '';
    } else {
      dot.className = 'status-dot status-dot-inactive';
      text.textContent = 'Disconnected';
      text.style.color = 'var(--text-dim)';
    }
  }

  /* ── Status Bar Updater ─────────────────────────────────────── */
  async function fetchStatus() {
    try {
      const data = await api('GET', '/api/status');

      const monitorStatus = document.getElementById('monitor-status');
      const contractsCount = document.getElementById('contracts-count');
      const alertsCount = document.getElementById('alerts-count');
      const lastUpdated = document.getElementById('last-updated');
      const statusDot = document.getElementById('status-dot');

      const running = data.running === true;

      if (monitorStatus) {
        monitorStatus.textContent = running ? 'Monitoring active' : 'Monitoring paused';
      }

      if (statusDot) {
        statusDot.className = running
          ? 'status-dot status-dot-active'
          : 'status-dot status-dot-inactive';
      }

      if (contractsCount) {
        contractsCount.textContent = data.contract_count ?? 0;
      }

      if (alertsCount) {
        const enabled = Array.isArray(data.enabled_alerts)
          ? data.enabled_alerts.length
          : 0;
        alertsCount.textContent = enabled;
      }

      if (lastUpdated) {
        const now = new Date();
        lastUpdated.textContent = now.toLocaleTimeString();
      }

      dispatchCustomEvent('status-updated', data);
    } catch (err) {
      // Silent fail — toast on repeated failures only
    }
  }

  /* ── Sidebar Active State ───────────────────────────────────── */
  function highlightSidebar() {
    const path = window.location.pathname;
    document.querySelectorAll('.sidebar-nav a').forEach(link => {
      link.classList.toggle('active', link.getAttribute('href') === path);
    });
  }

  /* ── Modal Helper ───────────────────────────────────────────── */
  let modalResolve = null;

  function showModal(options = {}) {
    const overlay = document.getElementById('modal-overlay');
    const titleEl = document.getElementById('modal-title');
    const bodyEl = document.getElementById('modal-body');
    const footerEl = document.getElementById('modal-footer');
    const confirmBtn = document.getElementById('modal-confirm');
    const cancelBtn = document.getElementById('modal-cancel');

    if (!overlay) return Promise.reject(new Error('Modal not found'));

    titleEl.textContent = options.title || 'Confirm';
    bodyEl.innerHTML = options.body || '';

    confirmBtn.textContent = options.confirmText || 'Confirm';
    confirmBtn.className = `btn ${options.danger ? 'btn-danger' : 'btn-primary'}`;
    cancelBtn.textContent = options.cancelText || 'Cancel';

    // Show/hide footer based on options
    if (options.hideFooter) {
      footerEl.style.display = 'none';
    } else {
      footerEl.style.display = '';
    }

    overlay.classList.add('active');
    overlay.setAttribute('aria-hidden', 'false');

    return new Promise((resolve) => {
      modalResolve = resolve;
    });
  }

  function hideModal(result = false) {
    const overlay = document.getElementById('modal-overlay');
    if (!overlay) return;

    overlay.classList.remove('active');
    overlay.setAttribute('aria-hidden', 'true');

    if (modalResolve) {
      modalResolve(result);
      modalResolve = null;
    }
  }

  function setupModalListeners() {
    const overlay = document.getElementById('modal-overlay');
    const closeBtn = document.getElementById('modal-close');
    const cancelBtn = document.getElementById('modal-cancel');
    const confirmBtn = document.getElementById('modal-confirm');

    if (!overlay) return;

    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) hideModal(false);
    });

    closeBtn?.addEventListener('click', () => hideModal(false));
    cancelBtn?.addEventListener('click', () => hideModal(false));
    confirmBtn?.addEventListener('click', () => hideModal(true));

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && overlay.classList.contains('active')) {
        hideModal(false);
      }
    });
  }

  /* ── Format Helpers ─────────────────────────────────────────── */
  function truncateAddress(addr, start = 6, end = 4) {
    if (!addr || addr.length <= start + end + 3) return addr || '';
    return `${addr.slice(0, start)}…${addr.slice(-end)}`;
  }

  function formatTimestamp(ts) {
    if (!ts) return '--';
    const date = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
    if (isNaN(date.getTime())) return String(ts);

    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHr = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHr / 24);

    if (diffSec < 60) return 'just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHr < 24) return `${diffHr}h ago`;
    if (diffDay < 7) return `${diffDay}d ago`;

    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function formatChain(chain) {
    if (!chain) return 'Unknown';
    const map = {
      ethereum: 'Ethereum',
      polygon: 'Polygon',
      bsc: 'BSC',
      arbitrum: 'Arbitrum',
      base: 'Base'
    };
    return map[chain.toLowerCase()] || chain.charAt(0).toUpperCase() + chain.slice(1);
  }

  /* ── Utility ────────────────────────────────────────────────── */
  function escapeHtml(str) {
    if (typeof str !== 'string') return String(str);
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  /* ── Mobile Sidebar Toggle ──────────────────────────────────── */
  function setupMobileNav() {
    // Add a hamburger button on mobile if not present
    const header = document.querySelector('.top-header');
    if (!header || document.getElementById('nav-toggle')) return;

    const toggle = document.createElement('button');
    toggle.id = 'nav-toggle';
    toggle.className = 'btn btn-ghost btn-sm';
    toggle.setAttribute('aria-label', 'Toggle navigation');
    toggle.innerHTML = '&#9776;';
    toggle.style.display = 'none';

    const brand = header.querySelector('.brand');
    if (brand) {
      brand.after(toggle);
    } else {
      header.prepend(toggle);
    }

    const mq = window.matchMedia('(max-width: 767px)');
    function handleMq() {
      toggle.style.display = mq.matches ? 'inline-flex' : 'none';
      if (!mq.matches) {
        document.getElementById('sidebar')?.classList.remove('open');
      }
    }

    toggle.addEventListener('click', () => {
      document.getElementById('sidebar')?.classList.toggle('open');
    });

    // Close sidebar when clicking a nav link on mobile
    document.querySelectorAll('.sidebar-nav a').forEach(link => {
      link.addEventListener('click', () => {
        if (mq.matches) {
          document.getElementById('sidebar')?.classList.remove('open');
        }
      });
    });

    handleMq();
    mq.addEventListener('change', handleMq);
  }

  /* ── Initialization ─────────────────────────────────────────── */
  function init() {
    highlightSidebar();
    setupModalListeners();
    setupMobileNav();

    // Poll status every 10s
    fetchStatus();
    setInterval(fetchStatus, 10000);

    // Connect SSE
    connectSSE();

    // Reconnect SSE on visibility change
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        disconnectSSE();
      } else {
        connectSSE();
      }
    });

    // Expose globals for inline scripts
    window.ScarpShield = {
      api,
      showToast,
      showModal,
      hideModal,
      connectSSE,
      disconnectSSE,
      truncateAddress,
      formatTimestamp,
      formatChain,
      escapeHtml
    };

    console.log('[ScarpShield] UI initialized');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
