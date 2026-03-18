// ProjectFlow — Core JS

const API = {
  base: '/api',
  token: () => localStorage.getItem('pf_token'),

  headers() {
    const h = { 'Content-Type': 'application/json' };
    if (this.token()) h['Authorization'] = `Bearer ${this.token()}`;
    return h;
  },

  async request(method, path, body = null) {
    try {
      const opts = { method, headers: this.headers() };
      if (body) opts.body = JSON.stringify(body);
      const res = await fetch(this.base + path, opts);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      return data;
    } catch (err) {
      throw err;
    }
  },

  get: (path) => API.request('GET', path),
  post: (path, body) => API.request('POST', path, body),
  put: (path, body) => API.request('PUT', path, body),
  delete: (path) => API.request('DELETE', path),
};

// ─── AUTH ─────────────────────────────────────────────────────────────────────
const Auth = {
  user: null,

  async init() {
    if (!API.token()) return false;
    try {
      const user = await API.get('/auth/me');
      this.user = user;
      return true;
    } catch {
      // Use stored user data if API fails
      const stored = localStorage.getItem('pf_user');
      if (stored) {
        this.user = JSON.parse(stored);
        return true;
      }
      this.logout();
      return false;
    }
  },

  logout() {
    localStorage.removeItem('pf_token');
    localStorage.removeItem('pf_user');
    window.location.href = '/login';
  },

  requireAuth() {
    if (!API.token()) { window.location.href = '/login'; return false; }
    return true;
  }
};

