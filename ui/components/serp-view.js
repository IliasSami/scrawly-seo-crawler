// ui/components/serp-view.js
// Titles & descriptions. Two lenses on the same text:
//   1. Google display: measured in pixels (Google cuts on render width, not
//      character count), so titles that fit get clicked.
//   2. AI context: your description is the first thing an AI assistant reads
//      about a page, so it needs real detail to understand and recommend you.
// "Write with AI" reads the live page and drafts a stronger title + description.

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const pathOf = (u) => { try { return new URL(u).pathname || '/'; } catch { return u; } };

export class SerpView {
  constructor(container, apiBase) {
    this.el = container;
    this.api = apiBase;
    this.rows = [];
    this.summary = {};
    this.filter = 'all';
    this.crawlId = null;
    this._shell();
  }

  _shell() {
    this.el.innerHTML = `
      <h1 style="margin-bottom:4px;">Titles &amp; descriptions</h1>
      <p style="margin-bottom:var(--space-3); max-width:70ch;">
        Your title and description are the first things Google and AI assistants read about a page.
        We check that your title fits on Google, and that your description gives AI enough detail to
        understand and recommend your page. Use <b>Write with AI</b> to draft a stronger version from
        the page's own content.</p>
      <div class="srp-stats"></div>
      <div class="srp-filters"></div>
      <div class="srp-list"></div>`;
  }

