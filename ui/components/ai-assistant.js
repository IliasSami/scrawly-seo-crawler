// ai-assistant.js — a floating, minimally-intrusive analyst scoped to the
// active audit. It streams responses from /api/ai/chat (SSE) and only ever
// reasons over the current crawl's data or how to use Scrawly (the scope guard
// lives server-side in the system prompt). The provider key stays on the
// server; this component never sees it.
//
// Three states, driven by classes on .ai-root (never the [hidden] attribute,
// which a `display:` rule would override):
//   closed    → just the floating bubble (FAB)
//   open      → full chat panel
//   minimized → a slim docked bar (conversation preserved), less intrusive
//               than the panel but quicker to reopen than the bubble.

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// Minimal, safe markdown → HTML: bold, inline code, and line breaks. Everything
// is escaped first, so raw model output is never injected as HTML.
function mdToHtml(text) {
  let h = esc(text);
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/\n/g, '<br>');
  return h;
}

const SUGGESTIONS = [
  'Summarize this audit',
  'What should I fix first?',
  'Explain the health score',
];

const ICON_SPARK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 4.8L18.7 9.6l-4.8 1.9L12 16.3l-1.9-4.8L5.3 9.6l4.8-1.9L12 3z"></path></svg>';
const ICON_CLOSE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
const ICON_MIN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line></svg>';
const ICON_UP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"></polyline></svg>';
const ICON_SEND = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';

export class AiAssistant {
  /**
   * @param {object} opts
   * @param {string} opts.apiBase   e.g. "/api"
   * @param {() => {crawlId: any, label: string}} opts.getContext current audit
   * @param {() => void} [opts.onOpenSettings] jump to Settings → AI provider
   */
  constructor({ apiBase, getContext, onOpenSettings }) {
    this.api = apiBase;
    this.getContext = getContext || (() => ({ crawlId: null, label: '' }));
    this.onOpenSettings = onOpenSettings;
    this.messages = [];       // [{role, content}]
    this.state = 'closed';    // 'closed' | 'open' | 'minimized'
    this.streaming = false;
    this._mount();
  }

