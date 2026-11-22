// ui/components/crawl-console.js
// A persistent, global live-crawl console. Mounted once at app root (outside the
// view sections) so it survives navigation between screens. Streams real crawl
// discovery: progress, counts, speed, status tally, in-flight URLs, and a live
// feed of pages as they're crawled.
import { esc } from './escape.js';
import { toast } from './toast.js';

const STATUS_CLASS = (code) => {
  if (!code) return 'err';
  if (code >= 500) return 's5';
  if (code >= 400) return 's4';
  if (code >= 300) return 's3';
  return 's2';
};
const hostOf = (u) => { try { return new URL(u).host; } catch { return u; } };
const pathOf = (u) => { try { const x = new URL(u); return (x.pathname + x.search) || '/'; } catch { return u; } };

export function formatCrawlProgress(status) {
  if (status.discovered == null) return `${status.url_count ?? 0} pages`;
  return `${status.processed ?? status.crawled ?? status.url_count ?? 0} processed · ${status.discovered} discovered`;
}

export function isPartialCrawl(status) {
  return Boolean(status?.resumable || (status?.phase
    && !['legacy', 'complete'].includes(status.phase)));
}

export class CrawlConsole {
  constructor(apiBase, { onView, onResume, onStopped } = {}) {
    this.apiBase = apiBase;
    this.onView = onView || (() => {});
    this.onResume = onResume || (() => {});
    this.onStopped = onStopped || (() => {});
    this.crawlId = null;
    this.timer = null;
    this.done = false;
    this._mount();
  }

  _mount() {
    const el = document.createElement('div');
    el.id = 'crawl-console';
    el.className = 'cc hidden';
    el.innerHTML = `
      <button class="cc-pill" type="button" aria-label="Show crawl console">
        <span class="cc-pill-dot"></span>
        <span class="cc-pill-label">Crawling</span>
        <span class="cc-pill-pct">0%</span>
      </button>
      <div class="cc-panel" role="dialog" aria-label="Live crawl console">
        <header class="cc-head">
          <div class="cc-head-main">
            <span class="cc-live"><span class="cc-live-dot"></span> LIVE</span>
            <span class="cc-target">Crawl</span>
          </div>
          <div class="cc-head-actions">
            <button class="cc-min" type="button" title="Minimize" aria-label="Minimize">–</button>
            <button class="cc-close" type="button" title="Hide" aria-label="Hide">✕</button>
          </div>
        </header>

        <div class="cc-phase"><span class="cc-phase-label">Starting…</span><span class="cc-elapsed"></span></div>
        <div class="cc-bar"><div class="cc-bar-fill" style="width:0%"></div></div>

        <div class="cc-metrics">
          <div class="cc-metric"><div class="cc-metric-val" data-k="processed">0</div><div class="cc-metric-label">Processed</div></div>
          <div class="cc-metric"><div class="cc-metric-val" data-k="discovered">0</div><div class="cc-metric-label">Discovered</div></div>
          <div class="cc-metric"><div class="cc-metric-val" data-k="queue">0</div><div class="cc-metric-label">Queued</div></div>
          <div class="cc-metric"><div class="cc-metric-val" data-k="pps">0</div><div class="cc-metric-label">Pages/s</div></div>
        </div>

        <div class="cc-tally"></div>

        <div class="cc-section-label">Now crawling</div>
        <ul class="cc-active"></ul>

        <div class="cc-section-label">Recently crawled</div>
        <ul class="cc-recent"></ul>

        <div class="cc-done hidden">
          <div class="cc-done-check">✓</div>
          <div class="cc-done-text">Crawl complete</div>
        </div>
        <div class="cc-actions" hidden>
          <button class="cc-view btn btn-secondary" type="button">View saved pages</button>
          <button class="cc-resume btn btn-primary" type="button">Resume audit</button>
        </div>
      </div>`;
    document.body.appendChild(el);
    this.el = el;
    const $ = (s) => el.querySelector(s);
    $('.cc-min').addEventListener('click', () => this._setMin(true));
    $('.cc-close').addEventListener('click', () => this.hide());
    $('.cc-pill').addEventListener('click', () => this._setMin(false));
    $('.cc-view').addEventListener('click', () => { this.onView(this.crawlId, this.partial); this.hide(); });
    $('.cc-resume').addEventListener('click', (e) => this.onResume(this.crawlId, e.currentTarget));
  }

  start(crawlId, onComplete) {
    this.crawlId = crawlId;
    this.done = false;
    // Optional per-run completion hook (e.g. the public window auto-advances to
    // results). Cleared each start so a normal crawl doesn't inherit it.
    this._onComplete = onComplete || null;
    this._unknown = 0;
    this._pollToken = (this._pollToken ?? 0) + 1;
    this.partial = true;
    this.el.classList.remove('hidden');
    this._setMin(false);
    this.el.querySelector('.cc-done').classList.add('hidden');
    this.el.querySelector('.cc-panel').classList.remove('cc-complete');
    this.el.querySelector('.cc-actions').hidden = true;
    this.el.querySelector('.cc-pill-label').textContent = 'Crawling';
    this.el.querySelector('.cc-target').textContent = 'Crawl';
    this._render({ status: 'Starting…' });
    if (this.timer) clearTimeout(this.timer);
    this._poll();
  }

  // Closing the panel only hides it: a running crawl keeps being tracked so its
  // results still open (and the completion hook still fires) when it finishes.
  hide() {
    this.el.classList.add('hidden');
    if (this.done && this.timer) { clearTimeout(this.timer); this.timer = null; }
  }

