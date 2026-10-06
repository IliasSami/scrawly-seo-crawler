// ui/components/integrations-panel.js
// Integrations — Google (one consent for Search Console + GA4), embeddings,
// spelling, authenticated crawling, and backlink providers.
//
// Everything here reports whether a credential exists, never what it is: secrets
// live in .env and are read server-side only (Invariant I5).
import { toast } from './toast.js';
import { openExternal } from './external.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

export class IntegrationsPanel {
  constructor(container, apiBase) {
    this.el = container;
    this.api = apiBase;
    this.state = {};
    this._shell();
  }

  _shell() {
    this.el.innerHTML = `
      <div class="card int-card" data-k="google">
        <div class="int-head">
          <h3>Google <span class="cfg-hint">Search Console + Analytics 4 - one connection</span></h3>
          <span class="int-badge" data-badge="google">…</span>
        </div>
        <div class="int-body" data-body="google">Loading…</div>
      </div>

      <div class="card int-card" data-k="embeddings">
        <div class="int-head">
          <h3>Embeddings <span class="cfg-hint">semantic similarity + low-relevance content</span></h3>
          <span class="int-badge" data-badge="embeddings">…</span>
        </div>
        <div class="int-body" data-body="embeddings">Loading…</div>
      </div>

      <div class="card int-card" data-k="spelling">
        <div class="int-head">
          <h3>Spelling &amp; grammar <span class="cfg-hint">content-area text</span></h3>
          <span class="int-badge" data-badge="spelling">…</span>
        </div>
        <div class="int-body" data-body="spelling">Loading…</div>
      </div>

      <div class="card int-card" data-k="auth">
        <div class="int-head">
          <h3>Authenticated crawling <span class="cfg-hint">web-form login</span></h3>
          <span class="int-badge" data-badge="auth">…</span>
        </div>
        <div class="int-body" data-body="auth">Loading…</div>
      </div>

      <div class="card int-card" data-k="backlinks">
        <div class="int-head">
          <h3>Backlinks <span class="cfg-hint">bring your own subscription</span></h3>
          <span class="int-badge" data-badge="backlinks">…</span>
        </div>
        <div class="int-body" data-body="backlinks">Loading…</div>
      </div>`;
  }

  _badge(key, text, cls) {
    const el = this.el.querySelector(`[data-badge="${key}"]`);
    if (el) { el.textContent = text; el.className = `int-badge ${cls}`; }
  }
  _body(key, html) {
    const el = this.el.querySelector(`[data-body="${key}"]`);
    if (el) el.innerHTML = html;
  }
  async _get(path) { try { return await (await fetch(`${this.api}${path}`)).json(); } catch { return {}; } }

  async load() {
    await Promise.all([
      this._loadGoogle(), this._loadEmbeddings(), this._loadSpelling(),
      this._loadAuth(), this._loadBacklinks(),
    ]);
  }

