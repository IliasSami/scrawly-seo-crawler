import '@fontsource-variable/inter';
import * as d3 from 'd3';
import { createThemeToggle, initTheme } from './theme.js';
import { startApp, ownerKey, onCrawlFinished } from './edition.js';
import { routeExternalLinks, openExternal, saveDownload } from './components/external.js';
import { PROJECT } from './components/help-rail.js';
import { esc } from './components/escape.js';
import { Wizard } from './components/wizard.js';
import { ClientWizard } from './components/client-wizard.js';
import { CrawlConsole } from './components/crawl-console.js';
import { ConfigPanel } from './components/config-panel.js';
import { Explorer } from './components/explorer.js';
import { SiteGraph } from './components/site-graph.js';
import { PublicAudit } from './components/public-audit.js';
import { ResourcesView } from './components/resources-view.js';
import { SerpView } from './components/serp-view.js';
import { AgenticView } from './components/agentic-view.js';
import { IntegrationsPanel } from './components/integrations-panel.js';
import { Drawer } from './components/drawer.js';
import { createHealthScoreRing } from './components/health-score.js';
import { createIssueCard } from './components/issue-card.js';
import { IssuesView } from './components/issues-view.js';
import { statTile, donut, bars, histogram, stackedBar } from './components/charts.js';
import { AiAssistant } from './components/ai-assistant.js';
import { FixAgent } from './components/fix-agent.js';
import { toast } from './components/toast.js';

const API_BASE = '/api';

// Edition-specific behaviour lives in edition.js (imported first). External links
// open in the user's browser.
routeExternalLinks();

// Keyboard access for the icon rail and the view tabs (they are clickable divs):
// focusable, announced as buttons/tabs, and activated with Enter or Space.
function makeKeyboardAccessible() {
  const wire = (el, role) => {
    if (el.dataset.kbd) return;
    el.dataset.kbd = '1';
    el.setAttribute('role', role);
    el.tabIndex = 0;
    if (!el.getAttribute('aria-label') && el.title) el.setAttribute('aria-label', el.title);
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); el.click(); }
    });
  };
  document.querySelectorAll('.global-nav .nav-icon:not(button), .global-nav .nav-brand')
    .forEach((el) => wire(el, 'button'));
  document.querySelector('.project-nav .pn-tabs')?.setAttribute('role', 'tablist');
  document.querySelectorAll('.project-nav .tab').forEach((el) => wire(el, 'tab'));
}
makeKeyboardAccessible();

// Resilient JSON fetch. The UI is a frontend for the local Scrawly engine served
// at the same origin (API_BASE is relative); when that process is down every /api
// call fails and the app looks dead with only a console error. This returns null
// on any failure (offline, empty body, non-2xx) and shows ONE explanatory banner
// instead — and clears it the moment the backend is back. This is the fix for the
// "I can't add clients / nothing works" symptom.
let _backendOffline = false;
async function fetchJson(path, opts) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, opts);
  } catch {
    _setBackendOffline(true);   // no response at all: the engine isn't reachable
    return null;
  }
  // Any HTTP answer (even 404/500) means the engine is up; a single failing call
  // must not claim the whole app is offline.
  _setBackendOffline(false);
  if (!res.ok) return null;
  try {
    const text = await res.text();
    return text ? JSON.parse(text) : null;
  } catch {
    return null;
  }
}
function _setBackendOffline(off) {
  if (off === _backendOffline) return;
  _backendOffline = off;
  let bar = document.getElementById('backend-offline-bar');
  if (off) {
    if (!bar) {
      bar = document.createElement('div');
      bar.id = 'backend-offline-bar';
      bar.setAttribute('role', 'alert');
      bar.textContent = '⚠ Scrawly’s engine isn’t responding. It usually recovers on its own; '
        + 'if this message stays, close and reopen Scrawly.';
      document.body.appendChild(bar);
    }
  } else if (bar) { bar.remove(); }
}

// App State
let currentCrawlId = null;
let currentCrawlData = { issues: [], urls: [] };
let currentClient = null;
let currentCanFix = false;   // auto-fix only exists for connected WordPress sites
let currentFixes = { byIssue: {}, list: [] };  // fixes the agent has applied
const crawlsById = {};

// The agentic Fix flow writes through the WordPress Connector, so it only makes
// sense for WordPress projects. Non-WP sites never show a Fix button.
function isWordPressClient(c) {
  if (!c) return false;
  const stack = (c.detected_stack && (c.detected_stack.stack || c.detected_stack.cms)) || '';
  return c.connected === true || /wordpress/i.test(String(stack));
}

// Views that belong to an open project — the top bar (project tabs + context)
// only makes sense here. Chrome views (home, settings, config, public, wizards)
// hide the top bar entirely.
const PROJECT_VIEWS = new Set([
  'view-dashboard', 'view-explorer', 'view-resources', 'view-serp',
  'view-issues', 'view-agentic', 'view-visuals', 'view-compare', 'view-reports',
]);

// Navigation Logic
function switchProjectView(targetId) {
  document.querySelectorAll('.project-nav .tab').forEach(t => {
    t.classList.remove('active');
    t.setAttribute('aria-selected', 'false');
  });
  const activeTab = document.querySelector(`.project-nav .tab[data-target="${targetId}"]`);
  if (activeTab) { activeTab.classList.add('active'); activeTab.setAttribute('aria-selected', 'true'); }

  // Top bar visible only inside a project (or a loaded public-audit result).
  const nav = document.querySelector('.project-nav');
  if (nav) nav.classList.toggle('is-hidden', !PROJECT_VIEWS.has(targetId));

  document.querySelectorAll('.main-content .view-section').forEach(v => v.classList.remove('active'));
  const targetView = document.getElementById(targetId);
  if (targetView) targetView.classList.add('active');

  if (targetId === 'view-visuals') {
    setTimeout(() => renderSiteArchitecture(currentCrawlId), 50);
  }
  if (targetId === 'view-resources') {
    resourcesView.load(currentCrawlId);
  }
  if (targetId === 'view-serp') {
    serpView.load(currentCrawlId);
  }
  if (targetId === 'view-agentic') {
    agenticView.load(currentCrawlId);
  }
  if (targetId === 'view-reports') {
    loadReports(currentCrawlId);
  }
}

// Reports hub — a live, branded preview of the exported report + branding status.
async function loadReports(crawlId) {
  const preview = document.getElementById('rpt-preview');
  const brandStatus = document.getElementById('rpt-brand-status');
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  if (!preview) return;
  if (!crawlId) {
    preview.innerHTML = '<div class="rpt-empty">Open a project to preview its report.</div>';
    if (brandStatus) brandStatus.textContent = ' - ';
    return;
  }
  preview.innerHTML = '<div class="rpt-empty">Building preview…</div>';
  const [d, s] = await Promise.all([fetchJson(`/dashboard/${crawlId}`), fetchJson('/settings')]);
  const brandName = (s && s.report_brand_name) || 'Scrawly';
  const brandColor = (s && s.report_brand_color) || '#6366f1';
  if (brandStatus) {
    brandStatus.innerHTML = (s && s.report_brand_name)
      ? `White-labelled as <strong>${esc(brandName)}</strong>${s.report_brand_logo ? ' with your logo' : ''}.`
      : 'Using the default <strong>Scrawly</strong> branding - add your agency name, logo and colour.';
  }
  if (!d) { preview.innerHTML = '<div class="rpt-empty">Preview unavailable.</div>'; return; }
  const c = crawlsById[crawlId];
  const site = (c && c.base_url) || d.target_url || '';
  const health = d.health_score ?? 0;
  const t = d.totals || {};
  const grad = `linear-gradient(135deg, ${esc(brandColor)}, color-mix(in srgb, ${esc(brandColor)} 55%, #a855f7))`;
  preview.innerHTML = `
    <div class="rpt-cover" style="background:${grad}">
      <div style="min-width:0;">
        <div class="rpt-cover-brand"><span class="rpt-cover-mark">${esc((brandName[0] || 'S').toUpperCase())}</span>${esc(brandName)}</div>
        <h2>Technical SEO Audit</h2>
        <div class="rpt-cover-site">${esc(site)}</div>
      </div>
      <div class="rpt-cover-ring"><div id="rpt-ring"></div><div class="rpt-cover-grade">${healthGrade(health)}</div></div>
    </div>
    <div class="rpt-cover-stats">
      <div class="rpt-cover-stat"><div class="v">${t.urls ?? 0}</div><div class="l">Pages</div></div>
      <div class="rpt-cover-stat"><div class="v">${d.indexable_pct ?? 0}%</div><div class="l">Indexable</div></div>
      <div class="rpt-cover-stat"><div class="v">${t.issues ?? 0}</div><div class="l">Issues</div></div>
      <div class="rpt-cover-stat"><div class="v">${(d.severity && d.severity.Critical) ?? 0}</div><div class="l">Critical</div></div>
    </div>`;
  const ring = document.getElementById('rpt-ring');
  if (ring) ring.appendChild(createHealthScoreRing(health, 74, 8));
}

