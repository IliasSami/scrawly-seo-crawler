// ui/components/client-wizard.js
// Per-client onboarding: Details → auto-detect stack → choose a connection
// method → Done. Any website connects (URL-only works for every stack); the
// WordPress Connector additionally unlocks guarded fixes + agentic features.
import { toast } from './toast.js';
import { saveDownload } from './external.js';

const METHODS = [
  { m: 'url_only', icon: '🌐', label: 'URL only', hint: 'Read-only audit · any site' },
  { m: 'wp_connector', icon: '🔌', label: 'WordPress Connector', hint: 'Safe fixes and AI tools' },
  { m: 'connector_file', icon: '📄', label: 'Verify by file', hint: 'Prove ownership' },
];

const STACK_LABEL = {
  wordpress: 'WordPress', shopify: 'Shopify', wix: 'Wix', squarespace: 'Squarespace',
  webflow: 'Webflow', framer: 'Framer', nextjs: 'Next.js', react: 'React',
  laravel: 'Laravel', drupal: 'Drupal', joomla: 'Joomla', magento: 'Magento',
  ghost: 'Ghost', generic: 'Custom / Unknown',
};

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

export class ClientWizard {
  constructor(container, apiBase, { onDone, onRunAudit } = {}) {
    this.container = container;
    this.apiBase = apiBase;
    this.onDone = onDone || (() => {});
    this.onRunAudit = onRunAudit || (() => {});
    this.step = 1;
    this.client = null;
    this.method = 'url_only';
    this.detected = null;
    this.fixReady = false;   // WordPress Connector verified → fixes/agentic on
    this.render();
  }

  open(client = null) {
    this.client = client;
    this.fixReady = !!(client && client.connected);
    this.method = (client && client.connection_method) || 'url_only';
    this.detected = (client && client.detected_stack) || null;
    this.step = 1;
    this.render();
    this.setStep(1);
  }

  setStep(n) {
    this.step = n;
    this.container.querySelectorAll('.wizard-step').forEach((s, i) => {
      s.classList.toggle('active', i + 1 === n);
      s.classList.toggle('completed', i + 1 < n);
    });
    this.container.querySelectorAll('.wizard-pane').forEach((p, i) => {
      p.classList.toggle('active', i + 1 === n);
    });
    if (n === 2) this.refreshConnectPane();
    if (n === 3) this.refreshDonePane();
  }

