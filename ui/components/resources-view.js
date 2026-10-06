// ui/components/resources-view.js
// Resources view — the CSS / JS / media sub-resources every page pulls in,
// HEAD-checked during the crawl for status, content-type and size (SF Pattern A).
// Broken (4xx/5xx/no-response) resources are the headline: a 404 stylesheet or
// script is invisible in a page-only crawl but breaks rendering for bots.

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const TYPE_LABEL = { css: 'CSS', js: 'JS', media: 'Media' };
const fmtSize = (b) => (b == null ? ' - ' : b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(1)} MB`);
const pathOf = (u) => { try { const x = new URL(u); return x.pathname + x.search; } catch { return u; } };
const hostOf = (u) => { try { return new URL(u).hostname; } catch { return ''; } };
// Map an HTTP status to a shared status-chip class (0/none → error).
const statusClass = (code) => {
  if (!code) return 'status-err';
  if (code >= 500) return 'status-5xx';
  if (code >= 400) return 'status-4xx';
  if (code >= 300) return 'status-3xx';
  return 'status-2xx';
};

export class ResourcesView {
  constructor(container, apiBase) {
    this.el = container;
    this.api = apiBase;
    this.data = { resources: [], summary: {} };
    this.filter = 'all';
    this.query = '';
    this.crawlId = null;
    this._shell();
  }

  _shell() {
    this.el.innerHTML = `
      <h1 style="margin-bottom:2px;">Resources</h1>
      <p style="margin-bottom:var(--space-2);">Every CSS, JavaScript and media file the crawled pages load - fetched and status-checked. Broken ones break rendering for bots.</p>
      <div class="rv-stats"></div>
      <div class="rv-bar">
        <div class="rv-filters"></div>
        <input class="rv-search" type="text" placeholder="Search resource URLs…">
      </div>
      <div class="rv-table-wrap"><table class="rv-table stbl">
        <thead><tr>
          <th style="width:70px;">Status</th><th style="width:64px;">Type</th>
          <th style="width:84px;">Size</th><th style="width:60px;">Refs</th>
          <th style="width:170px;">Content-Type</th><th>URL</th>
        </tr></thead>
        <tbody></tbody>
      </table></div>`;
    this.el.querySelector('.rv-search').addEventListener('input', (e) => {
      this.query = e.target.value.toLowerCase().trim();
      this._rows();
    });
  }

  async load(crawlId) {
    if (!crawlId) return;
    // Cache per crawl — the view is re-entered on every tab switch.
    if (this.crawlId === crawlId && this.data.resources.length) { this._render(); return; }
    try {
      const r = await fetch(`${this.api}/resources/${crawlId}`);
      this.data = await r.json();
      this.crawlId = crawlId;
    } catch { this.data = { resources: [], summary: {} }; }
    this._render();
  }

  _render() {
    const s = this.data.summary || {};
    const chip = (label, v, cls = '') => `<span class="chip-stat ${cls}">${v ?? 0}<small>${label}</small></span>`;
    this.el.querySelector('.rv-stats').innerHTML =
      chip('resources', s.total) +
      chip('css', s.css?.count) + chip('js', s.js?.count) + chip('media', s.media?.count) +
      chip('broken', s.broken, s.broken ? 'danger' : '');

    const counts = { all: s.total || 0, css: s.css?.count || 0, js: s.js?.count || 0, media: s.media?.count || 0, broken: s.broken || 0 };
    this.el.querySelector('.rv-filters').innerHTML = ['all', 'css', 'js', 'media', 'broken']
      .map(f => `<button class="pill${f === this.filter ? ' active' : ''}${f === 'broken' && counts.broken ? ' danger' : ''}" data-f="${f}">
        ${f === 'all' ? 'All' : (TYPE_LABEL[f] || 'Broken')} <span class="pill-n">${counts[f]}</span></button>`).join('');
    this.el.querySelectorAll('.rv-filters .pill').forEach(b => b.addEventListener('click', () => {
      this.filter = b.dataset.f;
      this._render();
    }));
    this._rows();
  }

  _rows() {
    const q = this.query;
    let rows = this.data.resources || [];
    if (this.filter === 'broken') rows = rows.filter(r => r.broken);
    else if (this.filter !== 'all') rows = rows.filter(r => r.type === this.filter);
    if (q) rows = rows.filter(r => r.url.toLowerCase().includes(q));
    // Broken first, then heaviest — the two things worth acting on.
    rows = [...rows].sort((a, b) => (b.broken - a.broken) || ((b.size || 0) - (a.size || 0)));

    const body = this.el.querySelector('.rv-table tbody');
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="6" class="stbl-empty">${
        this.data.resources?.length ? 'No resources match this filter.'
          : 'No resources recorded for this crawl. (Enable CSS / JavaScript / Media under Configuration → Extraction.)'
      }</td></tr>`;
      return;
    }
    body.innerHTML = rows.map(r => `
      <tr class="${r.broken ? 'rv-broken' : ''}">
        <td><span class="status-chip ${statusClass(r.status)}">${r.status || 'ERR'}</span></td>
        <td><span class="type-tag type-${r.type}">${TYPE_LABEL[r.type] || r.type}</span></td>
        <td class="stbl-num">${fmtSize(r.size)}</td>
        <td class="stbl-num">${r.ref_count}</td>
        <td class="rv-ct">${esc(r.content_type || ' - ')}</td>
        <td class="rv-url stbl-mono" title="${esc(r.url)}">
          <a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(pathOf(r.url))}</a>
          <span class="rv-host">${esc(hostOf(r.url))}</span>
        </td>
      </tr>`).join('');
  }
}