document.getElementById('rpt-brand-edit')?.addEventListener('click', () => {
  document.getElementById('nav-btn-settings')?.click();
});

// Global Nav
document.getElementById('nav-btn-projects').addEventListener('click', () => {
  document.querySelectorAll('.global-nav .nav-icon').forEach(n => n.classList.remove('active'));
  document.getElementById('nav-btn-projects').classList.add('active');
  switchProjectView('view-home');
  loadClients();
  loadHome();
});
document.getElementById('nav-btn-settings').addEventListener('click', () => {
  document.querySelectorAll('.global-nav .nav-icon').forEach(n => n.classList.remove('active'));
  document.getElementById('nav-btn-settings').classList.add('active');
  switchProjectView('view-settings');
  integrationsPanel.load();
});
document.getElementById('nav-btn-config').addEventListener('click', () => {
  document.querySelectorAll('.global-nav .nav-icon').forEach(n => n.classList.remove('active'));
  document.getElementById('nav-btn-config').classList.add('active');
  switchProjectView('view-config');
  configPanel.load();
});
// Brand logomark → the public audit window (anonymous, URL-only front door).
document.getElementById('nav-btn-public').addEventListener('click', () => {
  document.querySelectorAll('.global-nav .nav-icon').forEach(n => n.classList.remove('active'));
  switchProjectView('view-public');
  // Re-sync the persistent "your latest audit" card each time it's opened.
  window.publicAudit?.refresh();
});

document.querySelectorAll('.project-nav .tab').forEach(tab => {
  tab.addEventListener('click', (e) => {
    switchProjectView(e.target.dataset.target);
  });
});

// Theme: live OS sync + a persistent toggle in the top-bar action zone.
initTheme();
// Theme toggle lives in the left rail so it's always reachable, even when the
// project top bar is hidden (home / settings / config / public views).
(() => {
  const rail = document.querySelector('.global-nav');
  const settingsBtn = document.getElementById('nav-btn-settings');
  const toggle = createThemeToggle();
  toggle.classList.add('rail-toggle');
  if (rail && settingsBtn) {
    settingsBtn.style.marginTop = '0';
    toggle.style.marginTop = 'auto';
    rail.insertBefore(toggle, settingsBtn);
  } else {
    document.getElementById('topbar-actions')?.appendChild(toggle);
  }
})();
// Start with the top bar hidden until a project is opened.
document.querySelector('.project-nav')?.classList.add('is-hidden');

// Floating audit analyst — scoped to the current crawl, streams from /api/ai/chat.
const aiAssistant = new AiAssistant({
  apiBase: API_BASE,
  getContext: () => ({
    crawlId: currentCrawlId,
    label: currentCrawlId ? (document.getElementById('active-project-name')?.textContent || '') : '',
  }),
  onOpenSettings: () => document.getElementById('nav-btn-settings')?.click(),
});
window.aiAssistant = aiAssistant; // reachable for verification

// Autonomous fix agent — one click fixes every affected page, streaming progress
// onto the button and asking clarifying questions through the assistant.
const fixAgent = new FixAgent({
  onOverview: (issue) => showFixOverview(issue),
  apiBase: API_BASE,
  assistant: aiAssistant,
  toast: (m, t) => toast.show(m, t),
  onDone: async () => {
    if (!currentCrawlId) return;
    const crawlId = currentCrawlId;
    loadDashboard(crawlId);
    // Refresh which issues are fixed so their rows show "Fixed", not "Fix".
    const fx = await fetchJson(`/fixes/${crawlId}`);
    if (fx && crawlId === currentCrawlId) {
      currentFixes = { byIssue: fx.by_issue || {}, list: fx.fixes || [] };
      renderIssuesHub();
    }
  },
});
window.fixAgent = fixAgent;

// Dashboard → jump to the full Issues hub.
document.getElementById('dash-view-all-issues')?.addEventListener('click', () => {
  switchProjectView('view-issues');
});

// Settings → link back to the client-centric home
document.getElementById('settings-link-clients')?.addEventListener('click', (e) => {
  e.preventDefault();
  document.querySelectorAll('.global-nav .nav-icon').forEach(n => n.classList.remove('active'));
  document.getElementById('nav-btn-projects').classList.add('active');
  switchProjectView('view-home');
  loadClients();
});

// Components Initialization
const detailDrawer = new Drawer('detail-drawer');

// SF-style Explorer: dimension tabs + faceted filters (owns its own DataGrid).
const explorer = new Explorer({
  railEl: document.getElementById('explorer-rail'),
  tabsEl: document.getElementById('explorer-tabs'),
  filterEl: document.getElementById('explorer-filters'),
  gridEl: document.getElementById('grid-container'),
  onRowClick: (row) => detailDrawer.open(row, currentCrawlData.urls || []),
});

// Persistent global crawl console — survives navigation, streams live discovery.
const crawlConsole = new CrawlConsole(API_BASE, {
  onView: (crawlId) => {
    if (crawlId == null) return;
    loadCrawlData(crawlId);
    switchProjectView('view-dashboard');
    loadHome();
  },
});

// When a crawl starts, hand off to the global console and drop the user on the
// client home (the console keeps tracking wherever they navigate).
window.crawlConsole = crawlConsole; // reachable for debugging/verification

// Configuration workspace (crawl profiles)
const configPanel = new ConfigPanel(document.getElementById('config-container'), API_BASE);

// Resources view — CSS/JS/media sub-resources + their status (loaded on tab open).
const resourcesView = new ResourcesView(document.getElementById('resources-container'), API_BASE);

// SERP mode — pixel-width measurement of the crawl's titles/descriptions.
const serpView = new SerpView(document.getElementById('serp-container'), API_BASE);
// Origin-level agentic readiness (components/agentic-view.js).
const agenticView = new AgenticView(document.getElementById('agentic-container'),
                                    { apiBase: API_BASE });
window.agenticView = agenticView;   // reachable for verification

// Integrations (Google/embeddings/spelling/auth/backlinks) — loaded with Settings.
const integrationsPanel = new IntegrationsPanel(
  document.getElementById('integrations-container'), API_BASE);

// Public audit window — anonymous URL-only deep audit. On completion it loads
// the results into the same dashboard/explorer/graph the connected app uses.
// Open a public/anonymous crawl in the same dashboard the connected app uses.
// Shared by a just-completed audit and by re-opening the persisted latest one.
function openPublicCrawl(crawlId, targetUrl) {
  let host = targetUrl;
  try { host = new URL(targetUrl).hostname.replace(/^www\./, ''); } catch { /* keep raw */ }
  // Keep what we already know (e.g. started_at) instead of replacing the entry.
  crawlsById[crawlId] = {
    ...(crawlsById[crawlId] || {}), id: crawlId, client_name: host, base_url: targetUrl, public: true,
  };
  loadCrawlData(crawlId);
  switchProjectView('view-dashboard');
  document.querySelectorAll('.global-nav .nav-icon, .global-nav .nav-brand')
    .forEach(n => n.classList.remove('active'));
  document.getElementById('nav-btn-projects')?.classList.add('active');
}