  async load(crawlId) {
    if (!crawlId) return;
    if (this.crawlId === crawlId && this.rows.length) { this._render(); return; }
    try {
      const r = await fetch(`${this.api}/serp/preview`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ crawl_id: crawlId }),
      });
      const d = await r.json();
      this.rows = d.rows || [];
      this.summary = d.summary || {};
      this.crawlId = crawlId;
      // Weakest first (thin-for-AI, then over-long titles), sorted once so an
      // edit re-measures in place instead of reshuffling the list under you.
      this.rows.sort((a, b) => this._score(b) - this._score(a));
    } catch { this.rows = []; this.summary = {}; }
    this._render();
  }

  _score(r) {
    return (r.desc_ai_thin ? 2 : 0) + (r.title_truncated ? 1 : 0);
  }

  /** Recount the summary chips from the current (possibly edited) rows. */
  _recount() {
    this.summary = {
      total: this.rows.length,
      title_truncated: this.rows.filter(r => r.title_truncated).length,
      desc_ai_thin: this.rows.filter(r => r.desc_ai_thin).length,
    };
  }

  /** Re-measure one edited snippet server-side (same engine as the crawl). */
  async _remeasure(i, title, description) {
    const cur = this.rows[i] || {};
    if (title === (cur.title || '') && description === (cur.description || '')) return;
    try {
      const r = await fetch(`${this.api}/serp/preview`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows: [{ url: cur.url, title, description }] }),
      });
      const d = await r.json();
      if (d.rows?.[0]) {
        // Re-rendering rebuilds every card; keep whatever the person is typing
        // right now (often the next field) instead of wiping it.
        const editing = this._activeEdit();
        this.rows[i] = d.rows[0];
        this._recount();
        this._render();
        this._restoreEdit(editing);
      }
    } catch { /* keep the previous measurement */ }
  }

  _activeEdit() {
    const a = document.activeElement;
    if (!a || !this.el.contains(a) || !a.classList.contains('srp-in')) return null;
    const card = a.closest('.srp-card');
    if (!card) return null;
    return {
      i: card.dataset.i, field: a.classList.contains('srp-title') ? '.srp-title' : '.srp-desc',
      value: a.value, start: a.selectionStart, end: a.selectionEnd,
    };
  }

  _restoreEdit(k) {
    if (!k) return;
    const el = this.el.querySelector(`.srp-card[data-i="${k.i}"] ${k.field}`);
    if (!el) return;
    el.value = k.value;
    el.focus();
    try { el.setSelectionRange(k.start, k.end); } catch { /* not a text field */ }
  }

  /** Read the live page and let AI draft a better title + description. */
  async _generate(i) {
    const card = this.el.querySelector(`.srp-card[data-i="${i}"]`);
    const btn = card?.querySelector('.srp-ai');
    const errEl = card?.querySelector('.srp-ai-err');
    if (errEl) errEl.textContent = '';
    if (btn) { btn.disabled = true; btn.textContent = 'Writing…'; }
    try {
      const r = await fetch(`${this.api}/serp/generate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: this.rows[i].url }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        const detail = d.detail;
        throw new Error((detail && detail.message) || (typeof detail === 'string' ? detail : 'Could not write this one.'));
      }
      this.rows[i] = d;   // the endpoint returns a fully measured row
      this._recount();
      this._render();
    } catch (e) {
      if (btn) { btn.disabled = false; btn.textContent = '✨ Write with AI'; }
      if (errEl) errEl.textContent = e.message;
    }
  }

  _render() {
    const s = this.summary;
    const chip = (label, v, cls = '') => `<span class="chip-stat ${cls}">${v ?? 0}<small>${label}</small></span>`;
    this.el.querySelector('.srp-stats').innerHTML =
      chip('pages', s.total) +
      chip('titles too long for Google', s.title_truncated, s.title_truncated ? 'danger' : '') +
      chip('descriptions too thin for AI', s.desc_ai_thin, s.desc_ai_thin ? 'warn' : '');

    const counts = {
      all: this.rows.length,
      attention: this.rows.filter(r => r.title_truncated || r.desc_ai_thin).length,
    };
    this.el.querySelector('.srp-filters').innerHTML = ['all', 'attention']
      .map(f => `<button class="pill${f === this.filter ? ' active' : ''}${f === 'attention' && counts.attention ? ' danger' : ''}" data-f="${f}">
        ${f === 'all' ? 'All pages' : 'Needs attention'} <span class="pill-n">${counts[f]}</span></button>`).join('');
    this.el.querySelectorAll('.srp-filters .pill').forEach(b => b.addEventListener('click', () => {
      this.filter = b.dataset.f; this._render();
    }));

    // Order is fixed at load (weakest first) so editing never reshuffles the list.
    let rows = this.rows.map((r, i) => ({ r, i }));
    if (this.filter === 'attention') rows = rows.filter(({ r }) => r.title_truncated || r.desc_ai_thin);

    const bar = (px, limit, bad) => {
      const pct = Math.min(100, (px / limit) * 100);
      return `<div class="srp-bar"><i style="width:${pct}%" class="${bad ? 'bad' : ''}"></i>
        <span class="srp-px ${bad ? 'bad' : ''}">${px}/${limit}px</span></div>`;
    };

    this.el.querySelector('.srp-list').innerHTML = rows.length ? rows.map(({ r, i }) => `
      <div class="srp-card${r.ai_generated ? ' srp-ai-done' : ''}" data-i="${i}">
        <div class="srp-card-top">
          <div class="srp-url mono">${esc(pathOf(r.url))}</div>
          ${r.ai_generated ? '<span class="srp-ai-tag">✨ AI draft</span>' : ''}
        </div>
        <div class="srp-field">
          <label>Title <span class="srp-chars">${r.title_chars} characters</span></label>
          <input class="srp-in srp-title ${r.title_truncated ? 'bad' : ''}" value="${esc(r.title)}">
          ${bar(r.title_px, r.title_limit_px, r.title_truncated)}
          <div class="srp-note${r.title_truncated ? ' bad' : ''}">${r.title_truncated
            ? 'Google may cut this title off. Shorten it so it shows in full.'
            : 'Fits on Google.'}</div>
        </div>
        <div class="srp-field">
          <label>Description <span class="srp-chars">${r.desc_chars} characters</span></label>
          <textarea class="srp-in srp-desc ${r.desc_ai_thin ? 'warn' : ''}" rows="3">${esc(r.description)}</textarea>
          <div class="srp-note${r.desc_ai_thin ? ' warn' : ''}">${r.desc_ai_thin
            ? 'Too thin for AI. Add the key details (what the page offers, the main names and topics) so AI can understand and recommend it.'
            : 'Good detail for AI. Google shows the first part; the full text still helps AI understand the page.'}</div>
        </div>
        <div class="srp-actions">
          <button class="srp-ai" type="button">✨ Write with AI</button>
          <span class="srp-ai-err"></span>
        </div>
      </div>`).join('')
      : `<p style="color:var(--text-secondary);">${this.rows.length
          ? 'Every page looks good.'
          : 'No pages to show for this audit yet.'}</p>`;

    // Re-measure on blur; wire the AI writer.
    this.el.querySelectorAll('.srp-card').forEach(card => {
      const i = Number(card.dataset.i);
      const t = card.querySelector('.srp-title'), d = card.querySelector('.srp-desc');
      const fire = () => this._remeasure(i, t.value, d.value);
      t.addEventListener('blur', fire);
      d.addEventListener('blur', fire);
      card.querySelector('.srp-ai')?.addEventListener('click', () => this._generate(i));
    });
  }
}
