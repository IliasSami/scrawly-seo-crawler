// ui/components/config-panel.js
// Configuration workspace: named crawl-config profiles + a Screaming-Frog-style
// tabbed config surface. Fields marked {planned:true} are persisted with the
// profile but not yet honored by the crawler engine (labelled "Planned" in UI)
// — everything else is wired and affects the crawl.
import { toast } from './toast.js';

const UA_PRESETS = [
  { label: 'Scrawly (default)', value: 'ScrawlyBot/1.0' },
  { label: 'Googlebot Smartphone', value: 'Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)' },
  { label: 'Googlebot Desktop', value: 'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Googlebot/2.1; +http://www.google.com/bot.html) Chrome/120.0.0.0 Safari/537.36' },
  { label: 'Bingbot', value: 'Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)' },
];

// Beginner-friendly help shown on the per-field "?" tooltip. Keyed by field key.
const HELP = {
  include_patterns: 'Only crawl URLs matching these regex patterns (an allowlist). Comma-separate multiple; leave blank to crawl everything not excluded.',
  exclude_patterns: 'URLs matching these regex patterns are never fetched - great for /wp-admin/, faceted filters or tracking params.',
  discover_sitemap: 'Read robots.txt and /sitemap.xml to seed the crawl, so orphan pages that aren’t linked still get found.',
  sitemap_only: 'Crawl only the URLs listed in the sitemap - don’t follow links to discover more.',
  max_depth: 'How many link-hops from the start URL to follow. 1 = the homepage plus its direct links.',
  crawl_fragment_identifiers: 'Treat #anchor URLs as separate pages. Usually off - they’re the same document.',
  form_auth: 'Log in with a web form before crawling (staging / members areas). Credentials come from .env - see Settings → Integrations.',
  crawl_subdomains: 'Also crawl other subdomains of the same site (e.g. blog.example.com from www.example.com).',
  crawl_outside_start_folder: 'Allow the crawl to leave the starting folder - e.g. start at /blog/ but roam the whole site.',
  follow_nofollow: 'Follow internal links marked rel="nofollow". Off by default, matching how search engines treat them.',
  max_pages: 'Hard cap on total pages crawled - protects against runaway crawls on huge sites.',
  max_urls_per_depth: 'Cap the number of URLs crawled at each depth level. 0 = unlimited.',
  max_per_subdomain: 'Cap total pages per subdomain. 0 = unlimited.',
  max_url_length: 'Skip URLs longer than this many characters (often junk / tracking URLs).',
  max_query_params: 'Skip URLs with more than this many query-string parameters. 0 = unlimited.',
  max_links_per_page: 'Only follow the first N links on each page. 0 = unlimited.',
  max_folder_depth: 'Skip URLs nested deeper than this many folders. 0 = unlimited.',
  max_redirects: 'How many redirects to follow before giving up on a URL.',
  max_page_size_kb: 'Skip pages larger than this size in KB. 0 = unlimited.',
  concurrency: 'How many pages to fetch in parallel. Higher = faster, but heavier on the target server.',
  max_requests_per_sec: 'Throttle to at most this many requests per second, site-wide. 0 = unlimited.',
  response_timeout_s: 'Give up waiting for a page’s response after this many seconds.',
  js_render: 'Render each page in a headless browser (Playwright) to see JavaScript-built content - slower but accurate for SPAs.',
  render_sample: 'Only render the first N pages with the browser (the rest use raw HTML). 0 = render all.',
  user_agent: 'The User-Agent header sent when crawling. Pick a preset or set a custom identity.',
  render_timeout_s: 'Max time to wait for JavaScript / AJAX to finish when rendering a page.',
  window_width: 'Browser viewport width (px) used when rendering pages.',
  window_height: 'Browser viewport height (px) used when rendering pages.',
  js_error_reporting: 'Capture JavaScript console errors and warnings during rendering, surfaced per page.',
  flatten_shadow_dom: 'Pull Web-Component shadow-DOM content into the page so its text and links are analysed.',
  flatten_iframes: 'Inline same-origin iframe content into the page for analysis.',
  robots_mode: 'How to treat robots.txt: respect it, ignore it, or ignore-but-report what would have been blocked.',
  robots_user_agent: 'Which robots.txt user-agent group to obey (e.g. Googlebot rules vs the * catch-all).',
  remove_parameters: 'Strip these query parameters from URLs before crawling (comma-sep), collapsing duplicate tracking URLs.',
  lowercase_urls: 'Treat URLs as case-insensitive by lowercasing them, avoiding duplicate /Page vs /page.',
  regex_replace: 'Rewrite URLs with ordered find→replace rules, one per line as "pattern => replacement".',
  custom_headers: 'Extra HTTP request headers to send, one per line (e.g. Accept-Language: en).',
  store_html: 'Save each page’s raw HTML in the database. Enables re-analysis but grows storage.',
  store_rendered_html: 'Save the browser-rendered HTML (post-JavaScript). Larger, but useful for debugging SPAs.',
  store_hash: 'Compute a content hash per page to detect exact duplicates.',
  extract_structured_data: 'Parse JSON-LD / microdata / RDFa structured data from pages.',
  extract_cookies: 'Record the cookies each page sets.',
  extract_http_headers: 'Store the full HTTP response headers per page.',
  extract_pdf: 'Fetch PDFs and extract their document properties (title, author, page count).',
  crawl_images: 'Discover and record the <img> resources pages reference.',
  crawl_external: 'Status-check outbound links to other domains - finds broken external links.',
  crawl_css: 'Fetch and status-check the CSS files pages load.',
  crawl_js: 'Fetch and status-check the JavaScript files pages load.',
  crawl_media: 'Fetch and status-check media files (video / audio) pages load.',
  crawl_hreflang: 'Follow hreflang alternate links to also crawl language / region variants.',
  crawl_amp: 'Follow rel="amphtml" links to also crawl AMP versions.',
  crawl_pagination: 'Follow rel="next" / rel="prev" pagination links.',
  content_include: 'Restrict the "content area" to these CSS selectors (e.g. main, article) for word count, duplicates and spelling.',
  content_exclude: 'Exclude these CSS selectors (e.g. nav, footer) from the content area.',
  near_dup_threshold: 'Similarity % above which two pages are flagged near-duplicates (default 90%).',
  ignore_paginated_dupes: 'Don’t flag paginated URLs (?page=2, /page/2/) as duplicates of page 1.',
  spelling_enrich: 'Run a spelling / grammar check on each page’s content (needs a backend - see Settings → Integrations).',
  spelling_language: 'Language for spell-checking, e.g. en-US. "auto" reads each page’s <html lang>.',
  spelling_ignore: 'Words to never flag as misspelled (comma-separated), e.g. brand names.',
  list_mode: 'Crawl exactly the URLs you paste below - no link discovery.',
  list_urls: 'One URL per line. Only used when List mode is on.',
  ignore_non_indexable_issues: 'Hide issues that only affect non-indexable pages, focusing the report on what Google sees.',
  respect_noindex: 'Treat noindex pages as non-indexable and hide them from index-focused views.',
  respect_canonical: 'Treat canonicalised pages as pointing elsewhere and de-emphasise them.',
  assume_html: 'Assume responses are HTML even without a content-type header (some servers omit it).',
  extract_srcset: 'Also extract responsive image candidates from <img srcset>.',
  cdns: 'Domains to treat as part of this site (your CDN hosts), so their assets count as internal.',
  html_validation: 'Run structural HTML checks: DOCTYPE, <html lang>, multiple <title>, charset, invalid <head> content.',
  psi_enrich: 'Pull Core Web Vitals from Google PageSpeed Insights. Needs a free PageSpeed API key: add PAGESPEED_API_KEY to the .env file in the Scrawly folder (see docs/DESKTOP.md).',
  gsc_enrich: 'Pull impressions / clicks from Google Search Console for matched URLs.',
  ga4_enrich: 'Pull engagement metrics (sessions, conversions) from Google Analytics 4.',
  ga4_property_id: 'Your GA4 property ID (numeric), e.g. 123456789.',
  ga4_days: 'How many days of GA4 data to pull (the lookback window).',
  ga4_fuzzy_match: 'Match GA4 page paths to crawled URLs loosely (handles trailing-slash / index.html).',
  embeddings_enrich: 'Generate text embeddings to find semantically similar / low-relevance pages (needs an embeddings key).',
  embeddings_similarity_threshold: 'Cosine-similarity cutoff for flagging near-identical content by meaning.',
};

