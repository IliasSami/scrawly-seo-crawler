// ui/components/explorer.js
// Screaming-Frog-style Explorer: dimension tabs (one data model, many slices),
// each with its own column set + a contextual, faceted filter bar showing live
// counts. Owns a DataGrid for the table and delegates row-clicks to a detail view.
import { DataGrid } from './data-grid.js';
import { esc } from './escape.js';

const len = (s) => (s == null ? 0 : String(s).length);
const norm = (u) => (u || '').replace(/#.*$/, '').replace(/\/$/, '').toLowerCase();
const joinArr = (a) => Array.isArray(a) ? a.join(' | ') : (a || '');

const statusCell = (val) => {
  const span = document.createElement('span');
  if (val == null) { span.textContent = ' - '; return span; }
  let cls = 'passed';
  if (val >= 500) cls = 'critical'; else if (val >= 400) cls = 'critical';
  else if (val >= 300) cls = 'notice';
  span.className = `badge badge-${cls}`;
  span.textContent = val;
  return span;
};
const yesno = (v) => (v === false ? 'No' : 'Yes');
const linkCell = (val) => {
  const a = document.createElement('a');
  a.href = '#'; a.className = 'mono'; a.textContent = val;
  a.style.color = 'var(--text-primary)'; a.style.textDecoration = 'none';
  a.addEventListener('click', (e) => e.preventDefault());
  return a;
};

// Column presets
const C = {
  address: { key: 'address', label: 'Address', render: linkCell },
  status: { key: 'status', label: 'Status', render: statusCell },
  indexable: { key: 'indexable', label: 'Indexable', render: yesno },
  depth: { key: 'depth', label: 'Depth', render: (v) => (v ?? '–') },
  inlinks: { key: 'inlink_count', label: 'Inlinks' },
  authority: { key: 'pagerank', label: 'Authority', render: (v) => (v == null ? '–' : v) },
  outlinks: { key: 'outlink_count', label: 'Outlinks' },
  words: { key: 'word_count', label: 'Words' },
  title: { key: 'title', label: 'Title' },
  titleLen: { key: '_titleLen', label: 'Len' },
  meta: { key: 'meta_desc', label: 'Meta Description' },
  metaLen: { key: '_metaLen', label: 'Len' },
  h1: { key: '_h1', label: 'H1' },
  h1count: { key: '_h1c', label: 'Count' },
  canonical: { key: 'canonical', label: 'Canonical', render: (v) => v || ' - ' },
  metaRobots: { key: 'meta_robots', label: 'Meta Robots', render: (v) => v || ' - ' },
  xRobots: { key: 'x_robots', label: 'X-Robots-Tag', render: (v) => v || ' - ' },
  reason: { key: 'indexability_reason', label: 'Indexability', render: (v) => v || 'Indexable' },
  hops: { key: '_hops', label: 'Hops' },
  cls: { key: 'cls', label: 'CLS', render: (v) => (v == null ? '–' : v) },
  lcp: { key: 'lcp_s', label: 'LCP(s)', render: (v) => (v == null ? '–' : v) },
  readability: { key: 'readability', label: 'Readability', render: (v) => (v == null ? '–' : v) },
  textCode: { key: 'text_to_code', label: 'Text/Code', render: (v) => (v == null ? '–' : Math.round(v * 100) + '%') },
  forms: { key: 'forms_count', label: 'Forms', render: (v) => (v || 0) },
  segment: { key: 'segment', label: 'Segment', render: (v) => v || ' - ' },
  ga4Sessions: { key: '_ga4Sessions', label: 'Sessions', render: (v) => (v == null ? '–' : v) },
  ga4Engaged: { key: '_ga4Engaged', label: 'Engaged', render: (v) => (v == null ? '–' : v) },
  ga4Views: { key: '_ga4Views', label: 'Views', render: (v) => (v == null ? '–' : v) },
  ga4Conv: { key: '_ga4Conv', label: 'Conversions', render: (v) => (v == null ? '–' : v) },
  spellCount: { key: '_spellCount', label: 'Issues', render: (v) => (v || 0) },
  pdfPages: { key: '_pdfPages', label: 'Pages', render: (v) => (v == null ? '–' : v) },
  pdfAuthor: { key: '_pdfAuthor', label: 'Author', render: (v) => v || ' - ' },
};

// Duplicate detector: rows whose non-empty key value occurs >1 time.
function dupes(rows, keyFn) {
  const counts = {};
  rows.forEach(r => { const k = keyFn(r); if (k) counts[k] = (counts[k] || 0) + 1; });
  return rows.filter(r => { const k = keyFn(r); return k && counts[k] > 1; });
}
const F = (id, label, fn) => ({ id, label, fn });

const DIMENSIONS = [
  { id: 'internal', label: 'Internal', cols: [C.address, C.status, C.indexable, C.depth, C.inlinks, C.authority, C.words, C.segment, C.title], filters: [
    F('all', 'All', (r) => r),
    F('indexable', 'Indexable', (r) => r.filter(x => x.indexable !== false)),
    F('nonindexable', 'Non-Indexable', (r) => r.filter(x => x.indexable === false)),
    F('orphan', 'Orphans (0 inlinks)', (r) => r.filter(x => (x.inlink_count || 0) === 0)),
    F('r3', 'Redirect (3xx)', (r) => r.filter(x => x.status >= 300 && x.status < 400)),
    F('r4', 'Client Error (4xx)', (r) => r.filter(x => x.status >= 400 && x.status < 500)),
    F('r5', 'Server Error (5xx)', (r) => r.filter(x => x.status >= 500)),
  ]},
  { id: 'response', label: 'Response Codes', cols: [C.address, C.status, C.hops, C.reason], filters: [
    F('all', 'All', (r) => r),
    F('ok', 'Success (2xx)', (r) => r.filter(x => x.status >= 200 && x.status < 300)),
    F('r3', 'Redirection (3xx)', (r) => r.filter(x => x.status >= 300 && x.status < 400)),
    F('r4', 'Client Error (4xx)', (r) => r.filter(x => x.status >= 400 && x.status < 500)),
    F('r5', 'Server Error (5xx)', (r) => r.filter(x => x.status >= 500)),
    F('none', 'No Response', (r) => r.filter(x => !x.status)),
  ]},
  { id: 'titles', label: 'Page Titles', cols: [C.address, C.title, C.titleLen], filters: [
    F('all', 'All', (r) => r),
    F('missing', 'Missing', (r) => r.filter(x => !x.title)),
    F('dup', 'Duplicate', (r) => dupes(r, x => (x.title || '').trim().toLowerCase())),
    F('long', 'Over 60 Chars', (r) => r.filter(x => len(x.title) > 60)),
    F('short', 'Below 30 Chars', (r) => r.filter(x => x.title && len(x.title) < 30)),
  ]},
  { id: 'meta', label: 'Meta Description', cols: [C.address, C.meta, C.metaLen], filters: [
    F('all', 'All', (r) => r),
    F('missing', 'Missing', (r) => r.filter(x => !x.meta_desc)),
    F('dup', 'Duplicate', (r) => dupes(r, x => (x.meta_desc || '').trim().toLowerCase())),
    F('thin', 'Too thin for AI', (r) => r.filter(x => x.meta_desc && len(x.meta_desc) < 120)),
    F('detailed', 'Detailed (120+)', (r) => r.filter(x => len(x.meta_desc) >= 120)),
  ]},
  { id: 'h1', label: 'H1', cols: [C.address, C.h1, C.h1count], filters: [
    F('all', 'All', (r) => r),
    F('missing', 'Missing', (r) => r.filter(x => !(x.h1 && x.h1.length))),
    F('multi', 'Multiple', (r) => r.filter(x => x.h1 && x.h1.length > 1)),
    F('dup', 'Duplicate', (r) => dupes(r, x => joinArr(x.h1).trim().toLowerCase())),
  ]},
  { id: 'directives', label: 'Directives', cols: [C.address, C.metaRobots, C.xRobots, C.indexable, C.canonical], filters: [
    F('all', 'All', (r) => r),
    F('noindex', 'Noindex', (r) => r.filter(x => /noindex/i.test(x.meta_robots || '') || /noindex/i.test(x.x_robots || '') || x.indexable === false)),
    F('nofollow', 'Nofollow', (r) => r.filter(x => /nofollow/i.test(x.meta_robots || ''))),
    F('canon', 'Canonicalised', (r) => r.filter(x => x.canonical && norm(x.canonical) !== norm(x.address))),
  ]},
  { id: 'canonicals', label: 'Canonicals', cols: [C.address, C.canonical, C.indexable], filters: [
    F('all', 'All', (r) => r),
    F('missing', 'Missing', (r) => r.filter(x => !x.canonical)),
    F('self', 'Self-Referencing', (r) => r.filter(x => x.canonical && norm(x.canonical) === norm(x.address))),
    F('canon', 'Canonicalised', (r) => r.filter(x => x.canonical && norm(x.canonical) !== norm(x.address))),
  ]},
  { id: 'content', label: 'Content', cols: [C.address, C.words, C.readability, C.textCode, C.forms], filters: [
    F('all', 'All', (r) => r),
    F('thin', 'Thin (<200 words)', (r) => r.filter(x => (x.word_count || 0) < 200)),
    F('hardread', 'Hard to Read (<30)', (r) => r.filter(x => x.readability != null && (x.word_count || 0) >= 300 && x.readability < 30)),
    F('forms', 'Has Forms', (r) => r.filter(x => (x.forms_count || 0) > 0)),
  ]},
  // Enrichment dimensions — only meaningful when the crawl ran the enrichment,
  // but harmless (empty) otherwise.
  { id: 'analytics', label: 'Analytics', cols: [C.address, C.ga4Sessions, C.ga4Engaged, C.ga4Views, C.ga4Conv, C.segment], filters: [
    F('all', 'All', (r) => r),
    F('hasdata', 'Has GA4 Data', (r) => r.filter(x => x._hasGa4)),
    F('nodata', 'No GA4 Data', (r) => r.filter(x => !x._hasGa4 && x.indexable !== false)),
    F('sessions', 'Sessions > 0', (r) => r.filter(x => (x._ga4Sessions || 0) > 0)),
    F('conv', 'Has Conversions', (r) => r.filter(x => (x._ga4Conv || 0) > 0)),
  ]},
  { id: 'spelling', label: 'Spelling', cols: [C.address, C.spellCount, C.words, C.title], filters: [
    F('all', 'All', (r) => r),
    F('issues', 'Has Issues', (r) => r.filter(x => (x._spellCount || 0) > 0)),
    F('clean', 'Clean', (r) => r.filter(x => (x._spellCount || 0) === 0)),
  ]},
  { id: 'pdf', label: 'PDF', cols: [C.address, C.status, C.pdfPages, C.pdfAuthor, C.words, C.indexable], filters: [
    F('all', 'PDFs', (r) => r.filter(x => x._isPdf)),
    F('nonindexable', 'Non-Indexable', (r) => r.filter(x => x._isPdf && x.indexable === false)),
  ]},
];

export class Explorer {
  constructor({ railEl, tabsEl, filterEl, gridEl, onRowClick }) {
    this.railEl = railEl;
    this.tabsEl = tabsEl;
    this.filterEl = filterEl;
    this.rows = [];
    this.dimId = 'internal';
    this.filterId = 'all';
    this.hiddenCols = new Set();
    this.focus = null;   // {ids:Set, label} while showing only some pages
    this.grid = new DataGrid(gridEl, { columns: DIMENSIONS[0].cols, onRowClick: onRowClick || (() => {}) });
    this._renderTabs();
  }

  _dim() {
    if (this.dimId === 'custom' && this.customDim) return this.customDim;
    return DIMENSIONS.find(d => d.id === this.dimId) || DIMENSIONS[0];
  }

  // Rows in view: everything, or only the focused pages.
  _base() {
    return this.focus ? this.rows.filter(r => this.focus.ids.has(r.id)) : this.rows;
  }

  _count(dimId, filterId) {
    const dim = DIMENSIONS.find(d => d.id === dimId);
    const f = dim && dim.filters.find(x => x.id === filterId);
    return f ? f.fn(this._base()).length : 0;
  }

  // Show only these pages (e.g. the pages an issue affects) until cleared.
  focusOn(ids, label) {
    this.focus = { ids: new Set(ids || []), label: label || 'selected pages' };
    this.dimId = 'internal';
    this.filterId = 'all';
    this._renderTabs();
    this._apply();
  }

  clearFocus() {
    this.focus = null;
    this._apply();
  }

  // Left overview rail: headline counts, click to jump to a dimension+filter.
  _renderRail() {
    if (!this.railEl) return;
    const spec = [
      ['Overview', [['All URLs', 'internal', 'all'], ['Indexable', 'internal', 'indexable'], ['Non-Indexable', 'internal', 'nonindexable']]],
      ['Status', [['Success (2xx)', 'response', 'ok'], ['Redirect (3xx)', 'response', 'r3'], ['Client Error (4xx)', 'response', 'r4'], ['Server Error (5xx)', 'response', 'r5']]],
      ['Content', [['Missing Titles', 'titles', 'missing'], ['Duplicate Titles', 'titles', 'dup'], ['Missing Meta', 'meta', 'missing']]],
    ];
    this.railEl.innerHTML = spec.map(([h, items]) => `
      <div class="ex-rail-group">
        <div class="ex-rail-h">${h}</div>
        ${items.map(([label, dim, f]) => {
          const active = dim === this.dimId && f === this.filterId ? ' active' : '';
          return `<button class="ex-rail-item${active}" data-dim="${dim}" data-f="${f}">
            <span>${label}</span><span class="ex-rail-n">${this._count(dim, f)}</span></button>`;
        }).join('')}
      </div>`).join('');
    this.railEl.querySelectorAll('.ex-rail-item').forEach(b =>
      b.addEventListener('click', () => {
        this.dimId = b.dataset.dim;
        this.filterId = b.dataset.f;
        this._renderTabs();
        this._apply();
      }));
  }

  setRows(rows) {
    this.focus = null;   // a new data set is never pre-filtered
    // Precompute derived fields so computed columns render AND sort correctly.
    const enriched = (rows || []).map(r => ({
      ...r,
      _titleLen: len(r.title),
      _metaLen: len(r.meta_desc),
      _h1: joinArr(r.h1),
      _h1c: Array.isArray(r.h1) ? r.h1.length : 0,
      _hops: (r.redirect_chain || []).length,
      // Enrichment-derived fields (GA4 / spelling / PDF) — flattened so they
      // render + sort in the grid like any other column.
      _ga4Sessions: (r.ga4 && r.ga4.sessions) ?? null,
      _ga4Engaged: (r.ga4 && r.ga4.engagedSessions) ?? null,
      _ga4Views: (r.ga4 && r.ga4.screenPageViews) ?? null,
      _ga4Conv: (r.ga4 && r.ga4.conversions) ?? null,
      _hasGa4: !!r.ga4,
      _spellCount: Array.isArray(r.spelling) ? r.spelling.length : 0,
      _isPdf: !!r.pdf_properties,
      _pdfPages: (r.pdf_properties && r.pdf_properties.page_count) ?? null,
      _pdfAuthor: (r.pdf_properties && r.pdf_properties.author) || '',
    }));
    // Custom-extraction columns (site-wide scraper): flatten each custom_data
    // key onto the row + build a dynamic "Custom" dimension.
    const keys = new Set();
    enriched.forEach(r => Object.keys(r.custom_data || {}).forEach(k => keys.add(k)));
    this.customKeys = [...keys];
    enriched.forEach(r => this.customKeys.forEach(k => {
      const v = (r.custom_data || {})[k];
      r['cx:' + k] = Array.isArray(v) ? v.join(' | ') : (v ?? '');
    }));
    this.customDim = this.customKeys.length ? {
      id: 'custom', label: 'Custom',
      cols: [C.address, ...this.customKeys.map(k => ({ key: 'cx:' + k, label: k }))],
      filters: [F('all', 'All', (r) => r)],
    } : null;
    this.rows = enriched;
    this._renderTabs();
    this._apply();
  }

  selectDimension(id) {
    this.dimId = id;
    this.filterId = 'all';
    this._renderTabs();
    this._apply();
  }

  selectFilter(id) {
    this.filterId = id;
    this._apply();
  }

  _renderTabs() {
    const dims = this.customDim ? [...DIMENSIONS, this.customDim] : DIMENSIONS;
    this.tabsEl.innerHTML = dims.map(d =>
      `<button class="ex-tab${d.id === this.dimId ? ' active' : ''}" data-dim="${d.id}">${d.label}</button>`
    ).join('');
    this.tabsEl.querySelectorAll('.ex-tab').forEach(b =>
      b.addEventListener('click', () => this.selectDimension(b.dataset.dim)));
  }

  _apply() {
    const dim = this._dim();
    // Contextual filter chips with live counts computed over the full row set.
    const base = this._base();
    const focusBar = this.focus
      ? `<div class="ex-focus" role="status">Showing ${base.length} page${base.length === 1 ? '' : 's'} with:
          <b>${esc(this.focus.label)}</b>
          <button class="ex-focus-clear" type="button">Show all pages</button></div>`
      : '';
    this.filterEl.innerHTML = focusBar + dim.filters.map(f => {
      const count = f.fn(base).length;
      return `<button class="ex-chip${f.id === this.filterId ? ' active' : ''}" data-f="${f.id}">
        ${f.label}<span class="ex-chip-n">${count}</span></button>`;
    }).join('');
    this.filterEl.querySelectorAll('.ex-chip').forEach(b =>
      b.addEventListener('click', () => this.selectFilter(b.dataset.f)));
    this.filterEl.querySelector('.ex-focus-clear')?.addEventListener('click', () => this.clearFocus());

    // Column picker (show/hide) — right-aligned in the filter bar.
    const pick = document.createElement('div');
    pick.className = 'ex-colpick';
    pick.innerHTML = `<button class="ex-colpick-btn" type="button">Columns ▾</button>
      <div class="ex-colpick-menu hidden">${dim.cols.filter(c => c.key !== 'address').map(c =>
        `<label><input type="checkbox" data-col="${c.key}" ${this.hiddenCols.has(c.key) ? '' : 'checked'}> ${c.label}</label>`).join('')}</div>`;
    this.filterEl.appendChild(pick);
    pick.querySelector('.ex-colpick-btn').addEventListener('click', () =>
      pick.querySelector('.ex-colpick-menu').classList.toggle('hidden'));
    pick.querySelectorAll('input[data-col]').forEach(cb => cb.addEventListener('change', () => {
      if (cb.checked) this.hiddenCols.delete(cb.dataset.col); else this.hiddenCols.add(cb.dataset.col);
      this._apply();
    }));

    const filter = dim.filters.find(f => f.id === this.filterId) || dim.filters[0];
    this.grid.columns = dim.cols.filter(c => !this.hiddenCols.has(c.key));
    this.grid.setData(filter.fn(base));
    this._renderRail();
  }
}