const publicAudit = new PublicAudit(
  document.getElementById('public-audit-container'),
  API_BASE,
  {
    onAuditStarted: (crawlId, targetUrl) => {
      // Give the dashboard a friendly name (public crawls are hidden from /api/crawls).
      let host = targetUrl;
      try { host = new URL(targetUrl).hostname.replace(/^www\./, ''); } catch { /* keep raw */ }
      crawlsById[crawlId] = {
        id: crawlId, client_name: host, base_url: targetUrl, public: true,
        started_at: new Date().toISOString(),
      };
      toast.show(`Audit of ${host} started. Follow it in the live panel.`, 'info');
      crawlConsole.start(crawlId, (id) => {
        onCrawlFinished();   // edition hook (see edition.js)
        openPublicCrawl(id, targetUrl);
        window.publicAudit?.refresh();   // update the persistent "latest audit" card
      });
    },
    // Re-open the persisted latest audit from the card in the public window.
    onOpenLatest: (crawlId, targetUrl) => openPublicCrawl(crawlId, targetUrl),
  }
);
window.publicAudit = publicAudit; // reachable for verification

function onCrawlStarted(crawlId) {
  crawlConsole.start(crawlId, () => onCrawlFinished());
  toast.show('Crawl started. Follow it in the live panel.', 'info');
  switchProjectView('view-home');
  loadClients();
}

const wizard = new Wizard(
  document.getElementById('wizard-container'),
  API_BASE,
  (crawlId) => {
    toast.show('Crawl complete. Your results are ready.', 'success');
    loadCrawlData(crawlId);
    switchProjectView('view-dashboard');
  },
  onCrawlStarted
);

// Client setup wizard (add / connect flow)
const clientWizard = new ClientWizard(
  document.getElementById('client-wizard-container'),
  API_BASE,
  {
    onDone: () => {
      switchProjectView('view-home');
      loadClients();
    },
    onRunAudit: async (client) => {
      switchProjectView('view-wizard');
      await wizard.openForClient(client.id);
    },
  }
);

function launchClientWizard(client = null) {
  switchProjectView('view-client-setup');
  clientWizard.open(client);
}

document.getElementById('btn-new-client')?.addEventListener('click', () => launchClientWizard(null));

// Load Clients (client-centric home)
async function loadClients() {
  const list = document.getElementById('clients-list');
  if (!list) return;
  try {
    const clients = await fetchJson('/clients');
    if (clients === null) {                       // backend offline - banner shown
      list.innerHTML = `<div class="card" style="text-align:center; padding: var(--space-4); color: var(--text-secondary);">
        Waiting for the local Scrawly engine…</div>`;
      return;
    }
    list.innerHTML = '';
    if (!clients.length) {
      list.innerHTML = `<div class="card" style="text-align:center; padding: var(--space-4);">
        <p style="margin-bottom: var(--space-2);">No clients yet.</p>
        <button class="btn btn-primary" id="clients-empty-add">+ Add your first client</button>
      </div>`;
      document.getElementById('clients-empty-add')?.addEventListener('click', () => launchClientWizard(null));
      return;
    }
    clients.forEach(c => {
      const card = document.createElement('div');
      card.className = 'card flex';
      card.style.cssText = 'justify-content: space-between; align-items: center;';
      // Every site can be audited; connecting WordPress only adds safe fixes.
      const badge = c.connected
        ? `<span class="badge badge-passed">WordPress connected</span>`
        : `<span class="badge badge-notice" title="Read-only audits. Connect WordPress to apply fixes.">URL only</span>`;
      card.innerHTML = `
        <div>
          <h3 style="margin-bottom:2px;">${esc(c.name)} ${badge}</h3>
          <p style="margin:0; color: var(--text-secondary);">${esc(c.base_url || '')}</p>
        </div>
        <div class="flex gap-2" style="align-items:center;">
          <button class="btn btn-link btn-remove" title="Remove client" aria-label="Remove ${esc(c.name)}">✕</button>
          <button class="btn btn-secondary btn-setup">${c.connected ? 'Manage' : 'Set up'}</button>
          <button class="btn btn-primary btn-audit">Run Audit</button>
        </div>`;
      card.querySelector('.btn-setup').addEventListener('click', () => launchClientWizard(c));
      card.querySelector('.btn-audit').addEventListener('click', async () => {
        switchProjectView('view-wizard');
        await wizard.openForClient(c.id);
      });
      card.querySelector('.btn-remove').addEventListener('click', async () => {
        if (!confirm(`Remove "${c.name}" and all its audits? This cannot be undone.`)) return;
        try {
          const r = await fetch(`${API_BASE}/clients/${c.id}`, { method: 'DELETE' });
          if (r.ok) { toast.show(`Removed ${c.name}.`, 'success'); loadClients(); loadHome(); }
          else { toast.show('Could not remove client.', 'error'); }
        } catch (e) { toast.show('Network error.', 'error'); }
      });
      list.appendChild(card);
    });
  } catch (e) { console.error('loadClients', e); }
}

// Load Home Projects (Crawls)
async function loadHome() {
  try {
    const crawls = await fetchJson('/crawls');
    const list = document.getElementById('projects-list');
    if (!list) return;
    if (crawls === null) { return; }              // backend offline - banner shown
    list.innerHTML = '';

    if (crawls.length === 0) {
      list.innerHTML = `<div class="card" style="text-align: center; padding: var(--space-5);">No crawls yet. Start a new one!</div>`;
      return;
    }
    
    crawls.forEach(c => {
      crawlsById[c.id] = c;
      const card = document.createElement('div');
      card.className = 'card flex';
      card.style.justifyContent = 'space-between';
      card.style.alignItems = 'center';

      const date = _fmtDate(c.started_at);
      card.innerHTML = `
        <div>
          <h3>${esc(c.client_name || 'Unknown')} <span style="color: var(--text-secondary); font-weight: 400;">· Audit #${c.id}</span></h3>
          <p style="margin: 0; color: var(--text-secondary);">${esc(c.base_url || '')} • ${esc(date)} • ${esc(c.url_count)} pages</p>
        </div>
        <div class="flex gap-1" style="align-items:center;">
          <button class="btn btn-secondary js-open">Open Project</button>
          <button class="btn btn-ghost js-delete" title="Delete this audit and all its data"
                  aria-label="Delete audit ${c.id}">Delete</button>
        </div>
      `;
      card.querySelector('.js-open').addEventListener('click', () => {
        loadCrawlData(c.id);
        switchProjectView('view-dashboard');
      });
      card.querySelector('.js-delete').addEventListener('click', () =>
        deleteAudit(c, card));
      list.appendChild(card);
    });
  } catch (e) {
    console.error(e);
  }
}

/**
 * Delete one audit and everything it produced.
 *
 * Destructive and irreversible, so it asks for a deliberate confirmation rather
 * than a reflexive one — the dialog states exactly what will be destroyed, and
 * the button is a quiet ghost so it is never the easy click next to "Open".
 */
