// ui/components/drawer.js — master-detail: Overview / Inlinks / Outlinks
const norm = (u) => (u || '').replace(/#.*$/, '').replace(/\/$/, '').toLowerCase();
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const pathOf = (u) => { try { const x = new URL(u); return (x.pathname + x.search) || '/'; } catch { return u; } };

export class Drawer {
  constructor(overlayId) {
    this.overlay = document.getElementById(overlayId);
    this.panel = this.overlay.querySelector('.drawer-panel');
    this.allRows = [];
    this.onNavigate = null; // set by host to open another row
    this.overlay.addEventListener('click', (e) => { if (e.target === this.overlay) this.close(); });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !this.overlay.classList.contains('hidden')) this.close();
    });
  }

  open(urlData, allRows = [], onNavigate = null) {
    this.data = urlData;
    this.allRows = allRows || [];
    this.onNavigate = onNavigate;
    this.tab = 'overview';
    this.shotDevice = 'desktop';
    this.render();
    this.overlay.classList.remove('hidden');
  }

  _loadShot() {
    const box = this.panel.querySelector('.dr-shot');
    if (!box) return;
    box.innerHTML = `<div class="dr-shot-loading"><span class="cc-spin"></span> Rendering ${this.shotDevice} screenshot…</div>`;
    const img = new Image();
    img.className = 'dr-shot-img';
    img.onload = () => { box.innerHTML = ''; box.appendChild(img); };
    img.onerror = () => { box.innerHTML = '<div class="dr-empty">Could not render this page.</div>'; };
    img.src = `/api/screenshot?url=${encodeURIComponent(this.data.address)}&device=${this.shotDevice}`;
  }

  close() { this.overlay.classList.add('hidden'); }

  _outlinks() {
    const set = new Set(this.allRows.map(r => norm(r.address)));
    return (this.data.internal_links || []).map(l => ({ url: l, crawled: set.has(norm(l)) }));
  }

  _inlinks() {
    const target = norm(this.data.address);
    return this.allRows.filter(r =>
      (r.internal_links || []).some(l => norm(l) === target) && norm(r.address) !== target);
  }

  render() {
    const d = this.data;
    const statusColor = d.status === 200 ? 'passed' : (d.status >= 400 ? 'critical' : 'warning');
    const outlinks = this._outlinks();
    const inlinks = this._inlinks();
    const titleLen = (d.title || '').length;
    const metaLen = (d.meta_desc || '').length;
    // Rough pixel width (avg ~8px/char at Arial 18/13) for SERP truncation hints.
    const titlePx = Math.round(titleLen * 8.5);
    const titleFit = titlePx <= 580;
    // A detailed description gives AI real context; ~120+ chars is a healthy floor.
    // Long is fine, so there is no upper limit here.
    const metaFit = metaLen >= 120;

    let host = ''; try { host = new URL(d.address).hostname; } catch { /* */ }

    // Collect @type recursively (WP/Yoast nest everything under @graph).
    const collectTypes = (b) => {
      if (!b) return [];
      if (Array.isArray(b)) return b.flatMap(collectTypes);
      const out = [];
      if (b['@type']) out.push(Array.isArray(b['@type']) ? b['@type'].join(',') : b['@type']);
      if (b['@graph']) out.push(...collectTypes(b['@graph']));
      return out;
    };
    const schemaTypes = [...new Set((d.jsonld || []).flatMap(collectTypes))];
    const microRdfa = [...(d.microdata_types || []), ...(d.rdfa_types || [])];

    const tabBtn = (id, label, n) =>
      `<button class="dr-tab${this.tab === id ? ' active' : ''}" data-tab="${id}">${label}${n != null ? ` <span class="dr-tab-n">${n}</span>` : ''}</button>`;

    const overview = `
      <h3>SERP Preview</h3>
      <div class="serp-preview">
        <div class="serp-url">${esc(host)} › ${esc(pathOf(d.address))}</div>
        <div class="serp-title">${esc(d.title || 'No title found')}</div>
        <div class="serp-desc">${esc(d.meta_desc || 'No meta description found for this page.')}</div>
      </div>
      <div class="serp-meta">
        <span class="${titleFit ? 'ok' : 'warn'}">Title ${titleLen} chars · ~${titlePx}px ${titleFit ? '✓' : '· may truncate'}</span>
        <span class="${metaFit ? 'ok' : 'warn'}">Meta ${metaLen} chars ${metaFit ? '· good for AI ✓' : (metaLen ? '· too thin for AI' : '· missing')}</span>
      </div>

      <h3>Technical</h3>
      <dl class="detail-grid">
        <dt>Status</dt><dd><span class="badge badge-${statusColor}">${d.status ?? ' - '}</span></dd>
        <dt>Indexable</dt><dd>${d.indexable === false ? 'No - ' + esc(d.indexability_reason || '') : 'Yes'}</dd>
        <dt>Canonical</dt><dd>${esc(d.canonical || ' - ')}</dd>
        <dt>Meta Robots</dt><dd>${esc(d.meta_robots || ' - ')}</dd>
        <dt>X-Robots-Tag</dt><dd>${esc(d.x_robots || ' - ')}</dd>
        <dt>H1</dt><dd>${esc(Array.isArray(d.h1) ? d.h1.join(' | ') : (d.h1 || ' - '))}</dd>
        <dt>Word count</dt><dd>${d.word_count ?? ' - '}</dd>
        <dt>Readability</dt><dd>${d.readability == null ? ' - ' : d.readability + ' (Flesch)'}</dd>
        <dt>Text / Code</dt><dd>${d.text_to_code == null ? ' - ' : Math.round(d.text_to_code * 100) + '%'}</dd>
        <dt>Forms</dt><dd>${d.forms_count ?? 0}</dd>
        <dt>Schema (JSON-LD)</dt><dd>${schemaTypes.length ? esc(schemaTypes.join(', ')) : ' - '}</dd>
        <dt>Microdata / RDFa</dt><dd>${microRdfa.length ? esc(microRdfa.join(', ')) : ' - '}</dd>
        <dt>Last-Modified</dt><dd>${esc(d.last_modified || ' - ')}</dd>
        <dt>Pagination</dt><dd>${(d.prev_url || d.next_url) ? `${d.prev_url ? 'prev ✓' : ''} ${d.next_url ? 'next ✓' : ''}`.trim() : ' - '}</dd>
        <dt>AMP</dt><dd>${d.amp_url ? esc(d.amp_url) : ' - '}</dd>
        <dt>Mobile alternate</dt><dd>${d.mobile_alternate ? esc(d.mobile_alternate) : ' - '}</dd>
        <dt>Cookies set</dt><dd>${(d.cookies && d.cookies.length) ? `${d.cookies.length} - ${esc(d.cookies.join(', '))}` : ' - '}</dd>
        <dt>Depth</dt><dd>${d.depth ?? ' - '}</dd>
        <dt>Inlinks / Outlinks</dt><dd>${inlinks.length} / ${outlinks.length}</dd>
        <dt>Internal authority</dt><dd>${d.pagerank == null ? ' - ' : d.pagerank + ' / 100 (PageRank)'}</dd>
        <dt>LCP / CLS</dt><dd>${d.lcp_s ?? ' - '}s / ${d.cls ?? ' - '}</dd>
        ${d.segment ? `<dt>Segment</dt><dd>${esc(d.segment)}</dd>` : ''}
        ${d.ga4 ? `<dt>GA4 (28d)</dt><dd>${d.ga4.sessions ?? 0} sessions · ${d.ga4.engagedSessions ?? 0} engaged · ${d.ga4.screenPageViews ?? 0} views · ${d.ga4.conversions ?? 0} conv.</dd>` : ''}
        ${d.pdf_properties ? `<dt>PDF</dt><dd>${d.pdf_properties.page_count ?? '?'} pages${d.pdf_properties.author ? ' · ' + esc(d.pdf_properties.author) : ''}${d.pdf_properties.producer ? ' · ' + esc(d.pdf_properties.producer) : ''}</dd>` : ''}
        ${(d.js_errors && d.js_errors.length) ? `<dt>JS console</dt><dd>${d.js_errors.length} error(s): ${esc(d.js_errors.slice(0, 3).join(' · '))}</dd>` : ''}
      </dl>
      ${(d.spelling && d.spelling.length) ? `
        <h3>Spelling &amp; grammar <span class="dr-tab-n">${d.spelling.length}</span></h3>
        <ul class="dr-spell">
          ${d.spelling.slice(0, 40).map(s => `<li>
            <span class="dr-spell-word">${esc(s.word)}</span>
            <span class="dr-spell-kind dr-spell-${s.kind === 'spelling' ? 'sp' : 'gr'}">${esc(s.kind)}</span>
            ${(s.suggestions && s.suggestions.length) ? `<span class="dr-spell-sug">→ ${esc(s.suggestions.slice(0, 3).join(', '))}</span>` : ''}
          </li>`).join('')}
        </ul>` : ''}`;

    const linkList = (items, render) => items.length
      ? `<ul class="dr-links">${items.map(render).join('')}</ul>`
      : `<p class="dr-empty">None found.</p>`;

    const inlinksHtml = linkList(inlinks, (r) =>
      `<li data-nav="${esc(r.address)}"><span class="mono">${esc(pathOf(r.address))}</span><span class="dr-link-title">${esc(r.title || '')}</span></li>`);

    const outlinksHtml = linkList(outlinks, (o) =>
      `<li${o.crawled ? ` data-nav="${esc(o.url)}"` : ''}><span class="mono">${esc(pathOf(o.url))}</span>${o.crawled ? '<span class="badge badge-passed">crawled</span>' : '<span class="badge badge-notice">external/uncrawled</span>'}</li>`);

    this.panel.innerHTML = `
      <div class="drawer-header">
        <div style="min-width:0;">
          <h2 class="dr-addr mono">${esc(d.address)}</h2>
        </div>
        <button class="drawer-close" aria-label="Close panel">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
      </div>
      <div class="dr-tabs">
        ${tabBtn('overview', 'Overview')}
        ${tabBtn('inlinks', 'Inlinks', inlinks.length)}
        ${tabBtn('outlinks', 'Outlinks', outlinks.length)}
        ${tabBtn('screenshot', 'Screenshot')}
      </div>
      <div class="drawer-content">
        <div class="dr-pane" data-pane="overview" ${this.tab === 'overview' ? '' : 'hidden'}>${overview}</div>
        <div class="dr-pane" data-pane="inlinks" ${this.tab === 'inlinks' ? '' : 'hidden'}>${inlinksHtml}</div>
        <div class="dr-pane" data-pane="outlinks" ${this.tab === 'outlinks' ? '' : 'hidden'}>${outlinksHtml}</div>
        <div class="dr-pane" data-pane="screenshot" ${this.tab === 'screenshot' ? '' : 'hidden'}>
          <div class="dr-shot-controls">
            <button class="dr-shot-dev${this.shotDevice === 'desktop' ? ' active' : ''}" data-dev="desktop">Desktop</button>
            <button class="dr-shot-dev${this.shotDevice === 'mobile' ? ' active' : ''}" data-dev="mobile">Mobile</button>
          </div>
          <div class="dr-shot"></div>
        </div>
      </div>`;

    this.panel.querySelector('.drawer-close').addEventListener('click', () => this.close());
    this.panel.querySelectorAll('.dr-tab').forEach(b =>
      b.addEventListener('click', () => { this.tab = b.dataset.tab; this.render(); }));
    this.panel.querySelectorAll('[data-nav]').forEach(li =>
      li.addEventListener('click', () => {
        const addr = li.dataset.nav;
        const row = this.allRows.find(r => norm(r.address) === norm(addr));
        if (row) this.open(row, this.allRows, this.onNavigate);
      }));
    this.panel.querySelectorAll('.dr-shot-dev').forEach(b =>
      b.addEventListener('click', () => { this.shotDevice = b.dataset.dev; this.render(); }));
    if (this.tab === 'screenshot') this._loadShot();
  }
}