// SF-style tabbed config. type: bool | num | text | ua | select | headers | rules | custom.
const TABS = [
  { id: 'spider', label: 'Spider', groups: [
    { group: 'Scope & discovery', items: [
      { k: 'include_patterns', label: 'Include URL patterns', type: 'text', hint: 'regex, comma-sep (allowlist)' },
      { k: 'exclude_patterns', label: 'Exclude URL patterns', type: 'text', hint: 'regex, comma-sep - never fetched' },
      { k: 'discover_sitemap', label: 'Discover & seed sitemap', type: 'bool' },
      { k: 'sitemap_only', label: 'Crawl only sitemap URLs', type: 'bool' },
      { k: 'max_depth', label: 'Max crawl depth', type: 'num' },
      { k: 'crawl_fragment_identifiers', label: 'Crawl #fragment identifiers', type: 'bool' },
      { k: 'form_auth', label: 'Authenticated crawl (web-form login)', type: 'bool', hint: 'credentials from .env - see Settings → Integrations' },
      { k: 'crawl_subdomains', label: 'Crawl all subdomains', type: 'bool' },
      { k: 'crawl_outside_start_folder', label: 'Crawl outside start folder', type: 'bool' },
      { k: 'follow_nofollow', label: 'Follow internal nofollow', type: 'bool', hint: 'default skips rel=nofollow' },
    ]},
    { group: 'Limits', items: [
      { k: 'max_pages', label: 'Limit crawl total (pages)', type: 'num' },
      { k: 'max_urls_per_depth', label: 'Limit URLs per crawl depth', type: 'num', hint: '0 = unlimited' },
      { k: 'max_per_subdomain', label: 'Limit crawl total per subdomain', type: 'num', hint: '0 = unlimited' },
      { k: 'max_url_length', label: 'Max URL length', type: 'num' },
      { k: 'max_query_params', label: 'Max query strings', type: 'num', hint: '0 = unlimited' },
      { k: 'max_links_per_page', label: 'Max links per URL', type: 'num', hint: '0 = unlimited' },
      { k: 'max_folder_depth', label: 'Max folder depth', type: 'num', hint: '0 = unlimited' },
      { k: 'max_redirects', label: 'Max redirects to follow', type: 'num' },
      { k: 'max_page_size_kb', label: 'Max page size (KB)', type: 'num', hint: '0 = unlimited' },
    ]},
    { group: 'Speed', items: [
      { k: 'concurrency', label: 'Max threads (concurrency)', type: 'num' },
      { k: 'max_requests_per_sec', label: 'Max URI/s (rate cap)', type: 'num', hint: '0 = unlimited' },
      { k: 'response_timeout_s', label: 'Response timeout (s)', type: 'num' },
    ]},
  ]},
  { id: 'rendering', label: 'Rendering', groups: [
    { group: 'JavaScript', items: [
      { k: 'js_render', label: 'JavaScript rendering (Playwright)', type: 'bool' },
      { k: 'render_sample', label: 'Render sample', type: 'num', hint: '0 = render all pages' },
      { k: 'user_agent', label: 'HTTP User-Agent', type: 'ua' },
      { k: 'render_timeout_s', label: 'AJAX timeout (s)', type: 'num' },
      { k: 'window_width', label: 'Window width (px)', type: 'num' },
      { k: 'window_height', label: 'Window height (px)', type: 'num' },
      { k: 'js_error_reporting', label: 'JavaScript error reporting', type: 'bool' },
      { k: 'flatten_shadow_dom', label: 'Flatten shadow DOM', type: 'bool' },
      { k: 'flatten_iframes', label: 'Flatten iframes', type: 'bool' },
    ]},
  ]},
  { id: 'robots', label: 'Robots', groups: [
    { group: 'Robots.txt', items: [
      { k: 'robots_mode', label: 'Robots.txt mode', type: 'select', options: [
        { value: 'respect', label: 'Respect (enforce)' },
        { value: 'ignore', label: 'Ignore (don\'t fetch)' },
        { value: 'ignore_but_report', label: 'Ignore but report' },
      ]},
      { k: 'robots_user_agent', label: 'Robots User-Agent', type: 'text', hint: 'matched against robots groups; blank = HTTP UA' },
    ]},
  ]},
  { id: 'url', label: 'URL Handling', groups: [
    { group: 'URL rewriting (applied to discovered URLs)', items: [
      { k: 'remove_parameters', label: 'Remove parameters', type: 'text', hint: 'query keys, comma-sep - e.g. utm_source, ref, sid' },
      { k: 'lowercase_urls', label: 'Lowercase discovered URLs', type: 'bool' },
      { k: 'regex_replace', label: 'Regex replace (ordered)', type: 'rules', hint: 'one rule per line: pattern => replacement' },
    ]},
    { group: 'Custom HTTP headers', items: [
      { k: 'custom_headers', label: 'Request headers', type: 'headers', hint: 'one per line: Name: value  (e.g. Accept-Language: en-GB)' },
    ]},
  ]},
  { id: 'extraction', label: 'Extraction', groups: [
    { group: 'Save page data', items: [
      { k: 'store_html', label: 'Store HTML', type: 'bool' },
      { k: 'store_rendered_html', label: 'Store rendered HTML', type: 'bool' },
      { k: 'store_hash', label: 'Store hash value (exact dupes)', type: 'bool' },
      { k: 'extract_structured_data', label: 'Structured data (JSON-LD/Microdata/RDFa)', type: 'bool' },
      { k: 'extract_cookies', label: 'Cookies', type: 'bool' },
      { k: 'extract_http_headers', label: 'HTTP headers', type: 'bool' },
      { k: 'extract_pdf', label: 'PDF properties', type: 'bool' },
    ]},
    { group: 'Check linked files', items: [
      { k: 'crawl_images', label: 'Images', type: 'bool' },
      { k: 'crawl_external', label: 'External links', type: 'bool' },
      { k: 'crawl_css', label: 'CSS', type: 'bool' },
      { k: 'crawl_js', label: 'JavaScript', type: 'bool' },
      { k: 'crawl_media', label: 'Media', type: 'bool' },
      { k: 'crawl_hreflang', label: 'Hreflang', type: 'bool', hint: 'follow alternates as pages' },
      { k: 'crawl_amp', label: 'AMP', type: 'bool', hint: 'follow rel=amphtml' },
      { k: 'crawl_pagination', label: 'Pagination (rel next/prev)', type: 'bool' },
    ]},
  ]},
  { id: 'content', label: 'Content', groups: [
    { group: 'Content area + duplicates', items: [
      { k: 'content_include', label: 'Include elements/classes', type: 'text', hint: 'CSS selector, e.g. main, article' },
      { k: 'content_exclude', label: 'Exclude elements/classes', type: 'text', hint: 'CSS selector, e.g. nav, footer' },
      { k: 'near_dup_threshold', label: 'Near-duplicate threshold (%)', type: 'num' },
      { k: 'ignore_paginated_dupes', label: 'Ignore paginated URLs for dupes', type: 'bool' },
    ]},
    { group: 'Spelling & grammar', items: [
      { k: 'spelling_enrich', label: 'Check spelling & grammar', type: 'bool', hint: 'see Settings → Integrations for the backend' },
      { k: 'spelling_language', label: 'Language', type: 'text', hint: 'auto = from <html lang>, or e.g. en-GB' },
      { k: 'spelling_ignore', label: 'Ignore words', type: 'text', hint: 'comma-separated' },
    ]},
  ]},
  { id: 'segments', label: 'Segments', groups: [
    { group: 'Segment rules - first match wins (order = priority)', items: [
      { k: '__segments__', type: 'segments' },
    ]},
  ]},
  { id: 'modes', label: 'List mode', groups: [
    { group: 'List mode - check exactly these URLs, no link discovery', items: [
      { k: 'list_mode', label: 'Enable list mode', type: 'bool' },
      { k: 'list_urls', label: 'URL list', type: 'urls', hint: 'one per line - non-URL lines are ignored, so raw exports paste in as-is' },
    ]},
  ]},
  { id: 'custom', label: 'Custom', groups: [
    { group: 'Custom extraction + search', items: [ { k: '__custom__', type: 'custom' } ] },
  ]},
  { id: 'advanced', label: 'Advanced', groups: [
    { group: 'Advanced', items: [
      { k: 'ignore_non_indexable_issues', label: 'Ignore non-indexable for issues', type: 'bool' },
      { k: 'respect_noindex', label: 'Respect noindex (hide from UI)', type: 'bool' },
      { k: 'respect_canonical', label: 'Respect canonical (hide from UI)', type: 'bool' },
      { k: 'assume_html', label: 'Assume pages are HTML', type: 'bool' },
      { k: 'extract_srcset', label: 'Extract images from IMG srcset', type: 'bool' },
      { k: 'cdns', label: 'CDNs (treat as internal)', type: 'text', hint: 'domains, comma-sep' },
      { k: 'html_validation', label: 'Perform HTML validation', type: 'bool', hint: 'DOCTYPE, lang, charset, head-element checks' },
    ]},
  ]},
  { id: 'integrations', label: 'APIs', groups: [
    { group: 'API enrichment - connect providers under Settings → Integrations', items: [
      { k: 'psi_enrich', label: 'PageSpeed Insights (CWV)', type: 'bool' },
      { k: 'gsc_enrich', label: 'Google Search Console', type: 'bool' },
      { k: 'ga4_enrich', label: 'Google Analytics 4', type: 'bool', hint: 'needs the Google connection' },
      { k: 'ga4_property_id', label: 'GA4 property ID', type: 'text', hint: 'e.g. 498765432 - listed under Settings → Integrations' },
      { k: 'ga4_days', label: 'GA4 date range (days)', type: 'num' },
      { k: 'ga4_fuzzy_match', label: 'Fuzzy URL matching', type: 'bool', hint: 'try trailing-slash / lowercase variants' },
    ]},
    { group: 'Semantic analysis', items: [
      { k: 'embeddings_enrich', label: 'Semantic similarity + low relevance', type: 'bool', hint: 'needs an embeddings provider' },
      { k: 'embeddings_similarity_threshold', label: 'Similarity threshold', type: 'text', hint: '0–1 (default 0.92)' },
    ]},
  ]},
];