async function deleteAudit(crawl, card) {
  const label = `the ${crawl.client_name || ''} audit from ${_fmtDate(crawl.started_at) || 'this date'}`.replace('the  audit', 'this audit');
  const ok = window.confirm(
    `Delete ${label}?\n\n` +
    `${crawl.url_count || 0} crawled URLs, along with this audit's findings, ` +
    `resources and applied-fix history, will be permanently removed.\n\n` +
    `The site itself and its other audits are not affected. This cannot be undone.`);
  if (!ok) return;

  const btn = card.querySelector('.js-delete');
  btn.disabled = true;
  btn.textContent = 'Deleting…';
  try {
    const res = await fetch(`${API_BASE}/crawls/${crawl.id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const r = data.removed || {};
    card.remove();
    delete crawlsById[crawl.id];
    // If the open project was the one deleted, leave it — the views would
    // otherwise keep rendering data that no longer exists.
    if (currentCrawlId === crawl.id) {
      currentCrawlId = null;
      currentCrawlData = { issues: [], urls: [] };
      switchProjectView('view-home');
    }
    toast.show(
      `Deleted ${label}: ${r.urls || 0} pages and ${r.issues || 0} findings removed.`,
      'success');
    loadHome();
  } catch (e) {
    btn.disabled = false;
    btn.textContent = 'Delete';
    console.warn('[scrawly] delete failed:', e);
    toast.show('Could not delete this audit. Please try again.', 'error');
  }
}

// Load Full Crawl Data for Dashboard & Explorer
// Each load gets a token; a slower, older load that finishes after the user has
// already opened another project must not paint its data over the new one.
let _loadSeq = 0;
async function loadCrawlData(crawlId) {
  const seq = ++_loadSeq;
  const stale = () => seq !== _loadSeq;
  currentCrawlId = crawlId;
  currentCrawlData = { issues: [], urls: [] };
  const known = crawlsById[crawlId];
  document.getElementById('active-project-name').textContent =
    `Loading ${(known && known.client_name) || 'audit'}...`;

  try {
    const issues = await fetchJson(`/issues/${crawlId}`) || [];
    if (stale()) return;
    currentCrawlData.issues = issues;

    // Resolve the owning client so the Fix agent only offers auto-fix on
    // connected WordPress sites (the button is hidden otherwise). The crawl
    // index may not have this crawl yet (opened right after it was created),
    // so refresh it once when needed.
    let meta = crawlsById[crawlId];
    if (!meta || (meta.client_id == null && !meta.public)) {
      await loadHome();
      if (stale()) return;
      meta = crawlsById[crawlId] || meta;
    }
    currentClient = (meta && meta.client_id != null)
      ? await fetchJson(`/clients/${meta.client_id}`) : null;
    if (stale()) return;
    currentCanFix = isWordPressClient(currentClient);

    // Fixes the agent has already applied — drives the persistent "Fixed" chip.
    const fx = await fetchJson(`/fixes/${crawlId}`);
    if (stale()) return;
    currentFixes = fx ? { byIssue: fx.by_issue || {}, list: fx.fixes || [] } : { byIssue: {}, list: [] };

    populateDashboard(crawlId, issues);
    renderIssuesHub();
    aiAssistant.refreshContext();   // keep the assistant's "Analyzing: …" fresh

    loadDashboard(crawlId);
    fetchUrls(crawlId, seq);

  } catch(e) {
    console.error("Error loading crawl data", e);
  }
}

async function fetchUrls(crawlId, seq = _loadSeq) {
  const urls = await fetchJson(`/urls/${crawlId}`);
  if (seq !== _loadSeq) return;
  if (urls) {
    currentCrawlData.urls = urls || [];
    explorer.setRows(urls || []);
  }
}

// Severity + status-code → CSS-var colours (theme-reactive via the tokens).
const SEV_COLORS = {
  Critical: 'var(--color-critical)',
  High: 'var(--color-warning)',
  Medium: 'var(--chart-3)',
  Low: 'var(--chart-1)',
  Info: 'var(--text-tertiary)',
};
const STATUS_COLORS = {
  '2xx': 'var(--color-passed)',
  '3xx': 'var(--chart-3)',
  '4xx': 'var(--color-warning)',
  '5xx': 'var(--color-critical)',
  other: 'var(--text-tertiary)',
};
function healthGrade(score) {
  if (score >= 90) return 'Excellent';
  if (score >= 75) return 'Good';
  if (score >= 50) return 'Needs work';
  if (score >= 25) return 'Poor';
  return 'Critical';
}

// Fetch the server-side aggregation and render the ring, stat tiles and charts.
async function loadDashboard(crawlId) {
  const d = await fetchJson(`/dashboard/${crawlId}`);
  if (!d) return;
  // The server knows the real start time even when the UI's crawl entry doesn't
  // (e.g. a public audit re-opened from the latest-audit card).
  if (d.started_at) {
    if (crawlsById[crawlId]) crawlsById[crawlId].started_at = d.started_at;
    const dateEl = document.getElementById('dash-date');
    if (dateEl) dateEl.textContent = _fmtDate(d.started_at);
  }
  const t = d.totals || {};
  const sev = d.severity || {};

  // Health ring + grade label
  const ring = document.getElementById('health-score-container');
  ring.innerHTML = '';
  ring.appendChild(createHealthScoreRing(d.health_score ?? 0, 96, 9));
  const gradeEl = document.getElementById('dash-health-label');
  if (gradeEl) gradeEl.textContent = healthGrade(d.health_score ?? 0);

  // Stat tiles
  const tiles = document.getElementById('dash-tiles');
  tiles.innerHTML = '';
  const pct = d.indexable_pct ?? 0;
  tiles.appendChild(statTile({ label: 'Pages crawled', value: t.urls ?? 0 }));
  tiles.appendChild(statTile({
    label: 'Indexable', value: `${pct}%`,
    sub: `${t.indexable ?? 0} of ${t.urls ?? 0} pages`,
    tone: pct >= 80 ? 'passed' : pct >= 50 ? 'warning' : 'critical',
  }));
  tiles.appendChild(statTile({
    label: 'Broken (4xx / 5xx)', value: t.broken ?? 0,
    sub: `avg depth ${t.avg_depth ?? 0}`,
    tone: (t.broken ?? 0) > 0 ? 'critical' : 'passed',
  }));
  tiles.appendChild(statTile({
    label: 'Total issues', value: t.issues ?? 0,
    sub: `${sev.Critical ?? 0} critical · ${sev.High ?? 0} high`,
    tone: (sev.Critical ?? 0) > 0 ? 'critical' : (sev.High ?? 0) > 0 ? 'warning' : 'passed',
  }));

  // Severity distribution (stacked bar + legend)
  const sevSegs = ['Critical', 'High', 'Medium', 'Low', 'Info']
    .map(k => ({ label: k, value: sev[k] || 0, color: SEV_COLORS[k] }));
  stackedBar(document.getElementById('chart-severity'), { segments: sevSegs });
  const sevTotal = document.getElementById('chart-severity-total');
  if (sevTotal) sevTotal.textContent = `${t.issues ?? 0} issue${(t.issues ?? 0) === 1 ? '' : 's'}`;

  // Response-code donut
  const sc = d.status_classes || {};
  donut(document.getElementById('chart-status'), {
    data: Object.keys(STATUS_COLORS).map(k => ({ label: k, value: sc[k] || 0, color: STATUS_COLORS[k] })),
    centerValue: t.urls ?? 0, centerLabel: 'URLs',
  });

  // Issues by category (horizontal bars)
  bars(document.getElementById('chart-categories'), {
    data: (d.issue_categories || []).map(c => ({ label: c.category, value: c.count })),
    colorVar: 'var(--chart-1)',
  });

  // Crawl depth histogram
  histogram(document.getElementById('chart-depth'), {
    data: (d.depth_histogram || []).map(h => ({ label: String(h.depth), value: h.count })),
    colorVar: 'var(--accent)',
  });

  // Segments (horizontal bars, palette-coloured)
  bars(document.getElementById('chart-segments'), {
    data: (d.segments || []).map(s => ({ label: s.name, value: s.count })),
  });

  // Indexability donut (indexable vs non-indexable)
  donut(document.getElementById('chart-indexability'), {
    data: [
      { label: 'Indexable', value: t.indexable ?? 0, color: 'var(--color-passed)' },
      { label: 'Non-indexable', value: t.non_indexable ?? 0, color: 'var(--color-warning)' },
    ],
    centerValue: `${pct}%`, centerLabel: 'indexable',
  });

  // Fixability by tier (how issues can be resolved)
  const tiers = d.tiers || {};
  const TIER_LABELS = { AUTO: 'Auto-fixable', REVIEW: 'Needs review', FLAG: 'Manual fix' };
  const TIER_COLORS = { AUTO: 'var(--color-passed)', REVIEW: 'var(--chart-3)', FLAG: 'var(--color-warning)' };
  bars(document.getElementById('chart-fixability'), {
    data: ['AUTO', 'REVIEW', 'FLAG']
      .map(k => ({ label: TIER_LABELS[k], value: tiers[k] || 0, color: TIER_COLORS[k] }))
      .filter(x => x.value > 0),
  });

  // Content & performance mini-stats
  const c = d.content || {}; const cwv = d.cwv || {};
  const mini = document.getElementById('dash-mini');
  if (mini) {
    const cell = (label, value, tone) =>
      `<div class="dash-mini-cell"><div class="dash-mini-v${tone ? ` tone-${tone}` : ''}">${value}</div><div class="dash-mini-l">${label}</div></div>`;
    const lcpTone = cwv.avg_lcp_s == null ? '' : cwv.avg_lcp_s <= 2.5 ? 'passed' : cwv.avg_lcp_s <= 4 ? 'warning' : 'critical';
    const clsTone = cwv.avg_cls == null ? '' : cwv.avg_cls <= 0.1 ? 'passed' : cwv.avg_cls <= 0.25 ? 'warning' : 'critical';
    mini.innerHTML =
      cell('Avg words / page', c.avg_words ?? 0) +
      cell('Thin pages (&lt;200w)', c.thin_pages ?? 0, (c.thin_pages ?? 0) > 0 ? 'warning' : '') +
      cell('Avg readability', c.avg_readability == null ? ' - ' : c.avg_readability) +
      cell('Redirects (3xx)', t.redirects ?? 0) +
      cell('Avg LCP', cwv.avg_lcp_s == null ? ' - ' : `${cwv.avg_lcp_s}s`, lcpTone) +
      cell('Avg CLS', cwv.avg_cls == null ? ' - ' : cwv.avg_cls, clsTone);
  }

  renderFixesWidget(crawlId);
}

// "Fixed by agent" dashboard insight — appears only once fixes have been applied.
async function renderFixesWidget(crawlId) {
  const box = document.getElementById('dash-fixes');
  if (!box) return;
  const fx = await fetchJson(`/fixes/${crawlId}`);
  const list = (fx && fx.fixes || []).filter(f => !f.reverted);
  const count = fx ? (fx.count || 0) : 0;
  if (!count) { box.innerHTML = ''; return; }
  const path = (u) => { try { return new URL(u).pathname || '/'; } catch { return u || ''; } };
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const rows = list.slice(0, 6).map(f =>
    `<div class="fixw-row"><span class="fixw-field">${esc(f.field || 'meta')}</span>`
    + `<span class="fixw-url mono">${esc(path(f.url))}</span>`
    + `<span class="fixw-val">${esc((f.value || '').slice(0, 48))}</span></div>`).join('');
  box.innerHTML = `
    <div class="card fixw">
      <div class="fixw-head">
        <div class="fixw-icon">✓</div>
        <div><div class="fixw-title">${count} fix${count !== 1 ? 'es' : ''} applied by the agent</div>
        <div class="fixw-sub">Written to WordPress - each with a rollback snapshot.</div></div>
      </div>
      <div class="fixw-list">${rows}${list.length > 6 ? `<div class="fixw-more">+${list.length - 6} more</div>` : ''}</div>
    </div>`;
}

// Advanced site-architecture visualization (components/site-graph.js).
const siteGraph = new SiteGraph(document.getElementById('site-graph'), {
  onNodeClick: (addr) => {
    const row = (currentCrawlData.urls || []).find(u => u.address === addr);
    if (row) detailDrawer.open(row, currentCrawlData.urls || []);
  },
});
let _sgCrawlId = null;
window.siteGraph = siteGraph; // reachable for verification

async function renderSiteArchitecture(crawlId) {
  if (!crawlId) return;
  if (_sgCrawlId === crawlId && siteGraph.data.nodes.length) { siteGraph.render(); return; }
  try {
    const graph = await (await fetch(`${API_BASE}/graph/${crawlId}`)).json();
    _sgCrawlId = crawlId;
    siteGraph.setData(graph);
  } catch (e) { console.error('graph load failed', e); }
}

// Locale date for a crawl timestamp; '' rather than "Invalid Date" when unknown.
// Server timestamps are UTC without a zone suffix, so mark them as UTC.
function _fmtDate(value) {
  if (!value) return '';
  const iso = /[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`;
  const dt = new Date(iso);
  return Number.isNaN(dt.getTime()) ? '' : dt.toLocaleString();
}

function populateDashboard(crawlId, issues) {
  const c = crawlsById[crawlId];
  const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  const when = _fmtDate(c && c.started_at);
  setText('active-project-name', c ? `${c.client_name}${when ? ` · ${when}` : ''}` : 'Audit');
  setText('dash-site-name', c ? c.client_name : 'Audit');
  setText('dash-date', _fmtDate(c && c.started_at));

  // Render Top 5 Issues
  const topIssuesContainer = document.getElementById('dash-top-issues');
  topIssuesContainer.innerHTML = '';
  
  if (issues.length === 0) {
    topIssuesContainer.innerHTML = `<div class="card"><p style="margin:0;">No issues found. Awesome!</p></div>`;
  } else {
    const sorted = [...issues].sort((a, b) => (SEV_RANK[b.severity] || 0) - (SEV_RANK[a.severity] || 0));
    sorted.slice(0, 5).forEach(issue => {
      const card = createIssueCard(issue, currentCanFix, currentFixes.byIssue[issue.id] || 0);
      wireIssueCardActions(card, issue);
      topIssuesContainer.appendChild(card);
    });
  }
}

const SEV_RANK = { Critical: 5, High: 4, Medium: 3, Low: 2, Info: 1 };

// Switch to the explorer, filtered to the pages an issue affects.
function openIssuePages(issue) {
  const ids = issue.affected_url_ids || [];
  if (ids.length === 0) {
    toast.show('This issue affects the whole site, not specific pages.', 'info');
    return;
  }
  switchProjectView('view-explorer');
  explorer.focusOn(ids, issue.title || 'this issue');
}

function wireIssueCardActions(card, issue) {
  const viewBtn = card.querySelector('.view-issue-btn');
  if (viewBtn) viewBtn.addEventListener('click', () => openIssuePages(issue));
  const promptBtn = card.querySelector('.copy-prompt-btn');
  if (promptBtn) promptBtn.addEventListener('click', () => copyFixPrompt(issue, promptBtn));
  const fixBtn = card.querySelector('.fix-issue-btn');
  if (!fixBtn) return;
  if (fixBtn.classList.contains('fx-done')) {
    // Already fixed (from a previous run) — click shows what was fixed.
    fixBtn.addEventListener('click', () => showFixOverview(issue));
  } else {
    fixBtn.addEventListener('click', () => fixAgent.run(issue, fixBtn));
  }
}

// Copy a stack-aware fix prompt for the user's own coding agent (MCP/CLI/SSH).
// Rendered server-side against the crawl's detected stack, so it names the file
// to edit on THAT platform rather than giving generic advice.
async function copyFixPrompt(issue, btn) {
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Building…';
  try {
    const res = await fetch(`${API_BASE}/prompt/${currentCrawlId}/${issue.id}`);
    if (!res.ok) throw new Error(`prompt request failed: ${res.status}`);
    const data = await res.json();
    // Only the clipboard write is allowed to fail here — the prompt is already
    // in hand, so a blocked clipboard must not cost a second round-trip.
    try {
      await navigator.clipboard.writeText(data.text);
      btn.textContent = 'Copied ✓';
      btn.classList.add('is-copied');
      aiAssistant.say(
        `**Fix prompt copied** - ${issue.title}\n\n` +
        `Tailored for **${data.stack_label}**, covering ${data.affected} affected ` +
        `page${data.affected !== 1 ? 's' : ''}. Paste it into your coding agent ` +
        `(any AI coding assistant, or over SSH). It includes ` +
        `acceptance criteria and a verification command so the agent can prove the fix landed.`);
    } catch {
      // Clipboard needs a user gesture and a permission grant; when the browser
      // refuses, show the prompt inline so the user can still select and copy it.
      btn.textContent = 'Shown in chat';
      aiAssistant.say(
        `**Fix prompt - ${issue.title}** (${data.stack_label}, ${data.affected} ` +
        `page${data.affected !== 1 ? 's' : ''}) - your browser blocked the ` +
        `clipboard, so here it is to copy manually:\n\n\`\`\`\n${data.text}\n\`\`\``);
    }
  } catch (err) {
    btn.textContent = 'Failed';
    aiAssistant.say(
      `Could not build a fix prompt for **${issue.title}** (${err.message}).`);
  } finally {
    setTimeout(() => {
      btn.disabled = false;
      btn.textContent = original;
      btn.classList.remove('is-copied');
    }, 2200);
  }
}

// Overview of what the agent fixed for an issue (persisted fixes), in the chat,
// with the option to undo: every fix restores its saved before-value.
async function showFixOverview(issue) {
  const mine = (currentFixes.list || []).filter(f => f.issue_id === issue.id && !f.reverted);
  if (!mine.length) { aiAssistant.say(`No recorded fixes for **${issue.title}**.`); return; }
  const path = (u) => { try { return new URL(u).pathname || '/'; } catch { return u || ''; } };
  const n = mine.length;
  const lines = mine.slice(0, 20).map(f => `• \`${path(f.url)}\` → ${f.value ?? ''}`).join('\n');
  aiAssistant.say(
    `**Fixed by agent - ${issue.title}** · ${n} page${n !== 1 ? 's' : ''} ` +
    `written to WordPress (each with a rollback snapshot):\n${lines}`);
  const choice = await aiAssistant.ask(
    `Undo ${n === 1 ? 'this change' : `these ${n} changes`} and restore the previous value on WordPress?`,
    [{ label: n === 1 ? 'Undo it' : `Undo all ${n}`, value: 'undo' }, { label: 'Keep', value: 'keep' }]);
  if (choice !== 'undo') return;
  let undone = 0, failed = 0;
  for (const f of mine) {
    try {
      const r = await fetch(`${API_BASE}/fix/revert`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fix_id: f.id }),
      });
      const d = await r.json().catch(() => ({}));
      if (r.ok && (d.reverted || d.status === 'already_reverted')) undone += 1; else failed += 1;
    } catch { failed += 1; }
  }
  aiAssistant.say(`↩︎ Restored the previous value on **${undone} page${undone !== 1 ? 's' : ''}**` +
    `${failed ? `. ${failed} couldn't be undone; check the WordPress connection and try again.` : '.'}`);
  const crawlId = currentCrawlId;
  const fx = crawlId ? await fetchJson(`/fixes/${crawlId}`) : null;
  if (fx && crawlId === currentCrawlId) {
    currentFixes = { byIssue: fx.by_issue || {}, list: fx.fixes || [] };
    renderIssuesHub();
    loadDashboard(crawlId);
  }
}

