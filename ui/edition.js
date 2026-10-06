// ui/edition.js (Free edition)
// Scrawly Free has no accounts, no sign-in, no approvals and no usage limits:
// the app boots straight in and every feature is available to everyone.
// Everything else in the UI talks to the edition only through these exports.

import { mountHelpRail } from './components/help-rail.js';

export function isFree() { return true; }

// One local database; no workspace routing.
export function ownerKey() { return ''; }

// No limits, so every crawl is allowed.
export async function authorizeCrawl() { return { allowed: true, token: null }; }

export async function onCrawlFinished() { /* nothing to count */ }

export async function startApp(boot) {
  boot();
  mountHelpRail();
}