const ITEMS = TABS.flatMap(t => t.groups.flatMap(g => g.items))
  .filter(f => f.type !== 'custom' && f.type !== 'segments');
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function parseHeaders(text) {
  const out = {};
  (text || '').split('\n').forEach(line => {
    const i = line.indexOf(':');
    if (i > 0) { const k = line.slice(0, i).trim(); const v = line.slice(i + 1).trim(); if (k) out[k] = v; }
  });
  return out;
}
function parseRules(text) {
  return (text || '').split('\n').map(line => {
    const i = line.indexOf('=>');
    if (i < 0) return null;
    const pattern = line.slice(0, i).trim();
    return pattern ? { pattern, replacement: line.slice(i + 2).trim() } : null;
  }).filter(Boolean);
}

export class ConfigPanel {
  constructor(container, apiBase) {
    this.container = container;
    this.apiBase = apiBase;
    this.profiles = [];
    this.currentId = null;
    this.activeTab = 'spider';
    this.render();
  }

  async load() {
    try { this.profiles = await (await fetch(`${this.apiBase}/profiles`)).json(); }
    catch { this.profiles = []; }
    if (!this.currentId) {
      const def = this.profiles.find(p => p.is_default) || this.profiles[0];
      this.currentId = def ? def.id : null;
    }
    this._syncProfileSelect();
    this._fillFields();
  }

