// Theme controller — light / dark with OS fallback + localStorage persistence.
//
// Contract:
//   • No stored value  → follow the OS (prefers-color-scheme) live.
//   • Stored 'light'/'dark' → explicit choice, wins over the OS.
// The <head> FOUC guard in index.html applies the stored value before first
// paint; this module owns runtime toggling and keeps things in sync.
//
// Every theme change is pure CSS (data-theme on <html> swaps token values), so
// components never re-render. We still emit a `themechange` event for any code
// that needs to read computed token values (e.g. D3 charts reading CSS vars).

const KEY = 'scrawly-theme';
const root = document.documentElement;
const mql = window.matchMedia('(prefers-color-scheme: dark)');

function stored() {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

/** The theme actually in effect right now: 'light' | 'dark'. */
export function resolvedTheme() {
  const s = stored();
  if (s === 'light' || s === 'dark') return s;
  return mql.matches ? 'dark' : 'light';
}

function emit() {
  document.dispatchEvent(
    new CustomEvent('themechange', { detail: { theme: resolvedTheme() } }),
  );
}

/** Apply a theme: 'light' | 'dark' | 'system' (clears the override). */
export function applyTheme(theme) {
  if (theme === 'system' || theme == null) {
    root.removeAttribute('data-theme');
    try { localStorage.removeItem(KEY); } catch { /* ignore */ }
  } else {
    root.setAttribute('data-theme', theme);
    try { localStorage.setItem(KEY, theme); } catch { /* ignore */ }
  }
  emit();
}

/** Flip between light and dark, pinning the choice. */
export function toggleTheme() {
  applyTheme(resolvedTheme() === 'dark' ? 'light' : 'dark');
}

const SUN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"></path></svg>';
const MOON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>';

/**
 * Build the top-bar theme toggle button. Shows the icon of the current mode
 * (moon in dark, sun in light) and repaints on every theme change.
 */
export function createThemeToggle() {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'icon-btn theme-toggle';
  btn.setAttribute('aria-label', 'Toggle color theme');

  const paint = () => {
    const dark = resolvedTheme() === 'dark';
    btn.innerHTML = dark ? MOON : SUN;
    btn.title = dark ? 'Dark theme. Switch to light' : 'Light theme. Switch to dark';
  };

  btn.addEventListener('click', toggleTheme);
  document.addEventListener('themechange', paint);
  paint();
  return btn;
}

/** Wire live OS-preference updates (only relevant while no override is set). */
export function initTheme() {
  mql.addEventListener('change', () => {
    if (!stored()) emit();
  });
}