  _setMin(min) { this.el.classList.toggle('cc-min-on', min); }

  async _poll() {
    if (this.crawlId == null) return;
    const token = this._pollToken;
    try {
      const response = await fetch(`${this.apiBase}/audit/status/${this.crawlId}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const s = await response.json();
      if (token !== this._pollToken) return;
      this._render(s);
      const done = s.phase === 'complete' || s.status === 'Complete' || s.progress >= 100;
      const failed = s.phase === 'failed' || (s.status || '').startsWith('Failed');
      if (done && !this.done) { this.done = true; this._renderDone(); return; }
      if (failed || s.phase === 'interrupted') { this.done = true; this._renderStopped(s); return; }
      // "Unknown" means the engine isn't tracking this crawl (e.g. the app was
      // restarted mid-crawl). Give it a few seconds, then say so instead of
      // spinning forever.
      this._unknown = s.status === 'Unknown' ? (this._unknown || 0) + 1 : 0;
      if (this._unknown >= 12) { this.done = true; this._renderStopped(s); return; }
      if (!done) this.timer = setTimeout(() => this._poll(), 700);
    } catch (e) {
      if (token === this._pollToken) this.timer = setTimeout(() => this._poll(), 1500);
    }
  }

  _render(s) {
    const el = this.el, $ = (q) => el.querySelector(q);
    const pct = Math.max(0, Math.min(100, s.progress || 0));
    $('.cc-bar-fill').style.width = pct + '%';
    $('.cc-pill-pct').textContent = pct + '%';
    if (s.target) $('.cc-target').textContent = hostOf(s.target);

    const phaseLabel = {
      crawl: 'Finding and crawling pages', enrich: 'Adding Google data',
      store: 'Saving results', audit: 'Checking your pages',
      complete: 'Complete', failed: 'Crawl stopped', interrupted: 'Crawl interrupted',
    }[s.phase] || (s.status === 'Unknown' ? 'Waiting…' : (s.status || ''));
    $('.cc-phase-label').textContent = phaseLabel;
    $('.cc-elapsed').textContent = s.elapsed_s != null ? `${s.elapsed_s}s` : '';

    const set = (k, v) => { const n = el.querySelector(`[data-k="${k}"]`); if (n) n.textContent = v; };
    set('processed', s.processed ?? s.crawled ?? 0);
    set('discovered', s.discovered ?? 0);
    set('queue', s.queue ?? 0);
    set('pps', s.pages_per_sec ?? 0);
    this._setActions((s.url_count ?? s.crawled ?? 0) > 0, s.resumable === true);

    // Status tally chips
    const tally = s.status_tally || {};
    const order = [['2xx', 's2'], ['3xx', 's3'], ['4xx', 's4'], ['5xx', 's5'], ['err', 'err']];
    $('.cc-tally').innerHTML = order
      .filter(([k]) => tally[k])
      .map(([k, cls]) => `<span class="cc-chip cc-${cls}">${tally[k]} ${k}</span>`)
      .join('') || '<span class="cc-chip cc-muted">no responses yet</span>';

    // Now crawling (in-flight)
    const active = s.active || [];
    $('.cc-active').innerHTML = active.length
      ? active.slice(0, 8).map(u =>
          `<li class="cc-active-item"><span class="cc-spin"></span><span class="cc-url mono">${esc(pathOf(u))}</span></li>`).join('')
      : '<li class="cc-empty">idle…</li>';

    // Recent feed (newest first), staggered entrance
    const recent = s.recent || [];
    $('.cc-recent').innerHTML = recent.slice(0, 12).map((r, i) =>
      `<li class="cc-recent-item" style="--i:${i}">
         <span class="cc-code cc-${STATUS_CLASS(r.status)}">${esc(r.status || ' - ')}</span>
         <span class="cc-url mono" title="${esc(r.url)}">${esc(pathOf(r.url))}</span>
         <span class="cc-depth" title="Clicks from the start page">depth ${esc(r.depth)}</span>
       </li>`).join('') || '<li class="cc-empty">waiting for first page…</li>';
  }

  _renderDone() {
    const el = this.el;
    el.querySelector('.cc-bar-fill').style.width = '100%';
    el.querySelector('.cc-panel').classList.add('cc-complete');
    el.querySelector('.cc-done').classList.remove('hidden');
    el.querySelector('.cc-phase-label').textContent = 'Complete';
    el.querySelector('.cc-pill-label').textContent = 'Complete';
    this.partial = false;
    this._setActions(true, false);
    this._setMin(false);
    toast.show('Crawl complete. Your results are ready.', 'success');
    if (this._onComplete) { const cb = this._onComplete; this._onComplete = null; cb(this.crawlId); }
  }

  _setActions(view, resume) {
    const actions = this.el.querySelector('.cc-actions');
    const viewButton = actions.querySelector('.cc-view');
    viewButton.textContent = this.partial ? 'View saved pages' : 'View results →';
    viewButton.hidden = !view;
    actions.querySelector('.cc-resume').hidden = !resume;
    actions.hidden = !view && !resume;
  }

  _renderStopped(s) {
    const el = this.el;
    el.querySelector('.cc-phase-label').textContent = 'Crawl interrupted';
    el.querySelector('.cc-pill-label').textContent = 'Interrupted';
    this.onStopped(this.crawlId);
    toast.show(s.resumable ? 'The crawl stopped. You can resume this audit.'
      : 'The crawl stopped before the audit completed.', 'warning');
  }
}