// ─── TOAST NOTIFICATIONS ─────────────────────────────────────────────────────
const Toast = {
  container: null,

  init() {
    this.container = document.createElement('div');
    this.container.className = 'toast-container';
    document.body.appendChild(this.container);
  },

  show(msg, type = 'info', duration = 3500) {
    if (!this.container) this.init();
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    const icons = { success: '✓', error: '✕', info: 'ℹ', warning: '⚠' };
    el.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${msg}</span>`;
    this.container.appendChild(el);
    setTimeout(() => el.remove(), duration);
  },

  success: (msg) => Toast.show(msg, 'success'),
  error: (msg) => Toast.show(msg, 'error'),
  info: (msg) => Toast.show(msg, 'info'),
  warning: (msg) => Toast.show(msg, 'warning'),
};

// ─── MODAL HELPER ─────────────────────────────────────────────────────────────
const Modal = {
  show(id) {
    const el = document.getElementById(id);
    if (el) { el.classList.add('show'); }
  },
  hide(id) {
    const el = document.getElementById(id);
    if (el) { el.classList.remove('show'); }
  },
  hideAll() {
    document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('show'));
  }
};

// ─── UTILS ────────────────────────────────────────────────────────────────────
const Utils = {
  formatDate(dateStr) {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  },

  formatDateTime(dateStr) {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' +
           d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  },

  timeAgo(dateStr) {
    const d = new Date(dateStr);
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  },

  initials(name) {
    if (!name) return '?';
    return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  },

  priorityColor(p) {
    return { low: '#10b981', medium: '#f59e0b', high: '#ef4444', critical: '#9333ea' }[p] || '#6b7280';
  },

  statusLabel(s) {
    return { todo: 'To Do', in_progress: 'In Progress', review: 'In Review', done: 'Done' }[s] || s;
  },

  fileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
  },

  isOverdue(dateStr) {
    if (!dateStr) return false;
    return new Date(dateStr) < new Date();
  },

  avatarEl(user, size = 32) {
    const el = document.createElement('div');
    el.className = 'user-avatar';
    el.style.cssText = `width:${size}px;height:${size}px;font-size:${size * 0.35}px;background:${Utils.strColor(user.name)}`;
    if (user.avatar) {
      el.innerHTML = `<img src="${user.avatar}" alt="">`;
    } else {
      el.textContent = Utils.initials(user.name);
    }
    el.title = user.name;
    return el;
  },

  strColor(str) {
    const colors = ['#6366f1','#10b981','#f59e0b','#3b82f6','#ec4899','#8b5cf6','#06b6d4','#84cc16'];
    let hash = 0;
    for (let c of (str || '')) hash = c.charCodeAt(0) + ((hash << 5) - hash);
    return colors[Math.abs(hash) % colors.length];
  }
};

// ─── SIDEBAR INIT ─────────────────────────────────────────────────────────────
function initSidebar() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-item[href]').forEach(item => {
    if (item.getAttribute('href') === path ||
        (path.startsWith('/projects') && item.getAttribute('href') === '/projects')) {
      item.classList.add('active');
    }
  });

  // Mobile toggle
  const toggle = document.getElementById('sidebar-toggle');
  const sidebar = document.querySelector('.sidebar');
  if (toggle && sidebar) {
    toggle.addEventListener('click', () => sidebar.classList.toggle('open'));
  }

  // Load notifications count
  loadNotifCount();

  // User info in sidebar
  if (Auth.user) {
    const nameEl = document.getElementById('sidebar-user-name');
    const roleEl = document.getElementById('sidebar-user-role');
    const avatarEl = document.getElementById('sidebar-avatar');
    if (nameEl) nameEl.textContent = Auth.user.name;
    if (roleEl) roleEl.textContent = Auth.user.role;
    if (avatarEl) {
      avatarEl.style.background = Utils.strColor(Auth.user.name);
      avatarEl.textContent = Utils.initials(Auth.user.name);
    }
  }
}

async function loadNotifCount() {
  try {
    const data = await API.get('/notifications');
    const badge = document.getElementById('notif-badge');
    if (badge && data.unread > 0) {
      badge.textContent = data.unread;
      badge.style.display = 'flex';
    }
  } catch {}
}

// ─── NOTIFICATION PANEL ───────────────────────────────────────────────────────
async function toggleNotifPanel() {
  const panel = document.getElementById('notif-panel');
  if (!panel) return;
  panel.classList.toggle('show');
  if (panel.classList.contains('show')) {
    await loadNotifPanel();
  }
}

async function loadNotifPanel() {
  const panel = document.getElementById('notif-panel');
  if (!panel) return;
  try {
    const data = await API.get('/notifications');
    const list = panel.querySelector('.notif-list');
    if (!list) return;
    list.innerHTML = data.notifications.slice(0, 8).map(n => `
      <div class="notif-item ${n.is_read ? '' : 'unread'}" onclick="markNotifRead(${n.id})">
        ${!n.is_read ? '<div class="notif-dot"></div>' : '<div style="width:8px"></div>'}
        <div>
          <div class="notif-text"><strong>${n.title}</strong><br>${n.message}</div>
          <div class="notif-time">${Utils.timeAgo(n.created_at)}</div>
        </div>
      </div>
    `).join('') || '<div style="padding:20px;text-align:center;color:var(--text-2)">No notifications</div>';
  } catch {}
}

async function markNotifRead(id) {
  try {
    await API.put(`/notifications/${id}/read`, {});
    loadNotifPanel();
    loadNotifCount();
  } catch {}
}

async function markAllNotifRead() {
  try {
    await API.put('/notifications/read-all', {});
    Toast.success('All notifications marked as read');
    toggleNotifPanel();
    loadNotifCount();
  } catch {}
}

// Close panels on outside click
document.addEventListener('click', (e) => {
  const panel = document.getElementById('notif-panel');
  const btn = document.getElementById('notif-btn');
  if (panel && !panel.contains(e.target) && btn && !btn.contains(e.target)) {
    panel.classList.remove('show');
  }
});

// ─── TABS ─────────────────────────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;
      const container = btn.closest('.tabs').parentElement;
      container.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      container.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const pane = container.querySelector(`[data-tab-pane="${target}"]`);
      if (pane) pane.classList.add('active');
    });
  });
}

// Close modals on overlay click
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-overlay')) Modal.hideAll();
});

// ─── PAGE INIT ────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', async () => {
  Toast.init();
  const publicPages = ['/login', '/register'];
  if (!publicPages.includes(window.location.pathname)) {
    const ok = await Auth.init();
    if (!ok) return;
    initSidebar();
    initTabs();
  }
});