  _current() { return this.profiles.find(p => p.id === this.currentId); }

  _syncProfileSelect() {
    const sel = this.container.querySelector('#cfg-profile');
    sel.innerHTML = this.profiles.map(p =>
      `<option value="${p.id}">${esc(p.name)}${p.is_default ? ' · default' : ''}${p.is_preset ? ' (preset)' : ''}</option>`
    ).join('');
    if (this.currentId) sel.value = String(this.currentId);
    const p = this._current();
    this.container.querySelector('#cfg-delete').disabled = !p || p.is_preset;
    this.container.querySelector('#cfg-badge').textContent = p && p.is_default ? 'Default' : '';
  }

  _fillFields() {
    const d = (this._current() || {}).data || {};
    ITEMS.forEach(f => {
      const el = this.container.querySelector(`[data-k="${f.k}"]`);
      if (!el) return;
      if (f.type === 'bool') el.checked = !!d[f.k];
      else if (f.type === 'headers') el.value = Object.entries(d[f.k] || {}).map(([k, v]) => `${k}: ${v}`).join('\n');
      else if (f.type === 'rules') el.value = (d[f.k] || []).map(r => `${r.pattern} => ${r.replacement}`).join('\n');
      else el.value = d[f.k] ?? '';
    });
    this._renderCustom();
  }

