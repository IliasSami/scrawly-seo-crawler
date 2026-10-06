import { toast } from './toast.js';
// ui/components/agentic-view.js
// Agentic Checks — origin-level AI-agent readiness.
//
// This view is deliberately shaped differently from the page-level Issues hub:
// there is exactly ONE result per capability for the whole origin, so it reads
// as a scored checklist rather than a table of affected URLs. Each row expands
// to the literal request/response trail that produced the verdict, because
// "your API catalog is missing" is only trustworthy if you can see the 404.

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const STATUS = {
  pass:           { label: 'Pass',      cls: 'ag-pass' },
  fail:           { label: 'Fail',      cls: 'ag-fail' },
  info:           { label: 'Info',      cls: 'ag-info' },
  not_applicable: { label: 'N/A',       cls: 'ag-na' },
  error:          { label: 'Not run',   cls: 'ag-err' },
};

/** Score ring — same visual language as the dashboard health ring. */
function ring(score, size = 108) {
  const r = (size - 14) / 2, c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  const tone = score >= 80 ? 'var(--color-passed)'
    : score >= 50 ? 'var(--color-warning)' : 'var(--color-critical)';
  return `<svg class="ag-ring" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" aria-hidden="true">
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none"
            stroke="var(--border-color)" stroke-width="9"/>
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none"
            stroke="${tone}" stroke-width="9" stroke-linecap="round"
            stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - pct)}"
            transform="rotate(-90 ${size / 2} ${size / 2})"/>
    <text x="50%" y="50%" text-anchor="middle" dy="0.36em"
          font-size="${size * 0.3}" font-weight="700"
          fill="var(--text-primary)">${score}</text>
  </svg>`;
}

function stepRow(s) {
  const code = s.status == null ? '' :
    `<span class="ag-code ag-code-${String(s.status)[0]}xx">${s.status}</span>`;
  const hdrs = Object.entries(s.response_headers || {});
  return `<div class="ag-step ${s.ok === false ? 'is-bad' : s.ok ? 'is-ok' : ''}">
    <div class="ag-step-head">
      <span class="ag-step-act mono">${esc(s.action)}</span>${code}
    </div>
    ${s.detail ? `<div class="ag-step-detail">${esc(s.detail)}</div>` : ''}
    ${hdrs.length ? `<div class="ag-step-hdrs mono">${hdrs.slice(0, 6)
      .map(([k, v]) => `<span><b>${esc(k)}</b>: ${esc(String(v).slice(0, 120))}</span>`)
      .join('')}</div>` : ''}
    ${s.body_excerpt ? `<pre class="ag-step-body">${esc(s.body_excerpt.slice(0, 600))}</pre>` : ''}
  </div>`;
}

function probeRow(r) {
  const st = STATUS[r.status] || STATUS.error;
  const hasPrompt = !!r.fix_prompt;
  return `<details class="ag-probe" data-probe="${esc(r.probe_id)}">
    <summary class="ag-probe-sum">
      <span class="ag-badge ${st.cls}">${st.label}</span>
      <span class="ag-probe-title">${esc(r.title)}</span>
      <span class="ag-probe-concl">${esc(r.conclusion)}</span>
      <span class="ag-probe-ms">${r.duration_ms || 0}ms</span>
    </summary>
    <div class="ag-probe-body">
      <div class="ag-goal"><b>Goal</b> ${esc(r.goal)}</div>
      ${r.remediation ? `<div class="ag-remedy"><b>How to fix</b> ${esc(r.remediation)}</div>` : ''}
      ${r.spec_urls?.length ? `<div class="ag-specs">${r.spec_urls.map(u =>
        `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\//, '').slice(0, 60))}</a>`
      ).join('')}</div>` : ''}
      ${hasPrompt ? `<div class="ag-prompt-wrap">
        <div class="ag-prompt-head">
          <span>Agent fix prompt</span>
          <button class="btn btn-secondary ag-copy" data-probe="${esc(r.probe_id)}">Copy prompt</button>
        </div>
        <pre class="ag-prompt mono">${esc(r.fix_prompt)}</pre>
      </div>` : ''}
      <div class="ag-trail">
        <div class="ag-trail-h">Audit trail - what we actually requested</div>
        ${(r.steps || []).map(stepRow).join('')}
      </div>
    </div>
  </details>`;
}

export class AgenticView {
  constructor(container, { apiBase = '/api' } = {}) {
    this.container = container;
    this.apiBase = apiBase;
    this.data = null;
    this.crawlId = null;
    this.filter = 'actionable';
  }

  async load(crawlId) {
    this.crawlId = crawlId;
    if (!crawlId) return this._empty('Open a project to see its agentic readiness.');
    this._loading();
    try {
      const res = await fetch(`${this.apiBase}/agentic/${crawlId}`);
      this.data = await res.json();
    } catch {
      return this._empty('Could not load the agentic report.');
    }
    if (!this.data?.available) {
      return this._empty(
        'No agentic report for this crawl yet - it predates the Agentic Checks pass.',
        true);
    }
    this.render();
  }

