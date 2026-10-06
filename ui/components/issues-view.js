// ui/components/issues-view.js — Issues & Audits, rebuilt around triage.
//
// The question this view has to answer is "what do I fix first?", and the old
// hub could not answer it: 49 findings rendered as identical 164px cards, with
// the deciding number (pages affected) as grey text at the bottom. Here severity
// and impact drive the visual hierarchy, filters actually filter, and detail
// stays collapsed until asked for.

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export const SEV_ORDER = ['Critical', 'High', 'Medium', 'Low', 'Info'];
const SEV_RANK = { Critical: 5, High: 4, Medium: 3, Low: 2, Info: 1 };
const SEV_VAR = {
  Critical: 'var(--color-critical)', High: 'var(--color-warning)',
  Medium: 'var(--color-warning)', Low: 'var(--color-notice)',
  Info: 'var(--border-color)',
};
const cls = (s) => `sev-${String(s || 'info').toLowerCase()}`;

// Impact score: severity is the primary key, breadth the tiebreaker. A Critical
// on one page still outranks a Low on two hundred — but among equals, the one
// touching more pages goes first.
const impactOf = (i) =>
  (SEV_RANK[i.severity] || 0) * 100000 + Math.min(99999, (i.affected_url_ids || []).length);

export class IssuesView {
  /**
   * @param {HTMLElement} container
   * @param {object} hooks  { onViewPages, onCopyPrompt, canFix, fixedCount, onFix, onFixOverview }
   */
  constructor(container, hooks = {}) {
    this.el = container;
    this.hooks = hooks;
    this.issues = [];
    this.category = 'all';
    this.sevFilter = new Set();
    this.query = '';
    this.sort = 'impact';
    this.open = new Set();
    this.collapsed = new Set();
  }

  setIssues(issues) {
    this.issues = (issues || []).map(i => ({ ...i, affected_url_ids: i.affected_url_ids || [] }));
    this.render();
  }

  // ---- derivation -------------------------------------------------------
  get categories() {
    const seen = new Map();
    for (const i of this.issues) {
      const c = i.category || 'Other';
      seen.set(c, (seen.get(c) || 0) + 1);
    }
    return [...seen.entries()].sort((a, b) => b[1] - a[1]);
  }

  _visible() {
    const q = this.query.trim().toLowerCase();
    let out = this.issues.filter(i =>
      (this.category === 'all' || i.category === this.category) &&
      (!this.sevFilter.size || this.sevFilter.has(i.severity)) &&
      (!q ||
        (i.title || '').toLowerCase().includes(q) ||
        (i.why_it_matters || '').toLowerCase().includes(q) ||
        (i.domain || '').toLowerCase().includes(q) ||
        (i.check_id || '').toLowerCase().includes(q))
    );
    const by = {
      impact: (a, b) => impactOf(b) - impactOf(a),
      pages: (a, b) => b.affected_url_ids.length - a.affected_url_ids.length,
      severity: (a, b) => (SEV_RANK[b.severity] || 0) - (SEV_RANK[a.severity] || 0),
      title: (a, b) => (a.title || '').localeCompare(b.title || ''),
    }[this.sort];
    return out.sort(by);
  }

  _sevCounts(list) {
    const c = {};
    for (const i of list) c[i.severity] = (c[i.severity] || 0) + 1;
    return c;
  }

  // ---- fragments --------------------------------------------------------
  _mixBar(list) {
    const c = this._sevCounts(list);
    const total = list.length || 1;
    return `<span class="iss-mix" title="${SEV_ORDER.filter(s => c[s]).map(s => `${c[s]} ${s}`).join(', ')}">` +
      SEV_ORDER.filter(s => c[s]).map(s =>
        `<i style="width:${(c[s] / total) * 100}%;background:${SEV_VAR[s]}"></i>`).join('') +
      '</span>';
  }