  // ---- Google (GSC + GA4) ----
  async _loadGoogle() {
    const s = await this._get('/oauth/google/status');
    this.state.google = s;
    if (!s.client_configured) {
      this._badge('google', 'Not set up', 'warn');
      this._body('google', `<p class="int-note">No OAuth client found. Add the Google Cloud Console
        client JSON at <code>secrets/google_oauth_client.json</code>, then reload.</p>`);
      return;
    }
    if (!s.connected) {
      this._badge('google', 'Not connected', '');
      this._body('google', `
        <p class="int-note">Connect once to enable Search Console <em>and</em> Analytics 4. You'll be
        sent to Google to approve read-only access; the token is encrypted on this machine and never
        leaves it.</p>
        <details class="int-details"><summary>Getting <code>Error 403: access_denied</code>?</summary>
          <p class="int-note">Your Cloud Console OAuth screen is in <b>Testing</b> mode. Either add your
          email under <b>OAuth consent screen → Test users</b> (tokens expire weekly), or - recommended
          for self-hosting - <b>Publish the app</b> there (one-time "unverified" warning, tokens then
          persist). These read-only scopes don't require Google's verification review.</p></details>
        <div class="int-actions"><button class="btn btn-primary" id="int-g-connect">Connect Google</button></div>`);
      this.el.querySelector('#int-g-connect')?.addEventListener('click', () => this._connectGoogle());
      return;
    }
    this._badge('google', 'Connected', 'ok');
    const props = await this._get('/google/properties');
    const gsc = props.gsc_sites || [];
    const ga4 = props.ga4_properties || [];
    this._body('google', `
      <div class="int-row"><span>Account</span><b>${esc(s.email || 'connected')}</b></div>
      <div class="int-row"><span>Search Console</span><b>${gsc.length} propert${gsc.length === 1 ? 'y' : 'ies'}</b></div>
      ${gsc.length ? `<ul class="int-list">${gsc.slice(0, 8).map(x => `<li class="mono">${esc(x)}</li>`).join('')}</ul>` : ''}
      <div class="int-row"><span>Analytics 4</span><b>${ga4.length} propert${ga4.length === 1 ? 'y' : 'ies'}</b></div>
      ${ga4.length ? `<ul class="int-list">${ga4.slice(0, 8).map(p =>
        `<li><span class="mono">${esc(p.property_id)}</span> - ${esc(p.display_name)} <span class="cfg-hint">${esc(p.account)}</span></li>`).join('')}</ul>
       <p class="int-note">Put a property ID in <b>Configuration → APIs → GA4 property</b> to enrich a crawl.</p>` : ''}
      <div class="int-actions"><button class="btn btn-secondary" id="int-g-disconnect">Disconnect</button></div>`);
    this.el.querySelector('#int-g-disconnect')?.addEventListener('click', async () => {
      if (!confirm('Disconnect Google? Scrawly will revoke the token and forget it.')) return;
      await fetch(`${this.api}/oauth/google/disconnect`, { method: 'POST' });
      toast.show('Google disconnected.', 'success');
      this._loadGoogle();
    });
  }

  async _connectGoogle() {
    if (this._gPoll) return;   // already waiting for approval
    const d = await this._get('/oauth/google/start');
    if (!d.auth_url) { toast.show(d.detail || 'Could not start the Google connection.', 'error'); return; }
    // Google must be approved by the person in their own browser (the desktop
    // window can't open one itself), then we poll until the callback lands.
    openExternal(d.auth_url);
    toast.show('Approve access in your browser. This page updates automatically.', 'info');
    const started = Date.now();
    this._gPoll = setInterval(async () => {
      const s = await this._get('/oauth/google/status');
      if (s.connected) {
        clearInterval(this._gPoll); this._gPoll = null;
        toast.show('Google connected!', 'success');
        this._loadGoogle();
      } else if (Date.now() - started > 180000) {   // give up after 3 min
        clearInterval(this._gPoll); this._gPoll = null;
        toast.show('Google approval timed out. Click Connect to try again.', 'warning');
      }
    }, 2000);
  }

  // ---- Embeddings ----
  async _loadEmbeddings() {
    const s = await this._get('/embeddings/status');
    if (!s.configured) {
      this._badge('embeddings', 'Not configured', '');
      this._body('embeddings', `
        <p class="int-note">Semantic similarity needs an <b>embeddings</b> endpoint - most chat
        providers don't serve one. Add to <code>.env</code> and restart:</p>
        <pre class="int-pre">SCRAWLY_EMBED_BASE_URL=https://api.openai.com/v1
SCRAWLY_EMBED_MODEL=text-embedding-3-small
SCRAWLY_EMBED_KEY=sk-...</pre>
        <p class="int-note">Local alternative (no key, nothing leaves your machine):
        <code>ollama pull nomic-embed-text</code> → base URL <code>http://localhost:11434/v1</code>.</p>`);
      return;
    }
    this._badge('embeddings', 'Configured', 'ok');
    this._body('embeddings', `
      <div class="int-row"><span>Endpoint</span><b class="mono">${esc(s.base_url)}</b></div>
      <div class="int-row"><span>Model</span><b class="mono">${esc(s.model)}</b></div>
      <div class="int-row"><span>API key</span><b>${s.api_key_set ? 'set' : 'none (local)'}</b></div>
      <div class="int-actions"><button class="btn btn-secondary" id="int-emb-test">Test embeddings</button>
        <span id="int-emb-res" class="cfg-hint"></span></div>`);
    this.el.querySelector('#int-emb-test')?.addEventListener('click', async () => {
      const out = this.el.querySelector('#int-emb-res');
      out.textContent = 'Testing…';
      try {
        const r = await (await fetch(`${this.api}/embeddings/test`, { method: 'POST' })).json();
        out.textContent = r.ok ? `✓ ${r.model} - ${r.dimensions} dimensions` : `✗ ${r.detail}`;
        out.style.color = r.ok ? 'var(--color-passed)' : 'var(--color-critical)';
      } catch { out.textContent = '✗ request failed'; }
    });
  }

