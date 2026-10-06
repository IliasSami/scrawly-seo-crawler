// ui/components/wizard.js
import { toast } from './toast.js';
import { esc } from './escape.js';
import { authorizeCrawl } from '../edition.js';

export class Wizard {
  constructor(containerElement, apiBase, onComplete, onStarted) {
    this.container = containerElement;
    this.apiBase = apiBase;
    this.onComplete = onComplete; // callback when crawl finishes
    this.onStarted = onStarted;   // callback when a crawl is launched (crawl_id)
    
    this.currentStep = 1;
    this.clients = [];
    
    this.render();
    this.fetchClients();
    this.fetchProfiles();
  }

  async fetchProfiles() {
    try {
      this.profiles = await (await fetch(`${this.apiBase}/profiles`)).json();
      const sel = this.container.querySelector('#wiz-profile');
      if (!sel) return;
      sel.innerHTML = this.profiles.map(p =>
        `<option value="${esc(p.id)}"${p.is_default ? ' selected' : ''}>${esc(p.name)}${p.is_default ? ' · default' : ''}</option>`
      ).join('');
      sel.onchange = () => this._applyProfile();
      this._applyProfile();
    } catch (e) { /* profiles optional */ }
  }

  // Sync the advanced-override fields to the selected profile's values.
  _applyProfile() {
    const sel = this.container.querySelector('#wiz-profile');
    const p = (this.profiles || []).find(x => String(x.id) === (sel && sel.value));
    if (!p) return;
    const d = p.data || {};
    const md = this.container.querySelector('#wiz-max-depth');
    const cc = this.container.querySelector('#wiz-concurrency');
    const js = this.container.querySelector('#wiz-js-render');
    if (md && d.max_depth != null) md.value = d.max_depth;
    if (cc && d.concurrency != null) cc.value = d.concurrency;
    if (js && d.js_render != null) js.checked = !!d.js_render;
  }

  async fetchClients() {
    try {
      const res = await fetch(`${this.apiBase}/clients`);
      if (!res.ok) return;                 // backend down - leave the select as-is
      const text = await res.text();
      if (!text) return;
      this.clients = JSON.parse(text);
      this.updateClientSelect();
    } catch { /* backend unreachable; the home banner already explains it */ }
  }