  _row(i) {
    const n = i.affected_url_ids.length;
    const fixed = this.hooks.fixedCount ? this.hooks.fixedCount(i) : 0;
    const isOpen = this.open.has(i.id);
    const canFix = this.hooks.canFix && this.hooks.canFix();
    return `<div class="iss-row ${isOpen ? 'is-open' : ''}" data-id="${i.id}">
      <span class="iss-bar ${cls(i.severity)}"></span>
      <span class="iss-sevlab ${cls(i.severity)}">${esc(i.severity)}</span>
      <div class="iss-main">
        <div class="iss-title" title="${esc(i.title)}">${esc(i.title)}</div>
        <div class="iss-why">${esc(i.why_it_matters || i.domain || '')}</div>
      </div>
      <div class="iss-impact">
        <div class="iss-impact-n">${n}</div>
        <div class="iss-impact-l">page${n === 1 ? '' : 's'}</div>
      </div>
      <div class="iss-actions">
        ${fixed > 0
          ? `<button class="btn btn-secondary iss-fixed" data-id="${i.id}">✓ Fixed ${fixed}</button>`
          : (canFix && i.tier !== 'FLAG'
            ? `<button class="btn btn-primary iss-fix" data-id="${i.id}">Fix</button>` : '')}
        <button class="btn btn-secondary iss-copy iss-secondary" data-id="${i.id}">Copy prompt</button>
        <button class="btn btn-secondary iss-pages iss-secondary" data-id="${i.id}">Pages</button>
        <button class="btn btn-secondary iss-more" data-id="${i.id}"
                aria-expanded="${isOpen}" title="Details">${isOpen ? '▴' : '▾'}</button>
      </div>
      ${isOpen ? this._detail(i) : ''}
    </div>`;
  }

  _detail(i) {
    // Truncate BEFORE escaping — slicing escaped output can cut an entity in
    // half (`&lt;` → `&l`) and render as mojibake.
    const ev = i.evidence && Object.keys(i.evidence).length
      ? Object.entries(i.evidence).slice(0, 5)
          .map(([k, v]) => `${esc(String(k).slice(0, 60))}: ${esc(String(v).slice(0, 160))}`)
          .join(' · ')
      : '';
    const tierNote = {
      AUTO: 'Scrawly can apply this automatically on a connected site.',
      REVIEW: 'Needs a human decision before it is applied.',
      FLAG: 'Report-only - never auto-applied.',
    }[i.tier] || '';
    return `<div class="iss-detail">
      ${i.recommended_fix ? `<div class="iss-detail-row"><b>Recommended fix</b>${esc(i.recommended_fix)}</div>` : ''}
      ${i.why_it_matters ? `<div class="iss-detail-row"><b>Why it matters</b>${esc(i.why_it_matters)}</div>` : ''}
      ${ev ? `<div class="iss-detail-row"><b>Evidence</b><span class="iss-ev mono">${ev}</span></div>` : ''}
      <div class="iss-tier">
        ${tierNote ? `<span>${esc(tierNote)}</span>` : ''}
      </div>
    </div>`;
  }

  // ---- render -----------------------------------------------------------
  render() {
    const visible = this._visible();
    const counts = this._sevCounts(this.issues);
    const cats = this.categories;

    // Triage: the three highest-impact findings, as direct jump targets.
    const top = [...this.issues].sort((a, b) => impactOf(b) - impactOf(a)).slice(0, 3);

    const groups = [];
    for (const i of visible) {
      const key = i.domain || 'Other';
      let g = groups.find(x => x.key === key);
      if (!g) groups.push(g = { key, rows: [] });
      g.rows.push(i);
    }
    groups.sort((a, b) => impactOf(b.rows[0]) - impactOf(a.rows[0]));

    this.el.innerHTML = `
      <div class="iss">
        <div class="iss-head">
          <div>
            <h1>Issues &amp; Audits</h1>
            <p class="iss-sub">${this.issues.length} finding${this.issues.length === 1 ? '' : 's'}
               across ${cats.length} area${cats.length === 1 ? '' : 's'} - sorted by impact.</p>
          </div>
          <div class="iss-sevs">
            ${SEV_ORDER.filter(s => counts[s]).map(s => `
              <button class="iss-sev ${cls(s)} ${this.sevFilter.has(s) ? 'is-on' : ''}"
                      data-sev="${s}" aria-pressed="${this.sevFilter.has(s)}">
                <span class="dot" style="background:${SEV_VAR[s]}"></span>
                <span class="n">${counts[s]}</span> ${s}
              </button>`).join('')}
          </div>
        </div>

        ${top.length ? `<div class="card iss-triage">
          <span class="iss-triage-h">Start here</span>
          <div class="iss-triage-list">
            ${top.map(i => `<span class="iss-triage-item" data-jump="${i.id}">
              <span class="dot" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${SEV_VAR[i.severity]}"></span>
              ${esc(i.title)} <span class="n">${i.affected_url_ids.length}</span>
            </span>`).join('')}
          </div>
        </div>` : ''}

        <div class="iss-tools">
          <input class="iss-search" type="search" placeholder="Search findings, checks or areas…"
                 value="${esc(this.query)}" aria-label="Search findings">
          <label class="iss-sort">Sort
            <select class="iss-sort-sel">
              <option value="impact"${this.sort === 'impact' ? ' selected' : ''}>Impact</option>
              <option value="pages"${this.sort === 'pages' ? ' selected' : ''}>Pages affected</option>
              <option value="severity"${this.sort === 'severity' ? ' selected' : ''}>Severity</option>
              <option value="title"${this.sort === 'title' ? ' selected' : ''}>Name</option>
            </select>
          </label>
          <span class="iss-count">${visible.length} shown</span>
        </div>

        <div class="iss-body">
          <nav class="iss-rail" aria-label="Filter by area">
            <div class="iss-rail-item ${this.category === 'all' ? 'is-on' : ''}" data-cat="all">
              <span>All issues</span><span class="iss-rail-n">${this.issues.length}</span>
            </div>
            ${cats.map(([c, n]) => `
              <div class="iss-rail-item ${this.category === c ? 'is-on' : ''} ${n ? '' : 'is-empty'}"
                   data-cat="${esc(c)}">
                <span>${esc(c)}</span><span class="iss-rail-n">${n}</span>
              </div>`).join('')}
          </nav>

          <div class="iss-list">
            ${groups.length ? groups.map(g => {
              const isCollapsed = this.collapsed.has(g.key);
              return `<section class="iss-group">
                <div class="iss-group-h ${isCollapsed ? 'collapsed' : ''}" data-group="${esc(g.key)}">
                  <span class="iss-group-caret">▾</span>
                  <span class="iss-group-t">${esc(g.key)}</span>
                  <span class="iss-group-n">${g.rows.length}</span>
                  ${this._mixBar(g.rows)}
                </div>
                <div class="iss-group-body ${isCollapsed ? 'collapsed' : ''}">
                  ${g.rows.map(r => this._row(r)).join('')}
                </div>
              </section>`;
            }).join('') : `<div class="iss-empty">
              <p><strong>Nothing matches these filters.</strong></p>
              <p>Try clearing the search or severity filters.</p>
            </div>`}
          </div>
        </div>
      </div>`;
    this._wire();
  }