  // ---- Spelling ----
  async _loadSpelling() {
    const s = await this._get('/spelling/status');
    const mode = s.mode || 'none';
    this._badge('spelling', mode === 'local' ? 'Local (unlimited)' : mode === 'public' ? 'Public API' : 'Unavailable',
      mode === 'local' ? 'ok' : mode === 'public' ? 'warn' : '');
    this._body('spelling', `
      <div class="int-row"><span>Backend</span><b>${mode === 'local' ? 'Local LanguageTool' : mode === 'public' ? 'LanguageTool public API' : 'Not installed'}</b></div>
      ${s.note ? `<p class="int-note">${esc(s.note)}</p>` : ''}
      <p class="int-note">Enable per crawl under <b>Configuration → Content</b>.</p>`);
  }

  // ---- Authenticated crawling ----
  async _loadAuth() {
    const s = await this._get('/auth/form/status');
    this._badge('auth', s.configured ? 'Configured' : 'Not configured', s.configured ? 'ok' : '');
    this._body('auth', s.configured ? `
      <div class="int-row"><span>Login URL</span><b class="mono">${esc(s.login_url)}</b></div>
      <div class="int-row"><span>User</span><b>${esc(s.user)}</b></div>
      <div class="int-row"><span>Password</span><b>${s.password_set ? 'set (in .env)' : 'missing'}</b></div>
      <p class="int-note">⚠ ${esc(s.note || '')}</p>
      <p class="int-note">Enable per crawl under <b>Configuration → Spider</b>. Logout, delete and
      wp-admin links are excluded automatically.</p>` : `
      <p class="int-note">Crawl pages behind a login. Add to <code>.env</code> and restart - use a
      <b>scoped throwaway account</b>, never an admin:</p>
      <pre class="int-pre">SCRAWLY_FORM_LOGIN_URL=https://example.com/wp-login.php
SCRAWLY_FORM_USER=...
SCRAWLY_FORM_PASS=...</pre>`);
  }

  // ---- Backlinks ----
  async _loadBacklinks() {
    const s = await this._get('/backlinks/status');
    const provs = s.providers || [];
    this._badge('backlinks', s.any_connected ? 'Connected' : 'Bring your own', s.any_connected ? 'ok' : '');
    this._body('backlinks', `
      <p class="int-note">No backlink API is free - each needs your own subscription. Scrawly ships
      the connection, not the credential.</p>
      ${provs.map(p => `
        <div class="int-prov">
          <div class="int-row">
            <span>${esc(p.label)}</span>
            <b class="${p.connected ? 'int-ok' : ''}">${p.connected ? '✓ connected' : 'not connected'}</b>
          </div>
          <div class="cfg-hint">${esc(p.note)} · env: <code>${p.env.join(', ')}</code>
            · <a href="${esc(p.signup)}" target="_blank" rel="noopener noreferrer">get a key</a></div>
          ${p.connected ? `<button class="btn btn-secondary btn-sm int-bl-test" data-p="${p.id}">Test</button>
            <span class="cfg-hint" data-blres="${p.id}"></span>` : ''}
        </div>`).join('')}`);
    this.el.querySelectorAll('.int-bl-test').forEach(b => b.addEventListener('click', async () => {
      const id = b.dataset.p;
      const out = this.el.querySelector(`[data-blres="${id}"]`);
      out.textContent = 'Testing…';
      try {
        const r = await (await fetch(`${this.api}/backlinks/test`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ provider: id }),
        })).json();
        out.textContent = r.ok ? '✓ credential accepted' : `✗ ${r.detail}`;
        out.style.color = r.ok ? 'var(--color-passed)' : 'var(--color-critical)';
      } catch { out.textContent = '✗ request failed'; }
    }));
  }
}
