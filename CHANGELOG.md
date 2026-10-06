# Changelog

All notable changes to Scrawly. Versions follow [Semantic Versioning](https://semver.org/).

## 1.0.0 (2026-10)

The first public release of **Scrawly Free**: a free, open-source technical SEO and GEO
crawler and site audit tool for macOS, Windows and Linux.

### Highlights

- **No account, no sign-up, no limits.** Install and start auditing.
- **250 checks** across 23 areas: crawlability, indexability, redirects, titles and meta,
  canonicals, content quality, structured data, internal links, Core Web Vitals, AI search
  readiness (GEO), the agentic web, accessibility, security, international and more.
- **Reports** as HTML or PDF, saved wherever you choose.
- **Safe WordPress fixes** with a rollback snapshot before every change.
- **One-line installers** for macOS, Linux and Windows that add Scrawly to your apps.
- **Automatic updates** that only install versions whose tests passed.
- **Send feedback** from inside the app, with an email or GitHub fallback.

### Reliability and security work in this release

- PDF reports: the crawler browser is now downloaded automatically when missing, which
  fixes failed PDF saves after an update.
- The local engine only accepts requests from the Scrawly window.
- Crawled page content can never run as code in the app.
- robots.txt is respected for every page, not just the first one.
- Server errors (5xx) and rate limits (429) are recorded instead of silently dropped, and a
  failing robots.txt or sitemap no longer stops an audit.
- Sites whose address redirects to another host (for example to `www`) and international
  (IDN) domains are crawled fully.
- Crawls fetch pages in parallel again, as configured.
- Images and other files linked from pages are no longer audited as pages.
- The WordPress fix agent uses an explicit list of which issues it may fix, asks before
  any live change, and reverts on the same site the fix was made on.
- TLS certificate expiry and robots.txt content-type checks now run.
- Dates and times display in your local time zone.
