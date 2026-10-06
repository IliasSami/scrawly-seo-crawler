// ui/components/external.js
// Open a link outside the app. Inside the desktop window (pywebview) new windows
// and target=_blank links do nothing, so links go through the native bridge,
// which hands them to the user's default browser or mail app. In a normal
// browser this is a plain new tab.

const SAFE = /^(https?:|mailto:)/i;

export function openExternal(url) {
  const href = String(url || '');
  if (!SAFE.test(href)) return false;
  const api = window.pywebview && window.pywebview.api;
  if (api && typeof api.open_external === 'function') {
    api.open_external(href);
    return true;
  }
  window.open(href, '_blank', 'noopener');
  return true;
}

// Route every external link click through openExternal while inside the desktop
// window, so links in reports, issue details and help text all work there too.
export function routeExternalLinks() {
  document.addEventListener('click', (e) => {
    const a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!a) return;
    const href = a.getAttribute('href') || '';
    if (!SAFE.test(href)) return;
    const api = window.pywebview && window.pywebview.api;
    if (!api || typeof api.open_external !== 'function') return; // browser: default
    e.preventDefault();
    api.open_external(href);
  });
}

// --- Saving files ------------------------------------------------------------
// Downloads (<a download>, blob URLs) are ignored inside the desktop window, so
// files are saved through the native bridge's Save dialog there. In a browser
// they download normally. Each returns 'saved' | 'cancelled' | 'failed'.

function _bridge() { return window.pywebview && window.pywebview.api; }

function _browserDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function _outcome(result) {
  if (result === null || result === undefined) return 'cancelled';
  return result ? 'saved' : 'failed';
}

// Save a file served by the local backend (path must start with /api/).
export async function saveDownload(apiPath, filename, owner = '') {
  const api = _bridge();
  if (api && typeof api.save_download === 'function') {
    return _outcome(await api.save_download(apiPath, owner, filename));
  }
  try {
    const res = await fetch(apiPath);
    if (!res.ok) return 'failed';
    _browserDownload(await res.blob(), filename);
    return 'saved';
  } catch { return 'failed'; }
}

// Save text produced in the UI (CSV exports and the like).
export async function saveText(filename, text, mime = 'text/plain') {
  const api = _bridge();
  if (api && typeof api.save_text === 'function') {
    return _outcome(await api.save_text(filename, text));
  }
  try {
    _browserDownload(new Blob([text], { type: `${mime};charset=utf-8` }), filename);
    return 'saved';
  } catch { return 'failed'; }
}