  async rerun() {
    if (!this.crawlId) return;
    const btn = this.container.querySelector('.ag-rerun');
    if (btn) { btn.disabled = true; btn.textContent = 'Re-probing…'; }
    try {
      const res = await fetch(`${this.apiBase}/agentic/${this.crawlId}/rerun`,
                              { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      this.data = await res.json();
      this.render();
    } catch {
      if (btn) { btn.disabled = false; btn.textContent = 'Re-run checks'; }
      toast.show('Could not run the checks again. Please try again.', 'error');
    }
  }

  _loading() {
    this.container.innerHTML =
      `<div class="ag-empty"><div class="ag-spin"></div>Probing agentic readiness…</div>`;
  }

  _empty(msg, offerRun = false) {
    this.container.innerHTML = `<div class="ag-empty">
      <p>${esc(msg)}</p>
      ${offerRun ? `<button class="btn btn-primary ag-rerun">Run agentic checks</button>` : ''}
    </div>`;
    this._wire();
  }

  render() {
    const d = this.data;
    const results = d.results || [];
    const actionable = results.filter(r => r.status === 'fail' || r.status === 'info');
    const shown = this.filter === 'all' ? results
      : this.filter === 'passed' ? results.filter(r => r.status === 'pass')
        : actionable;

    // Group by category, preserving the server's ordering.
    const groups = [];
    for (const r of shown) {
      let g = groups.find(x => x.label === r.category_label);
      if (!g) groups.push(g = { label: r.category_label, rows: [] });
      g.rows.push(r);
    }
    const catScore = (label) =>
      (d.categories || []).find(c => c.label === label) || null;

    this.container.innerHTML = `
      <div class="ag-page">
        <div class="ag-head">
          <div class="ag-head-main">
            <h1>Agentic Checks</h1>
            <p>Can an AI agent discover, read, authenticate against and transact
               with this site? Probes the origin root only - a fixed set of
               requests, independent of site size.</p>
            <div class="ag-origin mono">${esc(d.origin || '')}</div>
          </div>
          <button class="btn btn-secondary ag-rerun">Re-run checks</button>
        </div>

        <div class="card ag-hero">
          <div class="ag-hero-score">
            ${ring(d.score ?? 0)}
            <div class="ag-level">
              <div class="ag-level-name">${esc(d.level || '')}</div>
              <div class="ag-level-label">${esc(d.level_label || '')}</div>
              <div class="ag-level-sub">${Number(d.passed) || 0}/${Number(d.scored) || 0} checks passed</div>
            </div>
          </div>
          <div class="ag-cats">
            ${(d.categories || []).map(c => {
              const na = c.score === null || c.total === 0;
              return `<div class="ag-cat ${na ? 'is-na' : ''}">
                <div class="ag-cat-top">
                  <span class="ag-cat-label">${esc(c.label)}</span>
                  <span class="ag-cat-score">${na ? 'Not checked' : c.score + '%'}</span>
                </div>
                <div class="ag-bar"><div class="ag-bar-fill" style="width:${na ? 0 : c.score}%"></div></div>
                <div class="ag-cat-sub">${na ? 'no applicable checks' : `${c.passed}/${c.total} passed`}</div>
              </div>`;
            }).join('')}
          </div>
        </div>

        ${d.is_commerce ? '' : `<div class="ag-note">
          No e-commerce signals detected on this origin, so agentic-commerce
          protocols are shown for reference and do not affect the score.</div>`}

        <div class="ag-filters">
          ${[['actionable', `Needs action (${actionable.length})`],
             ['passed', `Passing (${results.filter(r => r.status === 'pass').length})`],
             ['all', `All (${results.length})`]]
            .map(([k, l]) => `<button class="ag-filter ${this.filter === k ? 'is-on' : ''}"
                 data-filter="${k}">${l}</button>`).join('')}
        </div>

        ${groups.length ? groups.map(g => {
          const cs = catScore(g.label);
          return `<section class="ag-group">
            <div class="ag-group-head">
              <h2>${esc(g.label)}</h2>
              ${cs && cs.total ? `<span class="ag-group-score">${cs.passed}/${cs.total}</span>` : ''}
            </div>
            ${g.rows.map(probeRow).join('')}
          </section>`;
        }).join('') : `<div class="ag-empty"><p>Nothing in this filter.</p></div>`}
      </div>`;
    this._wire();
  }

  _wire() {
    const $ = (s) => this.container.querySelectorAll(s);
    $('.ag-rerun').forEach(b => b.addEventListener('click', () => this.rerun()));
    $('.ag-filter').forEach(b => b.addEventListener('click', () => {
      this.filter = b.dataset.filter;
      this.render();
    }));
    $('.ag-copy').forEach(b => b.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const row = (this.data?.results || []).find(r => r.probe_id === b.dataset.probe);
      if (!row?.fix_prompt) return;
      try {
        await navigator.clipboard.writeText(row.fix_prompt);
        const was = b.textContent;
        b.textContent = 'Copied ✓';
        b.classList.add('is-copied');
        setTimeout(() => { b.textContent = was; b.classList.remove('is-copied'); }, 1600);
      } catch {
        b.textContent = 'Press ⌘C';
      }
    }));
  }
}