  _wire() {
    const $$ = (s) => this.el.querySelectorAll(s);
    const byId = (id) => this.issues.find(i => String(i.id) === String(id));

    $$('.iss-sev').forEach(b => b.addEventListener('click', () => {
      const s = b.dataset.sev;
      this.sevFilter.has(s) ? this.sevFilter.delete(s) : this.sevFilter.add(s);
      this.render();
    }));
    $$('.iss-rail-item').forEach(b => b.addEventListener('click', () => {
      this.category = b.dataset.cat;
      this.render();
    }));
    $$('.iss-group-h').forEach(h => h.addEventListener('click', () => {
      const k = h.dataset.group;
      this.collapsed.has(k) ? this.collapsed.delete(k) : this.collapsed.add(k);
      this.render();
    }));
    $$('.iss-more').forEach(b => b.addEventListener('click', (e) => {
      e.stopPropagation();
      const id = Number(b.dataset.id);
      this.open.has(id) ? this.open.delete(id) : this.open.add(id);
      this.render();
    }));

    const search = this.el.querySelector('.iss-search');
    if (search) {
      // Re-render on input loses focus, so restore caret position after.
      search.addEventListener('input', () => {
        this.query = search.value;
        const pos = search.selectionStart;
        this.render();
        const s2 = this.el.querySelector('.iss-search');
        if (s2) { s2.focus(); s2.setSelectionRange(pos, pos); }
      });
    }
    const sortSel = this.el.querySelector('.iss-sort-sel');
    if (sortSel) sortSel.addEventListener('change', () => {
      this.sort = sortSel.value;
      this.render();
    });

    $$('.iss-triage-item').forEach(t => t.addEventListener('click', () => {
      const row = this.el.querySelector(`.iss-row[data-id="${t.dataset.jump}"]`);
      if (row) {
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
        row.classList.add('is-open');
        setTimeout(() => row.classList.remove('is-open'), 1600);
      }
    }));

    $$('.iss-pages').forEach(b => b.addEventListener('click', (e) => {
      e.stopPropagation();
      this.hooks.onViewPages?.(byId(b.dataset.id));
    }));
    $$('.iss-copy').forEach(b => b.addEventListener('click', (e) => {
      e.stopPropagation();
      this.hooks.onCopyPrompt?.(byId(b.dataset.id), b);
    }));
    $$('.iss-fix').forEach(b => b.addEventListener('click', (e) => {
      e.stopPropagation();
      this.hooks.onFix?.(byId(b.dataset.id), b);
    }));
    $$('.iss-fixed').forEach(b => b.addEventListener('click', (e) => {
      e.stopPropagation();
      this.hooks.onFixOverview?.(byId(b.dataset.id));
    }));
  }
}