  async saveDetails() {
    const name = this.container.querySelector('#cw-name').value.trim();
    const url = this.container.querySelector('#cw-url').value.trim();
    if (!name) { toast.show('Enter a client name.', 'error'); return false; }
    if (!/^https?:\/\//.test(url)) {
      toast.show('Enter a valid Site URL starting with https://', 'error');
      return false;
    }
    try {
      const method = this.client && this.client.id ? 'PUT' : 'POST';
      const path = this.client && this.client.id
        ? `${this.apiBase}/clients/${this.client.id}` : `${this.apiBase}/clients`;
      const res = await fetch(path, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, base_url: url }),
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        toast.show(e.detail || 'Could not save client.', 'error');
        return false;
      }
      this.client = await res.json();
      return true;
    } catch (e) {
      toast.show('Network error saving client.', 'error');
      return false;
    }
  }

  /** Fingerprint the site → recommend a method + remember the stack for presets. */
  async autoDetect() {
    const chip = this.container.querySelector('#cw-detect-chip');
    if (chip) chip.innerHTML = '<span class="cw-detecting">Checking what the site is built with…</span>';
    try {
      const r = await fetch(`${this.apiBase}/clients/${this.client.id}/detect`, { method: 'POST' });
      if (!r.ok) throw new Error('detect failed');
      const data = await r.json();
      this.detected = data.detection;
      // Recommend the Connector for WordPress; URL-only for everything else.
      if (!this.client.connection_method || this.client.connection_method === 'url_only') {
        this.method = this.detected.stack === 'wordpress' ? 'wp_connector' : 'url_only';
      }
    } catch (e) {
      this.detected = null;
    }
  }

  refreshConnectPane() {
    const host = (() => { try { return new URL(this.client.base_url).hostname; } catch { return this.client?.base_url || ''; } })();
    const hostEl = this.container.querySelector('#cw-site-host');
    if (hostEl) hostEl.textContent = host;
    const chip = this.container.querySelector('#cw-detect-chip');
    if (chip) {
      if (this.detected && this.detected.stack) {
        const lbl = STACK_LABEL[this.detected.stack] || this.detected.stack;
        const conf = Math.round((this.detected.confidence || 0) * 100);
        chip.innerHTML = `<span class="cw-stack-chip">Detected: <b>${esc(lbl)}</b> · ${conf}% · settings picked for you</span>`;
      } else {
        chip.innerHTML = '';
      }
    }
    // Cards
    this.container.querySelectorAll('.cw-method').forEach((b) =>
      b.classList.toggle('sel', b.dataset.m === this.method));
    this.renderMethodPanel(this.method);
  }

  selectMethod(m) {
    this.method = m;
    this.container.querySelectorAll('.cw-method').forEach((b) =>
      b.classList.toggle('sel', b.dataset.m === m));
    // Persist the chosen method immediately so the client is auditable via it.
    if (this.client?.id) {
      fetch(`${this.apiBase}/clients/${this.client.id}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ connection_method: m }),
      }).catch(() => {});
    }
    this.renderMethodPanel(m);
  }

  renderMethodPanel(m) {
    const panel = this.container.querySelector('#cw-method-panel');
    if (!panel) return;
    const site = this.client?.wp_url || this.client?.base_url || '';
    const builders = {
      url_only: () => `
        <div class="cw-mp">
          <p><b>Read-only deep audit.</b> Scrawly maps the architecture from the sitemap, then runs
          250+ technical-SEO, GEO &amp; crawlability checks on every page. Works on <em>any</em> tech
          stack - nothing is installed and nothing is written to the site.</p>
          <p class="cw-note">Guarded fixes &amp; the agentic layer need write access - add the WordPress
          Connector (or another write method) any time to unlock them.</p>
          <div class="cw-status cw-status-ok">✓ Ready to audit</div>
        </div>`,
      wp_connector: () => `
        <div class="cw-mp">
          <ol class="cw-steps">
            <li><button type="button" class="btn btn-secondary btn-sm" id="cw-plugin-dl">⬇ Download plugin (.zip)</button>
              <span class="cw-hint">6 KB · single file</span></li>
            <li>In <strong>wp-admin → Plugins → Add New → Upload Plugin</strong>, upload &amp; <strong>Activate</strong>.</li>
            <li>Open the <strong>Scrawly</strong> menu, copy the <strong>Connection Key</strong>, paste below.</li>
          </ol>
          <div class="form-group"><label>Site URL</label>
            <input type="url" id="cw-wp-url" value="${esc(site)}"></div>
          <div class="form-group"><label>Connection key</label>
            <div class="cw-key-row">
              <input type="password" id="cw-key" class="mono" placeholder="sk_…" autocomplete="off">
              <button type="button" class="btn btn-link btn-sm" id="cw-key-toggle">Show</button>
            </div></div>
          <div class="cw-actions"><button class="btn btn-primary" id="cw-test">Test connection</button>
            <span id="cw-conn-status" class="cw-status"></span></div>`,
      connector_file: () => `
        <div class="cw-mp">
          <p>Prove you control <b>${esc(site)}</b> by placing a verification file at its root. Universal - works on any host.</p>
          <div id="cw-vf-body" class="cw-vf">loading token…</div>
          <div class="cw-actions"><button class="btn btn-primary" id="cw-verify">Verify ownership</button>
            <span id="cw-conn-status" class="cw-status"></span></div>
        </div>`,
    };
    panel.innerHTML = (builders[m] || builders.url_only)();
    this._wireMethodPanel(m);
  }

  async _wireMethodPanel(m) {
    const $ = (s) => this.container.querySelector(s);
    if (m === 'wp_connector') {
      $('#cw-plugin-dl')?.addEventListener('click', async () => {
        const outcome = await saveDownload(`${this.apiBase}/connector/download`, 'scrawly-connector.zip');
        if (outcome === 'saved') toast.show('Plugin saved. Upload it in WordPress under Plugins, Add New.', 'success');
        else if (outcome === 'failed') toast.show('Could not save the plugin. Please try again.', 'error');
      });
      $('#cw-test')?.addEventListener('click', () => this.testConnection());
      $('#cw-key-toggle')?.addEventListener('click', () => {
        const inp = $('#cw-key'); const show = inp.type === 'password';
        inp.type = show ? 'text' : 'password';
        $('#cw-key-toggle').textContent = show ? 'Hide' : 'Show';
      });
    } else if (m === 'connector_file') {
      try {
        const t = await (await fetch(`${this.apiBase}/clients/${this.client.id}/verify-token`)).json();
        const body = $('#cw-vf-body');
        if (body) body.innerHTML = `
          <div class="cw-vf-file"><span class="cw-vf-label">File</span>
            <code class="mono">${esc(t.path)}</code></div>
          <div class="cw-vf-file"><span class="cw-vf-label">Contents</span>
            <code class="mono">${esc(t.token)}</code></div>
          <p class="cw-note">Or add <code>&lt;meta name="scrawly-verify" content="${esc(t.token)}"&gt;</code> to your homepage <code>&lt;head&gt;</code>.</p>`;
      } catch { /* ignore */ }
      $('#cw-verify')?.addEventListener('click', () => this.verifyFile());
    }
  }

  async verifyFile() {
    const st = this.container.querySelector('#cw-conn-status');
    st.className = 'cw-status'; st.textContent = 'Checking…';
    try {
      const r = await fetch(`${this.apiBase}/clients/${this.client.id}/verify-file`, { method: 'POST' });
      const d = await r.json();
      if (d.verified) {
        st.className = 'cw-status cw-status-ok'; st.textContent = '✓ Ownership verified';
        toast.show('Ownership verified!', 'success');
      } else {
        st.className = 'cw-status cw-status-err'; st.textContent = `✗ ${d.detail || 'Not found yet.'}`;
      }
    } catch (e) {
      st.className = 'cw-status cw-status-err'; st.textContent = 'Network error.';
    }
  }

  async testConnection() {
    const key = this.container.querySelector('#cw-key').value.trim();
    const wpUrl = this.container.querySelector('#cw-wp-url').value.trim();
    const statusEl = this.container.querySelector('#cw-conn-status');
    if (!key) { toast.show('Paste the Connection Key from the plugin.', 'error'); return; }
    statusEl.className = 'cw-status'; statusEl.textContent = 'Testing connection…';
    try {
      const res = await fetch(`${this.apiBase}/clients/${this.client.id}/wp-test`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wp_url: wpUrl, wp_connection_key: key }),
      });
      const d = await res.json();
      if (d.connected) {
        await fetch(`${this.apiBase}/clients/${this.client.id}`, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ wp_url: wpUrl, wp_connection_key: key, connection_method: 'wp_connector' }),
        });
        this.fixReady = true;
        this.client.connected = true;
        statusEl.className = 'cw-status cw-status-ok';
        statusEl.textContent = `✓ Connected to WordPress ${d.wp_version || ''}` +
          `${d.seo_plugin && d.seo_plugin !== 'none' ? ` · SEO: ${d.seo_plugin}` : ''}` +
          `${d.fixes_allowed ? ' · fixes enabled' : ' · fixes disabled on site'}`;
        toast.show('WordPress connected!', 'success');
      } else {
        statusEl.className = 'cw-status cw-status-err';
        statusEl.textContent = `✗ ${d.detail || 'Could not connect. Check the URL and key.'}`;
      }
    } catch (e) {
      statusEl.className = 'cw-status cw-status-err';
      statusEl.textContent = 'Network error while testing.';
    }
  }

  refreshDonePane() {
    const nameEl = this.container.querySelector('#cw-done-name');
    if (nameEl) nameEl.textContent = this.client?.name || 'Client';
    const badge = this.container.querySelector('#cw-done-badge');
    if (badge) {
      if (this.fixReady) {
        badge.className = 'badge badge-passed';
        badge.textContent = 'Connected · fixes enabled';
      } else {
        const lbl = this.detected && this.detected.stack
          ? (STACK_LABEL[this.detected.stack] || this.detected.stack) : '';
        badge.className = 'badge badge-notice';
        badge.textContent = lbl ? `Audit-ready · ${lbl}` : 'Audit-ready';
      }
    }
  }

  render() {
    this.container.innerHTML = `
      <div class="wizard-card">
        <div class="wizard-steps">
          <div class="wizard-step active"><div class="step-circle">1</div><div class="step-label">Details</div></div>
          <div class="wizard-step"><div class="step-circle">2</div><div class="step-label">Connect</div></div>
          <div class="wizard-step"><div class="step-circle">3</div><div class="step-label">Done</div></div>
        </div>

        <div class="wizard-body">
          <div class="wizard-pane active" data-pane="1">
            <h2>Add a website</h2>
            <p>Name it and paste its URL. Scrawly detects the tech stack automatically and picks the best way to connect.</p>
            <div class="form-group"><label>Name</label>
              <input type="text" id="cw-name" placeholder="e.g. Acme Corp" autocomplete="off"></div>
            <div class="form-group"><label>Site URL</label>
              <input type="url" id="cw-url" placeholder="https://example.com" autocomplete="off"></div>
          </div>

          <div class="wizard-pane" data-pane="2">
            <h2>Connect the site</h2>
            <p>Choose how Scrawly reaches <b id="cw-site-host"></b>. <span id="cw-detect-chip"></span></p>
            <div class="cw-methods">
              ${METHODS.map((x) => `<button type="button" class="cw-method" data-m="${x.m}">
                <span class="cw-method-ico">${x.icon}</span>
                <span class="cw-method-lbl">${x.label}</span>
                <small>${x.hint}</small></button>`).join('')}
            </div>
            <div class="cw-method-panel" id="cw-method-panel"></div>
          </div>

          <div class="wizard-pane" data-pane="3">
            <div class="cw-done">
              <div class="cw-done-check">✓</div>
              <h2><span id="cw-done-name">Client</span> is ready</h2>
              <span id="cw-done-badge" class="badge badge-notice">Audit-ready</span>
              <p style="margin-top: var(--space-3);">Run the first audit now, or come back any time from the Clients screen.</p>
              <div class="flex gap-2" style="justify-content:center; margin-top: var(--space-3);">
                <button class="btn btn-secondary" id="cw-goto-clients">Back to Clients</button>
                <button class="btn btn-primary" id="cw-run-audit">Run first audit →</button>
              </div>
            </div>
          </div>
        </div>

        <div class="wizard-footer">
          <button class="btn btn-secondary" id="cw-back">Back</button>
          <div class="flex gap-2">
            <button class="btn btn-primary" id="cw-next">Next</button>
          </div>
        </div>
      </div>`;

    const $ = (s) => this.container.querySelector(s);

    $('#cw-back').addEventListener('click', () => { if (this.step > 1) this.setStep(this.step - 1); });

    $('#cw-next').addEventListener('click', async () => {
      if (this.step === 1) {
        const btn = $('#cw-next'); btn.disabled = true; btn.textContent = 'Detecting…';
        const ok = await this.saveDetails();
        if (ok) await this.autoDetect();
        btn.disabled = false; btn.textContent = 'Next';
        if (ok) this.setStep(2);
      } else if (this.step === 2) {
        this.setStep(3);
      }
    });

    this.container.querySelectorAll('.cw-method').forEach((b) =>
      b.addEventListener('click', () => this.selectMethod(b.dataset.m)));

    $('#cw-goto-clients').addEventListener('click', () => this.onDone(this.client));
    $('#cw-run-audit').addEventListener('click', () => this.onRunAudit(this.client));

    const syncFooter = () => {
      $('#cw-back').style.visibility = this.step === 1 ? 'hidden' : 'visible';
      $('#cw-next').style.display = this.step === 3 ? 'none' : 'inline-flex';
      $('.wizard-footer').style.display = this.step === 3 ? 'none' : 'flex';
      $('#cw-next').textContent = this.step === 2 ? 'Finish →' : 'Next';
    };
    const origSetStep = this.setStep.bind(this);
    this.setStep = (n) => { origSetStep(n); syncFooter(); };

    if (this.client) {
      $('#cw-name').value = this.client.name || '';
      $('#cw-url').value = this.client.base_url || '';
    }
    syncFooter();
  }
}