  updateClientSelect() {
    const select = this.container.querySelector('#wiz-client-select');
    if (!select) return;
    
    select.innerHTML = '<option value="" disabled selected>Choose a client</option>';
    this.clients.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.id;
      opt.textContent = `${c.name} (${c.base_url})`;
      select.appendChild(opt);
    });
  }

  setStep(stepNum) {
    if (stepNum < 1 || stepNum > 4) return;
    
    // validate before moving next
    if (stepNum === 2 && this.currentStep === 1) {
      const clientId = this.container.querySelector('#wiz-client-select').value;
      if (!clientId) { 
        toast.show("Please choose a client first, or add one from the Clients screen.", "error"); 
        return; 
      }
    }
    
    this.currentStep = stepNum;
    
    // Update step UI
    const steps = this.container.querySelectorAll('.wizard-step');
    steps.forEach((s, idx) => {
      if (idx + 1 < stepNum) {
        s.classList.remove('active');
        s.classList.add('completed');
      } else if (idx + 1 === stepNum) {
        s.classList.remove('completed');
        s.classList.add('active');
      } else {
        s.classList.remove('completed', 'active');
      }
    });
    
    // Update panes
    const panes = this.container.querySelectorAll('.wizard-pane');
    panes.forEach(p => p.classList.remove('active'));
    this.container.querySelector(`#pane-${stepNum}`).classList.add('active');
    
    // Update footer
    const footer = this.container.querySelector('.wizard-footer');
    if (stepNum === 4) {
      footer.classList.add('hidden'); // monitor handles its own completion
      this.startCrawl();
    } else {
      footer.classList.remove('hidden');
      const btnNext = footer.querySelector('#btn-wiz-next');
      if (stepNum === 3) {
        btnNext.textContent = 'Start Crawl 🚀';
        
        // update review text
        const clientOpt = this.container.querySelector('#wiz-client-select option:checked');
        const maxDepth = this.container.querySelector('#wiz-max-depth').value;
        const jsRender = this.container.querySelector('#wiz-js-render').checked ? 'Enabled' : 'Disabled';
        this.container.querySelector('#wiz-review-text').textContent = 
          `Ready to crawl ${clientOpt ? clientOpt.textContent : ''}. Max Depth: ${maxDepth}, JS Rendering: ${jsRender}.`;
          
      } else {
        btnNext.textContent = 'Next';
      }
      
      const btnPrev = footer.querySelector('#btn-wiz-prev');
      btnPrev.disabled = (stepNum === 1);
    }
  }

  // Open the crawl wizard at step 1 with a client pre-selected.
  async openForClient(clientId) {
    await Promise.all([this.fetchClients(), this.fetchProfiles()]);   // never show stale lists
    this.currentStep = 1;
    this.setStep(1);
    const sel = this.container.querySelector('#wiz-client-select');
    if (sel && clientId != null) sel.value = String(clientId);
  }

  async startCrawl(overrideClientId = null) {
    this.container.querySelector('#btn-wiz-retry')?.classList.add('hidden');
    let clientId;
    if (overrideClientId !== null && overrideClientId !== undefined) {
      clientId = overrideClientId;
    } else {
      clientId = parseInt(this.container.querySelector('#wiz-client-select').value, 10);
    }
    
    try {
      const profileSel = this.container.querySelector('#wiz-profile');
      const payload = {
        client_id: clientId,
        profile_id: profileSel && profileSel.value ? parseInt(profileSel.value, 10) : undefined,
        js_render: this.container.querySelector('#wiz-js-render').checked,
        concurrency: parseInt(this.container.querySelector('#wiz-concurrency').value, 10),
        max_depth: parseInt(this.container.querySelector('#wiz-max-depth').value, 10)
      };
      
      // Ask the edition whether this crawl may start (always yes in the Free edition).
      const authz = await authorizeCrawl();
      if (authz.allowed === false) {
        this._startFailed(authz.message || 'This crawl cannot start right now.');
        return;
      }
      const headers = { 'Content-Type': 'application/json' };
      if (authz.token) headers['X-Scrawly-Authz'] = authz.token;
      const res = await fetch(`${this.apiBase}/audit/start`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        let errData = null;
        try { errData = await res.json(); } catch { /* empty body */ }
        const d = errData && errData.detail;
        // Show the server's plain-language message when it has one, never raw JSON.
        throw new Error((typeof d === 'string' && d) || (d && d.message) || '');
      }
      const data = await res.json();
      if (!data.crawl_id) throw new Error('');
      // Hand off to the persistent global crawl console (survives navigation).
      if (this.onStarted) this.onStarted(data.crawl_id);
      else this.pollProgress(data.crawl_id);
    } catch(err) {
      console.error(err);
      this._startFailed((err && err.message) || 'The crawl could not start. Please try again.');
    }
  }

  // Explain a failed start where the person will see it (the monitor pane may be
  // hidden, e.g. when Re-crawl starts directly) and offer a way back.
  _startFailed(message) {
    const status = this.container.querySelector('#monitor-status');
    if (status) status.textContent = message;
    this.container.querySelector('#btn-wiz-retry')?.classList.remove('hidden');
    toast.show(message, 'error');
  }

  async pollProgress(crawlId) {
    try {
      const res = await fetch(`${this.apiBase}/audit/status/${crawlId}`);
      const status = await res.json();
      
      this.container.querySelector('#monitor-status').textContent = status.status;
      this.container.querySelector('.monitor-progress-fill').style.width = status.progress + '%';
      
      const done = status.status === 'Complete' || status.progress >= 100;
      if (done || status.status.startsWith('Failed')) {
        if (done) {
          setTimeout(() => {
            this.onComplete(crawlId);
          }, 1000);
        }
      } else {
        setTimeout(() => this.pollProgress(crawlId), 1000);
      }
    } catch (err) {
      console.error(err);
      setTimeout(() => this.pollProgress(crawlId), 2000);
    }
  }

  render() {
    this.container.innerHTML = `
      <div class="wizard-card">
        <div class="wizard-steps">
          <div class="wizard-step active"><div class="step-circle">1</div><div class="step-label">Target</div></div>
          <div class="wizard-step"><div class="step-circle">2</div><div class="step-label">Scope</div></div>
          <div class="wizard-step"><div class="step-circle">3</div><div class="step-label">Review</div></div>
        </div>
        
        <div class="wizard-body">
          <!-- Step 1 -->
          <div id="pane-1" class="wizard-pane active">
            <h2>Select Target</h2>
            <p>Choose which client site to crawl.</p>
            <div class="form-group">
              <label>Target Client</label>
              <select id="wiz-client-select"></select>
            </div>
            <p class="text-sm"><em>Add a new client from the Clients screen (+ New Client).</em></p>
          </div>
          
          <!-- Step 2 -->
          <div id="pane-2" class="wizard-pane">
            <h2>Crawl Scope</h2>
            <div class="form-group">
              <label>Crawl profile</label>
              <select id="wiz-profile"></select>
            </div>
            <p>The profile sets the defaults. Override any of them below if needed.</p>
            <button id="wiz-toggle-advanced" class="btn btn-secondary" style="margin-bottom: var(--space-3);">Show Advanced Settings</button>
            
            <div id="wiz-advanced-settings" class="hidden">
              <div class="form-group">
                <label>Max Crawl Depth</label>
                <input type="number" id="wiz-max-depth" value="3">
              </div>
              <div class="form-group">
                <label>Pages at a time</label>
                <input type="number" id="wiz-concurrency" value="5">
              </div>
              <div class="form-group" style="display: flex; align-items: center; gap: 8px;">
                <input type="checkbox" id="wiz-js-render" checked>
                <label for="wiz-js-render" style="margin: 0;">Load JavaScript (slower, more accurate)</label>
              </div>
            </div>
          </div>
          
          <!-- Step 3 -->
          <div id="pane-3" class="wizard-pane">
            <h2>Review & Launch</h2>
            <p id="wiz-review-text" style="font-size: 16px; font-weight: 500;"></p>
            <p class="text-sm">Scrawly follows the site's robots.txt rules and slows down automatically if the site asks it to.</p>
          </div>
          
          <!-- Step 4 (Monitor) -->
          <div id="pane-4" class="wizard-pane monitor-pane">
            <h2>Crawling...</h2>
            <p id="monitor-status" style="font-weight: 500;">Initializing...</p>
            <div class="monitor-progress-bg">
              <div class="monitor-progress-fill"></div>
            </div>
            <p class="text-sm">You can navigate away. The audit will continue in the background.</p>
            <button id="btn-wiz-retry" class="btn btn-secondary hidden" type="button">Back to settings</button>
          </div>
        </div>
        
        <div class="wizard-footer">
          <button id="btn-wiz-prev" class="btn btn-secondary" disabled>Back</button>
          <button id="btn-wiz-next" class="btn btn-primary">Next</button>
        </div>
      </div>
    `;
    
    this.container.querySelector('#btn-wiz-next').addEventListener('click', () => this.setStep(this.currentStep + 1));
    this.container.querySelector('#btn-wiz-retry').addEventListener('click', () => this.setStep(3));
    this.container.querySelector('#btn-wiz-prev').addEventListener('click', () => this.setStep(this.currentStep - 1));
    
    this.container.querySelector('#wiz-toggle-advanced').addEventListener('click', (e) => {
      const adv = this.container.querySelector('#wiz-advanced-settings');
      if (adv.classList.contains('hidden')) {
        adv.classList.remove('hidden');
        e.target.textContent = 'Hide Advanced Settings';
      } else {
        adv.classList.add('hidden');
        e.target.textContent = 'Show Advanced Settings';
      }
    });
  }
}
