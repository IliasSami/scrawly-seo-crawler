# Security policy

## Reporting a vulnerability

Please report security problems privately by email to **me@iliassami.com** with
"Scrawly security" in the subject. Include what you found, how to reproduce it, and the
version (shown under **About** in the app). You'll get a reply as soon as possible, and
credit in the release notes if you'd like.

Please don't open a public GitHub issue for a vulnerability until a fix is released.

## Supported versions

Scrawly updates itself, so only the latest release is supported. Security fixes ship as a
new release that installed copies pick up automatically.

## How Scrawly is designed to stay safe

- **Local only.** The app's engine listens only on your own computer (127.0.0.1) and refuses
  requests that don't come from the Scrawly window: it checks the Host and Origin of every
  request and allows no cross-site access, so websites you visit can't control it.
- **No accounts, no analytics.** Scrawly collects nothing about you or your audits. Your data
  stays in your user data folder.
- **Crawled content is untrusted.** Page titles, URLs and other content from audited sites
  are always displayed as text, never run as code, in the app and in reports.
- **Safe WordPress changes.** Every change to a live site captures a rollback snapshot first,
  requires your confirmation, and higher-risk fixes are never applied automatically.
- **Your keys stay yours.** API keys you add (AI provider, PageSpeed) are stored on your
  computer and sent only to the service they belong to.