// Issues & Audits — triage-first view (components/issues-view.js).
// The old hub rendered every finding as an identical card with the deciding
// number (pages affected) as grey text at the bottom; this one leads with
// severity and impact so "what do I fix first?" is answerable at a glance.
const issuesView = new IssuesView(document.getElementById('issues-hub-container'), {
  canFix: () => currentCanFix,
  fixedCount: (issue) => currentFixes.byIssue[issue.id] || 0,
  onViewPages: (issue) => issue && openIssuePages(issue),
  onCopyPrompt: (issue, btn) => issue && copyFixPrompt(issue, btn),
  onFix: (issue, btn) => issue && fixAgent.run(issue, btn),
  onFixOverview: (issue) => issue && showFixOverview(issue),
});
window.issuesView = issuesView;   // reachable for verification

function renderIssuesHub() {
  issuesView.setIssues((currentCrawlData && currentCrawlData.issues) || []);
}

// Reports: open the report + save it as a PDF. The desktop app runs in a sandboxed
// webview where window.open() and downloads do nothing, so we call a native bridge
// (open in the system browser / save via a file dialog). In a plain browser we fetch
// the report through the API and open or download it as a blob.
function _reportFilename() {
  const c = crawlsById[currentCrawlId];
  let host = (c && c.base_url) || '';
  try { host = new URL(host).hostname.replace(/^www\./, ''); } catch { /* keep raw */ }
  return `scrawly-report-${host || currentCrawlId}.pdf`;
}

