// ui/components/help-rail.js
// "Send feedback" and "About Scrawly" at the bottom of the icon rail. Scrawly is
// free and built for the SEO community, so a note to the maintainer is always
// one click away, in every edition.

import { openExternal } from './external.js';

export const PROJECT = {
  name: 'Scrawly',
  author: 'Ilias Sami',
  site: 'https://iliassami.com/',
  email: 'me@iliassami.com',
  repo: 'https://github.com/IliasSami/scrawly-seo-crawler',
  license: 'MIT License',
};

const ICON_FEEDBACK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>';
const ICON_ABOUT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function railButton(id, label, icon, onClick) {
  const b = document.createElement('button');
  b.type = 'button';
  b.id = id;
  b.className = 'nav-icon help-rail-btn';
  b.title = label;
  b.setAttribute('aria-label', label);
  b.innerHTML = icon;
  b.addEventListener('click', onClick);
  return b;
}

export async function appInfo() {
  try {
    const r = await fetch('/api/edition', { cache: 'no-store' });
    if (r.ok) return await r.json();
  } catch { /* backend offline: the banner explains it */ }
  return { edition: window.SCRAWLY_EDITION || 'free', version: '' };
}

export function openAbout() {
  document.querySelector('.about-overlay')?.remove();
  const ov = document.createElement('div');
  ov.className = 'fb-overlay about-overlay';
  ov.innerHTML = `
    <div class="fb-card about-card" role="dialog" aria-modal="true" aria-labelledby="about-title">
      <h2 class="fb-title" id="about-title">Scrawly</h2>
      <p class="about-version" aria-live="polite">&nbsp;</p>
      <p class="fb-sub">A free, open-source technical SEO and GEO crawler. Audit any
        website for search and AI-search readiness, see what to fix, and fix
        WordPress sites safely. No account, no limits, free forever.</p>
      <dl class="about-meta">
        <dt>Created by</dt>
        <dd><a href="${esc(PROJECT.site)}" data-ext>${esc(PROJECT.author)}</a>
          (<a href="${esc(PROJECT.site)}" data-ext>iliassami.com</a>)</dd>
        <dt>Contact</dt>
        <dd><a href="mailto:${esc(PROJECT.email)}" data-ext>${esc(PROJECT.email)}</a></dd>
        <dt>Source code</dt>
        <dd><a href="${esc(PROJECT.repo)}" data-ext>GitHub</a></dd>
        <dt>License</dt>
        <dd>${esc(PROJECT.license)}</dd>
      </dl>
      <div class="fb-actions">
        <button class="fb-cancel" type="button">Close</button>
        <button class="fb-send about-feedback" type="button">Send feedback</button>
      </div>
    </div>`;
  document.body.appendChild(ov);
  const close = () => { ov.remove(); document.removeEventListener('keydown', onKey); };
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  document.addEventListener('keydown', onKey);
  ov.addEventListener('click', (e) => {
    if (e.target === ov) { close(); return; }
    const a = e.target.closest && e.target.closest('a[data-ext]');
    if (a) { e.preventDefault(); e.stopPropagation(); openExternal(a.getAttribute('href')); }
  });
  ov.querySelector('.fb-cancel').addEventListener('click', close);
  ov.querySelector('.about-feedback').addEventListener('click', () => {
    close();
    if (typeof window.openFeedback === 'function') window.openFeedback();
  });
  setTimeout(() => ov.querySelector('.fb-cancel').focus(), 30);
  appInfo().then((info) => {
    const v = ov.querySelector('.about-version');
    if (!v) return;
    const ed = info.edition === 'free' ? 'Free edition' : 'Managed edition';
    v.textContent = info.version ? `${ed} · version ${info.version}` : ed;
  });
}

export function mountHelpRail() {
  const rail = document.querySelector('.global-nav');
  if (!rail || document.getElementById('nav-btn-feedback')) return;
  rail.appendChild(railButton('nav-btn-feedback', 'Send feedback', ICON_FEEDBACK,
    () => { if (typeof window.openFeedback === 'function') window.openFeedback(); }));
  rail.appendChild(railButton('nav-btn-about', 'About Scrawly', ICON_ABOUT, openAbout));
}