  _collect() {
    const out = {};
    ITEMS.forEach(f => {
      const el = this.container.querySelector(`[data-k="${f.k}"]`);
      if (!el) return;
      if (f.type === 'bool') out[f.k] = el.checked;
      else if (f.type === 'num') out[f.k] = parseInt(el.value, 10) || 0;
      else if (f.type === 'headers') out[f.k] = parseHeaders(el.value);
      else if (f.type === 'rules') out[f.k] = parseRules(el.value);
      else out[f.k] = el.value;
    });
    return out;
  }

  async _save() {
    const p = this._current();
    if (!p) return;
    try {
      await fetch(`${this.apiBase}/profiles/${p.id}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: { ...this._collect(), ...this._collectCustom() } }),
      });
      toast.show(`Saved "${p.name}".`, 'success');
      await this.load();
    } catch { toast.show('Save failed.', 'error'); }
  }

  async _saveAs() {
    const name = prompt('New profile name:');
    if (!name) return;
    try {
      const r = await fetch(`${this.apiBase}/profiles`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, data: { ...this._collect(), ...this._collectCustom() } }),
      });
      const p = await r.json();
      this.currentId = p.id;
      toast.show(`Created "${name}".`, 'success');
      await this.load();
    } catch { toast.show('Could not create profile.', 'error'); }
  }

  async _setDefault() {
    const p = this._current();
    if (!p) return;
    await fetch(`${this.apiBase}/profiles/${p.id}/default`, { method: 'POST' });
    toast.show(`"${p.name}" is now the default.`, 'success');
    await this.load();
  }

  async _delete() {
    const p = this._current();
    if (!p || p.is_preset) return;
    if (!confirm(`Delete profile "${p.name}"?`)) return;
    const r = await fetch(`${this.apiBase}/profiles/${p.id}`, { method: 'DELETE' });
    if (r.ok) { this.currentId = null; toast.show('Profile deleted.', 'success'); await this.load(); }
    else { toast.show('Could not delete.', 'error'); }
  }

  _field(f) {
    if (f.type === 'segments') {
      return `<div class="cfg-custom-wrap">
        <p class="cfg-hint" style="margin-bottom:10px;">Classify every crawled URL by regex. Rules cascade top-down - the first match wins - so put the most specific rule first. Segments colour the architecture map and filter the Explorer.</p>
        <div id="cfg-segments"></div>
        <button class="btn btn-secondary btn-sm" id="cfg-add-seg" style="margin-top:8px;">+ Add segment</button>
      </div>`;
    }
    if (f.type === 'custom') {
      return `<div class="cfg-custom-wrap">
        <h4>Custom extraction <span class="cfg-hint">CSS selector / XPath / regex</span></h4>
        <div id="cfg-extractors"></div>
        <button class="btn btn-secondary btn-sm" id="cfg-add-ex" style="margin-top:8px;">+ Add extractor</button>
        <h4 style="margin-top:var(--space-3);">Custom search <span class="cfg-hint">count regex matches per page</span></h4>
        <div id="cfg-searches"></div>
        <button class="btn btn-secondary btn-sm" id="cfg-add-search" style="margin-top:8px;">+ Add search</button>
      </div>`;
    }
    const planned = f.planned ? ' <span class="cfg-planned" title="Persisted with the profile; engine support in a later phase">Planned</span>' : '';
    let input;
    if (f.type === 'bool') input = `<input type="checkbox" data-k="${f.k}">`;
    else if (f.type === 'num') input = `<input type="number" class="wizard-input cfg-num" data-k="${f.k}">`;
    else if (f.type === 'ua') input = `<select class="filter-select cfg-ua" data-k="${f.k}">${UA_PRESETS.map(u => `<option value="${esc(u.value)}">${u.label}</option>`).join('')}</select>`;
    else if (f.type === 'select') input = `<select class="filter-select" data-k="${f.k}">${f.options.map(o => `<option value="${o.value}">${o.label}</option>`).join('')}</select>`;
    else if (f.type === 'headers' || f.type === 'rules') input = `<textarea class="wizard-input mono cfg-area" rows="3" data-k="${f.k}"></textarea>`;
    else if (f.type === 'urls') input = `<textarea class="wizard-input mono cfg-area" rows="8" data-k="${f.k}" placeholder="https://example.com/page-1&#10;https://example.com/page-2"></textarea>`;
    else input = `<input type="text" class="wizard-input cfg-text" data-k="${f.k}">`;
    const wide = ['headers', 'rules', 'urls', 'text'].includes(f.type) ? ' cfg-row-wide' : '';
    const help = HELP[f.k]
      ? ` <button type="button" class="help" aria-label="Help" tabindex="0">?<span class="help-tip">${esc(HELP[f.k])}</span></button>`
      : '';
    return `<div class="settings-row${wide}">
      <label>${f.label}${help}${planned}${f.hint ? ` <span class="cfg-hint">${f.hint}</span>` : ''}</label>
      ${input}
    </div>`;
  }

  render() {
    const tabBar = TABS.map(t =>
      `<button class="cfg-tab${t.id === this.activeTab ? ' active' : ''}" data-tab="${t.id}">${t.label}</button>`).join('');
    const panels = TABS.map(t => `
      <div class="cfg-panel${t.id === this.activeTab ? ' active' : ''}" data-panel="${t.id}">
        ${t.groups.map(g => `
          <div class="card cfg-group">
            <h3>${g.group}</h3>
            <div class="cfg-fields">${g.items.map(f => this._field(f)).join('')}</div>
          </div>`).join('')}
      </div>`).join('');

    this.container.innerHTML = `
      <div class="flex" style="justify-content: space-between; align-items: center; margin-bottom: var(--space-1);">
        <h1>Crawl settings</h1>
      </div>
      <p style="margin-bottom: var(--space-3);">Save your favourite audit settings as profiles you can reuse. Every option here controls how Scrawly checks a site.</p>

      <div class="card cfg-bar">
        <div class="cfg-bar-left">
          <label class="cfg-bar-label">Profile</label>
          <select id="cfg-profile" class="filter-select" style="min-width: 220px;"></select>
          <span id="cfg-badge" class="badge badge-notice"></span>
        </div>
        <div class="flex gap-2">
          <button class="btn btn-secondary" id="cfg-saveas">Save As…</button>
          <button class="btn btn-secondary" id="cfg-default">Set Default</button>
          <button class="btn btn-link" id="cfg-delete">Delete</button>
          <button class="btn btn-primary" id="cfg-save">Save</button>
        </div>
      </div>

      <div class="card cfg-group cfg-preset-card">
        <h3>Tech-stack preset <span class="cfg-hint">applies sensible exclude rules + render defaults for the stack</span></h3>
        <div class="cfg-preset-row">
          <select id="cfg-tech" class="filter-select"><option value=""> - choose a stack / CMS - </option></select>
          <select id="cfg-subcat" class="filter-select" style="display:none"><option value=""> - type - </option></select>
          <button class="btn btn-secondary" id="cfg-apply-preset">Apply preset</button>
        </div>
        <div id="cfg-preset-note" class="cfg-hint" style="margin-top: 8px;"></div>
      </div>

      <div class="cfg-tabs">${tabBar}</div>
      <div class="cfg-panels">${panels}</div>`;

    const $ = (s) => this.container.querySelector(s);
    $('#cfg-profile').addEventListener('change', (e) => {
      this.currentId = parseInt(e.target.value, 10);
      this._syncProfileSelect();
      this._fillFields();
    });
    $('#cfg-save').addEventListener('click', () => this._save());
    $('#cfg-saveas').addEventListener('click', () => this._saveAs());
    $('#cfg-default').addEventListener('click', () => this._setDefault());
    $('#cfg-delete').addEventListener('click', () => this._delete());
    $('#cfg-add-ex').addEventListener('click', () => this._addExtractorRow());
    $('#cfg-add-search').addEventListener('click', () => this._addSearchRow());
    $('#cfg-add-seg').addEventListener('click', () => this._addSegmentRow());
    $('#cfg-tech').addEventListener('change', () => this._syncSubcat());
    $('#cfg-apply-preset').addEventListener('click', () => this._applyPreset());
    this.container.querySelectorAll('.cfg-tab').forEach(b =>
      b.addEventListener('click', () => this._switchTab(b.dataset.tab)));
    this._loadPresets();
  }

  _switchTab(id) {
    this.activeTab = id;
    this.container.querySelectorAll('.cfg-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === id));
    this.container.querySelectorAll('.cfg-panel').forEach(p => p.classList.toggle('active', p.dataset.panel === id));
  }

  async _loadPresets() {
    try { this.presets = await (await fetch(`${this.apiBase}/presets`)).json(); }
    catch { this.presets = {}; }
    const sel = this.container.querySelector('#cfg-tech');
    if (!sel) return;
    sel.innerHTML = '<option value=""> - choose a stack / CMS - </option>' +
      Object.entries(this.presets).map(([k, v]) => `<option value="${k}">${v.label}</option>`).join('');
  }

  _syncSubcat() {
    const tech = this.container.querySelector('#cfg-tech').value;
    const sub = this.container.querySelector('#cfg-subcat');
    const subs = (this.presets?.[tech]?.subcategories) || {};
    const keys = Object.keys(subs);
    if (keys.length) {
      sub.innerHTML = '<option value=""> - type (optional) - </option>' +
        keys.map(k => `<option value="${k}">${subs[k]}</option>`).join('');
      sub.style.display = '';
    } else { sub.style.display = 'none'; sub.innerHTML = ''; }
  }

  async _applyPreset() {
    const tech = this.container.querySelector('#cfg-tech').value;
    if (!tech) { toast.show('Choose a tech stack first.', 'error'); return; }
    const subcat = this.container.querySelector('#cfg-subcat').value || '';
    try {
      const d = await (await fetch(`${this.apiBase}/presets/${tech}?subcategory=${encodeURIComponent(subcat)}`)).json();
      const setV = (k, v) => { const el = this.container.querySelector(`[data-k="${k}"]`); if (el) el.value = v; };
      const setC = (k, v) => { const el = this.container.querySelector(`[data-k="${k}"]`); if (el) el.checked = v; };
      if (d.exclude_patterns != null) setV('exclude_patterns', d.exclude_patterns);
      if (d.js_render != null) setC('js_render', d.js_render);
      this.container.querySelector('#cfg-preset-note').textContent =
        `Applied - excludes ${(d.exclude_patterns || '').split(',').filter(Boolean).length} pattern(s), JS render ${d.js_render ? 'on' : 'off'}. Review the Spider/Rendering tabs & Save As a profile.`;
      toast.show('Preset applied to the fields - Save As a profile to keep it.', 'success');
    } catch { toast.show('Could not load preset.', 'error'); }
  }

  _addExtractorRow(item = {}) {
    const box = this.container.querySelector('#cfg-extractors');
    const row = document.createElement('div');
    row.className = 'cfg-cx-row';
    row.innerHTML = `
      <input class="wizard-input cx-name" placeholder="name" value="${esc(item.name || '')}">
      <select class="filter-select cx-source">
        <option value="css"${(item.source || 'css') === 'css' ? ' selected' : ''}>CSS</option>
        <option value="xpath"${item.source === 'xpath' ? ' selected' : ''}>XPath</option>
        <option value="regex"${item.source === 'regex' ? ' selected' : ''}>Regex</option>
      </select>
      <input class="wizard-input cx-expr mono" placeholder="selector or regex" value="${esc(item.expr || '')}">
      <input class="wizard-input cx-attr" placeholder="attr (css)" value="${esc(item.attr || '')}" style="width:80px;">
      <button class="btn btn-link cx-del" title="Remove">✕</button>`;
    row.querySelector('.cx-del').addEventListener('click', () => row.remove());
    box.appendChild(row);
  }

  _addSegmentRow(item = {}) {
    const box = this.container.querySelector('#cfg-segments');
    const row = document.createElement('div');
    row.className = 'cfg-cx-row';
    row.innerHTML = `
      <input class="wizard-input sg-name" placeholder="segment name" value="${esc(item.name || '')}">
      <input class="wizard-input sg-pattern mono" placeholder="URL regex - e.g. ^https://ex\\.com/blog/" value="${esc(item.pattern || '')}">
      <button class="btn btn-link sg-up" title="Move up (higher priority)">↑</button>
      <button class="btn btn-link sg-del" title="Remove">✕</button>`;
    row.querySelector('.sg-del').addEventListener('click', () => row.remove());
    row.querySelector('.sg-up').addEventListener('click', () => {
      const prev = row.previousElementSibling;
      if (prev) box.insertBefore(row, prev);   // order == cascade priority
    });
    box.appendChild(row);
  }

  _collectSegments() {
    return [...this.container.querySelectorAll('#cfg-segments .cfg-cx-row')]
      .map(r => ({
        name: r.querySelector('.sg-name').value.trim(),
        pattern: r.querySelector('.sg-pattern').value.trim(),
      }))
      .filter(s => s.name && s.pattern);
  }

  _addSearchRow(item = {}) {
    const box = this.container.querySelector('#cfg-searches');
    const row = document.createElement('div');
    row.className = 'cfg-cx-row';
    row.innerHTML = `
      <input class="wizard-input cs-name" placeholder="name" value="${esc(item.name || '')}">
      <input class="wizard-input cs-regex mono" placeholder="regex" value="${esc(item.regex || '')}">
      <button class="btn btn-link cs-del" title="Remove">✕</button>`;
    row.querySelector('.cs-del').addEventListener('click', () => row.remove());
    box.appendChild(row);
  }

  _renderCustom() {
    const d = (this._current() || {}).data || {};
    const ex = this.container.querySelector('#cfg-extractors');
    const se = this.container.querySelector('#cfg-searches');
    const sg = this.container.querySelector('#cfg-segments');
    if (ex) ex.innerHTML = '';
    if (se) se.innerHTML = '';
    if (sg) sg.innerHTML = '';
    (d.custom_extractors || []).forEach(i => this._addExtractorRow(i));
    (d.custom_searches || []).forEach(i => this._addSearchRow(i));
    (d.segments || []).forEach(i => this._addSegmentRow(i));
  }

  _collectCustom() {
    const extractors = [...this.container.querySelectorAll('#cfg-extractors .cfg-cx-row')]
      .map(r => ({
        name: r.querySelector('.cx-name').value.trim(),
        source: r.querySelector('.cx-source').value,
        expr: r.querySelector('.cx-expr').value.trim(),
        attr: r.querySelector('.cx-attr').value.trim() || undefined,
      })).filter(e => e.name && e.expr);
    const searches = [...this.container.querySelectorAll('#cfg-searches .cfg-cx-row')]
      .map(r => ({
        name: r.querySelector('.cs-name').value.trim(),
        regex: r.querySelector('.cs-regex').value.trim(),
      })).filter(s => s.name && s.regex);
    return {
      custom_extractors: extractors,
      custom_searches: searches,
      segments: this._collectSegments(),
    };
  }
}