  _mount() {
    const root = document.createElement('div');
    root.className = 'ai-root';
    root.innerHTML = `
      <button class="ai-fab" aria-label="Ask the audit analyst" title="Ask AI about this audit">
        ${ICON_SPARK}
      </button>

      <button class="ai-dock" aria-label="Reopen audit analyst" title="Reopen">
        <span class="ai-dock-icon">${ICON_SPARK}</span>
        <span class="ai-dock-name">Audit Analyst</span>
        <span class="ai-dock-caret">${ICON_UP}</span>
      </button>

      <section class="ai-panel" role="dialog" aria-label="Audit AI assistant">
        <header class="ai-head">
          <div class="ai-head-title">
            <span class="ai-head-icon">${ICON_SPARK}</span>
            <div class="ai-head-meta">
              <div class="ai-head-name">Audit Analyst</div>
              <div class="ai-head-ctx" data-ctx></div>
            </div>
          </div>
          <div class="ai-head-actions">
            <button class="ai-min icon-btn" aria-label="Minimize" title="Minimize">${ICON_MIN}</button>
            <button class="ai-close icon-btn" aria-label="Close" title="Close">${ICON_CLOSE}</button>
          </div>
        </header>
        <div class="ai-msgs" data-msgs></div>
        <form class="ai-input">
          <textarea data-in rows="1" placeholder="Ask about this audit…" aria-label="Message"></textarea>
          <button type="submit" class="ai-send" aria-label="Send" disabled>${ICON_SEND}</button>
        </form>
      </section>`;
    document.body.appendChild(root);

    this.root = root;
    this.panel = root.querySelector('.ai-panel');
    this.msgsEl = root.querySelector('[data-msgs]');
    this.ctxEl = root.querySelector('[data-ctx]');
    this.input = root.querySelector('[data-in]');
    this.sendBtn = root.querySelector('.ai-send');

    root.querySelector('.ai-fab').addEventListener('click', () => this.openPanel());
    root.querySelector('.ai-dock').addEventListener('click', () => this.openPanel());
    root.querySelector('.ai-min').addEventListener('click', () => this.minimize());
    root.querySelector('.ai-close').addEventListener('click', () => this.close());
    root.querySelector('.ai-input').addEventListener('submit', (e) => {
      e.preventDefault();
      this._send(this.input.value);
    });
    this.input.addEventListener('input', () => {
      this.sendBtn.disabled = !this.input.value.trim() || this.streaming;
      this.input.style.height = 'auto';
      this.input.style.height = Math.min(120, this.input.scrollHeight) + 'px';
    });
    this.input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this._send(this.input.value); }
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.state === 'open') this.minimize();
    });

    this._renderEmpty();
    this._applyState();
  }

  _applyState() {
    this.root.classList.toggle('is-open', this.state === 'open');
    this.root.classList.toggle('is-min', this.state === 'minimized');
  }

  openPanel() {
    this.state = 'open';
    this._applyState();
    this._updateContext();
    requestAnimationFrame(() => { this.input.focus(); this._scroll(); });
  }

  minimize() {
    // Only meaningful once a conversation exists; otherwise just close.
    this.state = this.messages.length ? 'minimized' : 'closed';
    this._applyState();
  }

  close() {
    this.state = 'closed';
    this._applyState();
  }

  _updateContext() {
    const { label } = this.getContext();
    this.ctxEl.textContent = label ? `Analyzing: ${label}` : 'No audit loaded - open a project first';
  }

  /** Repaint the context line — call when the active crawl changes so an
   *  already-open panel doesn't show a stale "No audit loaded". */
  refreshContext() { this._updateContext(); }

  _clearWelcome() {
    if (!this._started) { this.msgsEl.innerHTML = ''; this._started = true; }
  }

  /** Post a plain assistant message (agent status / reports). Does not enter the
   *  chat history sent to the model. */
  say(text) {
    this.openPanel();
    this._clearWelcome();
    const el = this._bubble('assistant');
    el.innerHTML = mdToHtml(text);
    this._scroll();
    return el;
  }

  /** Ask a clarifying question with quick-reply options; resolves the chosen
   *  value. Used by the fix agent to confirm scope before writing. */
  ask(question, options) {
    return new Promise((resolve) => {
      this.openPanel();
      this._clearWelcome();
      const el = this._bubble('assistant');
      el.innerHTML = mdToHtml(question);
      const wrap = document.createElement('div');
      wrap.className = 'ai-opts';
      (options || []).forEach((o) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'ai-opt';
        b.textContent = o.label;
        b.addEventListener('click', () => {
          wrap.querySelectorAll('.ai-opt').forEach((x) => { x.disabled = true; });
          b.classList.add('chosen');
          const u = this._bubble('user');
          u.textContent = o.label;
          resolve(o.value);
        }, { once: true });
        wrap.appendChild(b);
      });
      el.appendChild(wrap);
      this._scroll();
    });
  }

  _renderEmpty() {
    this._started = false;
    this.msgsEl.innerHTML = `
      <div class="ai-welcome">
        <div class="ai-welcome-icon">${ICON_SPARK}</div>
        <p class="ai-welcome-lead">Ask me about the current audit.</p>
        <p class="ai-welcome-sub">I read this crawl's pages, issues and metrics - and I can explain how to use Scrawly.</p>
        <div class="ai-suggest">
          ${SUGGESTIONS.map((s) => `<button type="button" class="ai-chip" data-suggest="${esc(s)}">${esc(s)}</button>`).join('')}
        </div>
      </div>`;
    this.msgsEl.querySelectorAll('[data-suggest]').forEach((b) =>
      b.addEventListener('click', () => this._send(b.dataset.suggest)));
  }

  _bubble(role) {
    const el = document.createElement('div');
    el.className = `ai-msg ai-${role}`;
    this.msgsEl.appendChild(el);
    this._scroll();
    return el;
  }

  _scroll() { this.msgsEl.scrollTop = this.msgsEl.scrollHeight; }

  async _send(text) {
    text = (text || '').trim();
    if (!text || this.streaming) return;

    this._clearWelcome();

    this.messages.push({ role: 'user', content: text });
    const userEl = this._bubble('user');
    userEl.textContent = text;

    this.input.value = '';
    this.input.style.height = 'auto';
    this.sendBtn.disabled = true;
    this.streaming = true;

    const botEl = this._bubble('assistant');
    botEl.innerHTML = '<span class="ai-typing"><i></i><i></i><i></i></span>';

    let acc = '';
    try {
      await this._stream(this.messages, (delta) => {
        acc += delta;
        botEl.innerHTML = mdToHtml(acc);
        this._scroll();
      });
      if (acc.trim()) {
        this.messages.push({ role: 'assistant', content: acc });
      } else {
        botEl.innerHTML = '<span class="ai-muted">No response.</span>';
      }
    } catch (err) {
      this._renderError(botEl, String(err && err.message ? err.message : err));
    } finally {
      this.streaming = false;
      this.sendBtn.disabled = !this.input.value.trim();
      this._scroll();
    }
  }

  _renderError(el, msg) {
    const unconfigured = /not configured/i.test(msg);
    el.innerHTML = `<div class="ai-error">${esc(msg)}</div>`;
    if (unconfigured && this.onOpenSettings) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'ai-chip';
      b.textContent = 'Open AI settings';
      b.addEventListener('click', () => { this.close(); this.onOpenSettings(); });
      el.querySelector('.ai-error').appendChild(b);
    }
  }

  // POST to the SSE endpoint and pump text deltas to `onDelta`.
  async _stream(messages, onDelta) {
    const { crawlId } = this.getContext();
    const res = await fetch(`${this.api}/ai/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ crawl_id: crawlId, messages }),
    });
    if (!res.ok || !res.body) throw new Error(`Request failed (${res.status})`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let serverError = null;

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep;
      while ((sep = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const line = frame.split('\n').find((l) => l.startsWith('data:'));
        if (!line) continue;
        let payload;
        try { payload = JSON.parse(line.slice(5).trim()); } catch { continue; }
        if (payload.delta) onDelta(payload.delta);
        else if (payload.error) serverError = payload.error;
      }
    }
    if (serverError) throw new Error(serverError);
  }
}