async function openReport() {
  if (!currentCrawlId) { toast.show('Please select a project first.', 'error'); return; }
  if (window.pywebview?.api?.open_report) {
    const ok = await window.pywebview.api.open_report(currentCrawlId, ownerKey());
    if (!ok) toast.show('Could not open the report. Please try again.', 'error');
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/report/${currentCrawlId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const url = URL.createObjectURL(new Blob([await res.text()], { type: 'text/html' }));
    window.open(url, '_blank');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch { toast.show('Could not open the report. Please try again.', 'error'); }
}

let _pdfBusy = false;
async function saveReportPdf() {
  if (!currentCrawlId) { toast.show('Please select a project first.', 'error'); return; }
  if (_pdfBusy) return;   // one save dialog at a time
  _pdfBusy = true;
  toast.show('Preparing your PDF…', 'info');
  try {
    let outcome;
    if (window.pywebview?.api?.save_pdf) {
      const path = await window.pywebview.api.save_pdf(currentCrawlId, ownerKey(), _reportFilename());
      outcome = path ? 'saved' : (path === false ? 'failed' : 'cancelled');
    } else {
      outcome = await saveDownload(`${API_BASE}/report/${currentCrawlId}/pdf`, _reportFilename());
    }
    if (outcome === 'saved') toast.show('Report saved to your computer.', 'success');
    else if (outcome === 'failed') toast.show('Could not create the PDF. Please try again.', 'error');
  } finally {
    _pdfBusy = false;
  }
}

document.getElementById('btn-open-report')?.addEventListener('click', openReport);
document.getElementById('btn-export-pdf')?.addEventListener('click', saveReportPdf);

// Re-crawl
document.getElementById('dash-btn-recrawl')?.addEventListener('click', async () => {
  if (!currentCrawlId) return;
  const known = crawlsById[currentCrawlId];
  // A public (quick) audit has no client: re-run it through the audit window.
  if (known && known.public) {
    switchProjectView('view-public');
    publicAudit.prefill(known.base_url);
    return;
  }
  try {
    const crawls = await fetchJson('/crawls') || [];
    const current = crawls.find(c => c.id === currentCrawlId);
    if (!current) { toast.show('Could not find this audit to run it again.', 'error'); return; }
    switchProjectView('view-wizard');
    wizard.startCrawl(current.client_id);
  } catch {
    toast.show('Could not start the crawl again. Please try again.', 'error');
  }
});

// Settings: crawl defaults
async function loadSettings() {
  try {
    const res = await fetch(`${API_BASE}/settings`);
    if (!res.ok) return;
    const s = await res.json();
    const set = (id, val) => { const el = document.getElementById(id); if (el && val != null) el.value = val; };
    // AI provider
    set('set-ai-provider', s.ai_provider || 'anthropic');
    set('set-ai-kind', s.ai_kind || 'openai');
    set('set-ai-base', s.ai_base_url);
    set('set-ai-model', s.ai_model);
    const hint = document.getElementById('set-ai-key-hint');
    if (hint) hint.textContent = s.ai_api_key_set ? '· a key is saved' : '· not set';
    // Report branding (white-label)
    set('set-brand-name', s.report_brand_name);
    set('set-brand-color', s.report_brand_color || '#6366f1');
    set('set-brand-logo', s.report_brand_logo);
    set('set-brand-contact', s.report_brand_contact);
  } catch (e) { console.error(e); }
}

// AI provider presets → autofill kind/base/model on provider change.
const AI_PRESETS = {
  anthropic: { kind: 'anthropic', base: 'https://api.anthropic.com', model: 'claude-sonnet-5' },
  openai: { kind: 'openai', base: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  deepseek: { kind: 'openai', base: 'https://api.deepseek.com', model: 'deepseek-chat' },
  openrouter: { kind: 'openai', base: 'https://openrouter.ai/api/v1', model: 'openai/gpt-4o-mini' },
  glm: { kind: 'openai', base: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash' },
  nara: { kind: 'openai', base: '', model: '' },
  opencode: { kind: 'openai', base: '', model: '' },
  custom: { kind: 'openai', base: '', model: '' },
};
document.getElementById('set-ai-provider')?.addEventListener('change', (e) => {
  const p = AI_PRESETS[e.target.value];
  if (!p) return;
  document.getElementById('set-ai-kind').value = p.kind;
  if (p.base) document.getElementById('set-ai-base').value = p.base;
  if (p.model) document.getElementById('set-ai-model').value = p.model;
});

function aiPayload() {
  return {
    ai_provider: document.getElementById('set-ai-provider')?.value || '',
    ai_kind: document.getElementById('set-ai-kind')?.value || 'openai',
    ai_base_url: document.getElementById('set-ai-base')?.value.trim() || '',
    ai_model: document.getElementById('set-ai-model')?.value.trim() || '',
    ai_api_key: document.getElementById('set-ai-key')?.value || '',  // blank = keep saved
  };
}

document.getElementById('settings-btn-ai-save')?.addEventListener('click', async () => {
  try {
    const res = await fetch(`${API_BASE}/settings`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(aiPayload()),
    });
    if (res.ok) { toast.show('AI provider saved.', 'success'); document.getElementById('set-ai-key').value = ''; loadSettings(); }
    else { toast.show('Failed to save AI provider.', 'error'); }
  } catch (e) { toast.show('Network error.', 'error'); }
});

document.getElementById('settings-btn-ai-test')?.addEventListener('click', async () => {
  const st = document.getElementById('ai-status');
  st.textContent = 'Saving + testing…';
  await fetch(`${API_BASE}/settings`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(aiPayload()),
  }).catch(() => {});
  document.getElementById('set-ai-key').value = '';
  try {
    const d = await (await fetch(`${API_BASE}/ai/test`, { method: 'POST' })).json();
    st.textContent = d.ok ? `✓ AI connected - ${d.model} replied "${d.reply}"` : `✗ ${d.detail || 'test failed'}`;
    st.style.color = d.ok ? 'var(--color-passed)' : 'var(--color-critical)';
    toast.show(d.ok ? 'AI connected!' : 'AI test failed.', d.ok ? 'success' : 'error');
  } catch (e) { st.textContent = '✗ Network error.'; }
});

// Report branding (white-label) — saved to global settings, applied to reports.
document.getElementById('settings-btn-brand-save')?.addEventListener('click', async () => {
  const val = (id) => document.getElementById(id)?.value.trim() || '';
  const payload = {
    report_brand_name: val('set-brand-name'),
    report_brand_color: val('set-brand-color') || '#6366f1',
    report_brand_logo: val('set-brand-logo'),
    report_brand_contact: val('set-brand-contact'),
  };
  const st = document.getElementById('brand-status');
  try {
    const res = await fetch(`${API_BASE}/settings`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    if (st) { st.textContent = res.ok ? '✓ Branding saved.' : '✗ Failed to save.'; st.style.color = res.ok ? 'var(--color-passed)' : 'var(--color-critical)'; }
    toast.show(res.ok ? 'Report branding saved.' : 'Failed to save branding.', res.ok ? 'success' : 'error');
  } catch (e) { toast.show('Network error saving branding.', 'error'); }
});

// Settings → Configuration shortcuts.
const goConfig = (e) => { if (e) e.preventDefault(); document.getElementById('nav-btn-config')?.click(); };
document.getElementById('settings-link-config')?.addEventListener('click', goConfig);
document.getElementById('settings-open-config')?.addEventListener('click', goConfig);

// Compare View
document.querySelector('.project-nav .tab[data-target="view-compare"]')?.addEventListener('click', async () => {
  try {
    const all = await fetchJson('/crawls') || [];
    const selLatest = document.getElementById('compare-sel-latest');
    const selPrevious = document.getElementById('compare-sel-previous');
    if (!selLatest || !selPrevious) return;
    // Comparing only makes sense for the same site: list the open site's audits
    // (all audits when no site is open), labelled with name and date.
    const open = crawlsById[currentCrawlId];
    const crawls = open && open.client_id != null
      ? all.filter(c => c.client_id === open.client_id) : all;
    const opts = crawls.map(c =>
      `<option value="${esc(c.id)}">${esc(c.client_name || c.base_url || 'Audit')} · ${esc(_fmtDate(c.started_at))}</option>`
    ).join('');
    selLatest.innerHTML = opts;
    selPrevious.innerHTML = opts;
    if (crawls.length > 1) selPrevious.selectedIndex = 1;
    if (crawls.length < 2) {
      document.getElementById('compare-results').innerHTML =
        '<div class="cmp-empty">Run this site’s audit at least twice to compare changes over time.</div>';
    }
  } catch (e) {
    console.error(e);
  }
});

document.getElementById('compare-btn-run')?.addEventListener('click', async () => {
  const latestId = document.getElementById('compare-sel-latest').value;
  const previousId = document.getElementById('compare-sel-previous').value;
  if (!latestId || !previousId) {
    toast.show('Please select two crawls to compare', 'error');
    return;
  }
  const container = document.getElementById('compare-results');
  container.innerHTML = '<div class="cmp-empty">Loading comparison…</div>';
  try {
    const res = await fetch(`${API_BASE}/compare?crawl1=${previousId}&crawl2=${latestId}`);
    if (!res.ok) throw new Error('Compare failed');
    const diff = await res.json();

    const regs = diff.regressions || [];
    const u = diff.urls || { new: [], missing: [], changed: [], summary: {} };
    const s = diff.summary || {};
    const esc = (x) => String(x ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    const path = (x) => { try { return new URL(x).pathname || '/'; } catch { return x; } };
    const val = (v) => v === null || v === undefined || v === '' ? ' - ' : String(v);
    const nameOf = (id) => {
      const c = crawlsById[id];
      return c ? `${c.client_name || 'Audit'} · ${_fmtDate(c.started_at)}` : 'Audit';
    };

    const netUrls = (s.latest_urls ?? 0) - (s.previous_urls ?? 0);
    const netStr = netUrls === 0 ? '±0' : (netUrls > 0 ? `+${netUrls}` : `${netUrls}`);

    // Summary tiles (reuse the dashboard stat-tile styling).
    const tile = (label, value, tone, sub) =>
      `<div class="stat-tile${tone ? ` tone-${tone}` : ''}">
        <div class="stat-tile-label">${label}</div>
        <div class="stat-tile-value">${value}</div>
        ${sub ? `<div class="stat-tile-sub">${sub}</div>` : ''}
      </div>`;

    const section = (title, note, body) => body
      ? `<div class="cmp-section"><div class="cmp-section-head"><h3>${title}</h3>${note ? `<span class="cmp-section-note">${note}</span>` : ''}</div>${body}</div>`
      : '';

    container.innerHTML = `
      <div class="cmp-summary-head card">
        <div class="cmp-crawl"><span class="cmp-crawl-tag">Baseline</span><span class="cmp-crawl-name">${esc(nameOf(previousId))}</span></div>
        <div class="cmp-summary-arrow">→</div>
        <div class="cmp-crawl"><span class="cmp-crawl-tag">Compared</span><span class="cmp-crawl-name">${esc(nameOf(latestId))}</span></div>
        <div class="cmp-net ${netUrls > 0 ? 'up' : netUrls < 0 ? 'down' : ''}">
          <span class="cmp-net-val">${netStr}</span><span class="cmp-net-lbl">URLs</span>
        </div>
      </div>

      <div class="cmp-summary">
        ${tile('Resolved', s.resolved ?? 0, (s.resolved ?? 0) > 0 ? 'passed' : '', 'issues fixed')}
        ${tile('New issues', s.new ?? 0, (s.new ?? 0) > 0 ? 'warning' : '', 'appeared')}
        ${tile('Regressions', regs.length, regs.length > 0 ? 'critical' : '', 'new Critical / High')}
        ${tile('New URLs', u.summary?.new ?? 0, '', 'added pages')}
        ${tile('Missing URLs', u.summary?.missing ?? 0, (u.summary?.missing ?? 0) > 0 ? 'warning' : '', 'removed pages')}
        ${tile('Changed URLs', u.summary?.changed ?? 0, '', 'field deltas')}
      </div>

      ${section('Regressions', 'new Critical / High issues', regs.length ? `<div class="cmp-list">${regs.slice(0, 40).map(r => `<div class="cmp-row">
        <span class="badge badge-${r.severity === 'Critical' ? 'critical' : 'warning'}">${r.severity}</span>
        <span class="mono cmp-url">${esc(r.key)}</span></div>`).join('')}</div>` : '')}

      ${section('Missing pages', 'in baseline, gone from newer', u.missing?.length ? `<div class="cmp-list">${u.missing.slice(0, 40).map(r => `<div class="cmp-row">
        <span class="status-chip status-err">gone</span><span class="mono cmp-url" title="${esc(r.address)}">${esc(path(r.address))}</span></div>`).join('')}</div>` : '')}

      ${section('New pages', "didn't exist in the baseline", u.new?.length ? `<div class="cmp-list">${u.new.slice(0, 40).map(r => `<div class="cmp-row">
        <span class="status-chip status-2xx">new</span><span class="mono cmp-url" title="${esc(r.address)}">${esc(path(r.address))}</span>
        <span class="status-chip ${r.status >= 400 ? 'status-4xx' : r.status >= 300 ? 'status-3xx' : 'status-2xx'}">${r.status ?? ' - '}</span></div>`).join('')}</div>` : '')}

      ${section('Changed pages', '', u.changed?.length ? `<div class="cmp-list">${u.changed.slice(0, 40).map(r => `<div class="cmp-changed">
        <div class="mono cmp-url" title="${esc(r.address)}">${esc(path(r.address))}</div>
        ${r.changes.map(c => `<div class="cmp-delta">
          <span class="cmp-field">${esc(c.label)}</span>
          <span class="cmp-before">${esc(val(c.before))}</span>
          <span class="cmp-arrow">→</span>
          <span class="cmp-after">${esc(val(c.after))}</span>
        </div>`).join('')}
      </div>`).join('')}</div>` : '')}

      ${!regs.length && !u.new?.length && !u.missing?.length && !u.changed?.length
        ? '<div class="cmp-nochange">✓ No differences between these two crawls.</div>' : ''}
    `;
  } catch(e) {
    container.innerHTML = '<div class="cmp-empty">Error loading comparison.</div>';
    toast.show('Failed to compare crawls', 'error');
  }
});

// Exposed for verification/debugging
window.explorer = explorer;
window.loadCrawlData = loadCrawlData;

// Lightweight feedback / improvement-note modal. Scrawly is free and built for the
// SEO community; it improves from real user and expert input, so sending a note is
// one click from the account menu.
function openFeedback(prefillEmail = '') {
  document.querySelector('.fb-overlay')?.remove();
  const e2 = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const ov = document.createElement('div');
  ov.className = 'fb-overlay';
  ov.innerHTML = `
    <div class="fb-card" role="dialog" aria-modal="true" aria-label="Send feedback">
      <h2 class="fb-title">Send feedback</h2>
      <p class="fb-sub">Scrawly is free and built for the SEO community. Tell us what to
        improve, what broke, or what you'd love to see next.</p>
      <textarea class="fb-text" rows="6" placeholder="Your note, idea, or bug report…"></textarea>
      <label class="fb-field"><span>Your email (optional, so we can reply)</span>
        <input class="fb-email" type="email" value="${e2(prefillEmail)}" placeholder="you@example.com"></label>
      <div class="fb-msg" aria-live="polite"></div>
      <div class="fb-actions">
        <button class="fb-cancel" type="button">Cancel</button>
        <button class="fb-send" type="button">Send</button>
      </div>
    </div>`;
  document.body.appendChild(ov);
  const opener = document.activeElement;
  const onKey = (ev) => { if (ev.key === 'Escape') close(); };
  const close = () => {
    ov.remove();
    document.removeEventListener('keydown', onKey);
    if (opener && typeof opener.focus === 'function') opener.focus();
  };
  document.addEventListener('keydown', onKey);
  ov.addEventListener('click', (ev) => { if (ev.target === ov) close(); });
  ov.querySelector('.fb-cancel').addEventListener('click', close);
  const ta = ov.querySelector('.fb-text');
  setTimeout(() => ta.focus(), 30);
  const fallback = (msg) => {
    const box = ov.querySelector('.fb-msg');
    box.className = 'fb-msg fb-err';
    box.innerHTML = `${(msg || 'Could not send right now.').replace(/[<>]/g, '')}
      <div class="fb-fallback">
        <button type="button" data-fb="mail">Email it instead</button>
        <button type="button" data-fb="issue">Open a GitHub issue</button>
      </div>`;
    const note = ta.value.trim();
    box.querySelector('[data-fb="mail"]').addEventListener('click', () => openExternal(
      `mailto:${PROJECT.email}?subject=${encodeURIComponent('Scrawly feedback')}&body=${encodeURIComponent(note)}`));
    box.querySelector('[data-fb="issue"]').addEventListener('click', () => openExternal(
      `${PROJECT.repo}/issues/new?title=${encodeURIComponent('Feedback')}&body=${encodeURIComponent(note)}`));
  };
  ov.querySelector('.fb-send').addEventListener('click', async (ev) => {
    const msg = ta.value.trim();
    const box = ov.querySelector('.fb-msg');
    if (!msg) { box.textContent = 'Please write a note first.'; box.className = 'fb-msg fb-err'; return; }
    const btn = ev.currentTarget;
    btn.disabled = true;
    btn.textContent = 'Sending…';
    box.className = 'fb-msg';
    box.textContent = 'Sending your note. This can take a few seconds.';
    try {
      const res = await fetch(`${API_BASE}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, email: ov.querySelector('.fb-email').value.trim() }),
      });
      let data = null;
      try { data = await res.json(); } catch { /* empty body */ }
      if (!res.ok) throw new Error((data && data.detail && data.detail.message) || '');
      toast.show((data && data.message) || 'Thanks, your note was sent.', 'success');
      close();
    } catch (err) {
      btn.disabled = false;
      btn.textContent = 'Send';
      fallback(err && err.message);
    }
  });
}
window.openFeedback = openFeedback;   // reachable for verification

let _appBooted = false;
function bootApp() {
  if (_appBooted) return;
  _appBooted = true;
  loadClients();
  loadHome();
  loadSettings();
}

// Start the app for this edition (see edition.js).
startApp(bootApp);
