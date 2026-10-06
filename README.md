<p align="center">
  <img src="assets/icons/scrawly.png" width="112" height="112" alt="Scrawly logo">
</p>

<h1 align="center">Scrawly: the free, open-source SEO crawler and site audit tool</h1>

<p align="center">
  <b>Free technical SEO, GEO and AI-search audits for any website.</b><br>
  A free alternative to Screaming Frog and Sitebulb. No account, no page cap, no subscription.
</p>

<p align="center">
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/license-MIT-6366f1"></a>
  <img alt="macOS, Windows and Linux" src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-6366f1">
  <img alt="250 SEO checks" src="https://img.shields.io/badge/checks-250-a855f7">
  <a href="https://github.com/IliasSami/scrawly-seo-crawler/releases"><img alt="Latest release" src="https://img.shields.io/github/v/release/IliasSami/scrawly-seo-crawler?color=a855f7"></a>
</p>

**Scrawly** is a free, open-source desktop SEO crawler and technical site audit tool for
macOS, Windows and Linux. It crawls a website, runs **250 technical SEO, GEO (Generative
Engine Optimization) and agentic-web checks** on every page, maps the site's architecture,
and explains in plain language what to fix. For WordPress sites it can also apply safe,
reversible fixes. Scrawly is created by **[Ilias Sami](https://iliassami.com/)** and released
for the SEO community under the MIT License.

> **In one sentence:** Scrawly is a free desktop app that audits any website for the
> technical issues that affect Google rankings and AI-search visibility (ChatGPT,
> Perplexity, Google AI Overviews), with no account and no page limit.

---

## Contents

- [Install in one line](#install-in-one-line)
- [What Scrawly checks](#what-scrawly-checks)
- [Free alternative to Screaming Frog and Sitebulb](#a-free-alternative-to-screaming-frog-and-sitebulb)
- [GEO and AEO: auditing for AI search](#geo-and-aeo-auditing-for-ai-search)
- [Fix WordPress issues safely](#fix-wordpress-issues-safely)
- [Privacy](#privacy-your-audits-stay-on-your-computer)
- [FAQ](#frequently-asked-questions)
- [Documentation](#documentation) · [Contributing](#contributing-and-feedback) · [License](#license-and-credits)

## Install in one line

Scrawly installs itself, adds an app icon (Applications on macOS, the Start Menu on
Windows, your app menu on Linux), and keeps itself up to date.

**macOS or Linux** (Terminal):

```bash
curl -fsSL https://raw.githubusercontent.com/IliasSami/scrawly-seo-crawler/main/install.sh | bash
```

**Windows** (PowerShell):

```powershell
irm https://raw.githubusercontent.com/IliasSami/scrawly-seo-crawler/main/install.ps1 | iex
```

Then open **Scrawly** like any other app. There is nothing to sign up for.

<details>
<summary><b>Prefer to install by hand?</b></summary>

You need **Python 3.11 or newer** and **git**. (Node.js is not needed: releases ship the
interface prebuilt.)

```bash
git clone https://github.com/IliasSami/scrawly-seo-crawler.git Scrawly
cd Scrawly
python3 scripts/install.py        # Windows: py scripts\install.py
```

The installer creates a private Python environment, downloads the crawler browser
(about 150 MB, once), and adds Scrawly to your apps. Full guide, Linux notes and
troubleshooting: **[docs/DESKTOP.md](docs/DESKTOP.md)**.
</details>

## What Scrawly checks

Scrawly runs **250 checks** grouped into 23 areas. Every finding comes with why it matters,
how to fix it, and the exact pages affected.

| Area | Examples |
|---|---|
| **Crawlability and indexability** | robots.txt rules, meta robots and `X-Robots-Tag`, noindex conflicts, orphan pages, crawl depth |
| **Response codes and redirects** | 4xx and 5xx pages, redirect chains and loops, temporary vs permanent redirects |
| **Titles, meta and headings** | missing, duplicate, too long or too short titles; pixel-width truncation; meta descriptions too thin for AI; H1 and heading order |
| **Canonicalization** | missing, conflicting, cross-domain or non-indexable canonicals |
| **Content quality** | thin and duplicate content, near-duplicates, readability |
| **Structured data** | JSON-LD, Microdata and RDFa, with schema validation |
| **Internal linking and architecture** | link graph, internal PageRank ("authority"), broken links, generic anchors |
| **Performance and Core Web Vitals** | PageSpeed Insights lab and field (CrUX) data, TTFB, page weight |
| **AI search readiness (GEO)** | which AI crawlers you allow or block, `llms.txt`, AI citation readiness |
| **Agentic web** | how well AI agents can read and operate your site |
| **And more** | images and alt text, hreflang, XML sitemaps, security and TLS, mobile, JavaScript rendering, pagination, WordPress specifics |

The full catalogue, with severity and fix tier for every check, is in
[docs/CHECK_MANIFEST.yaml](docs/CHECK_MANIFEST.yaml).

**Also included:** JavaScript rendering, custom extraction, saved crawl profiles, a 3D site
graph and depth tree, crawl-to-crawl comparison, scheduled audits with regression alerts,
Google Search Console and GA4 data, branded HTML and PDF reports, an AI writer for titles
and meta descriptions (bring your own AI key), and an MCP server so AI assistants can work
with your audits ([docs/MCP.md](docs/MCP.md)).

## A free alternative to Screaming Frog and Sitebulb

Screaming Frog SEO Spider and Sitebulb are excellent tools. Scrawly is a free, open-source
option for people who want a deep technical audit without a licence, plus checks for AI search.

| | Screaming Frog / Sitebulb | **Scrawly** |
|---|---|---|
| Price | Paid licence or subscription (limited free tier or trial) | **Free and open-source (MIT)** |
| Account or licence key | Needed for full use | **None** |
| Page limit | The free tier is capped | **No cap: you set the limit** |
| AI search (GEO) and agentic-web checks | Some, depending on version | **A dedicated set: AI crawler access, `llms.txt`, citation and agent readiness** |
| Fixes | Report only | **Safe, reversible fixes on WordPress** |
| Source code | Closed | **Open: read, audit, contribute** |

Scrawly is independent and not affiliated with Screaming Frog Ltd or Sitebulb.

## GEO and AEO: auditing for AI search

Search now includes AI answer engines that read your pages and decide whether to cite
you. Scrawly audits for **Generative Engine Optimization (GEO)** and **Answer Engine
Optimization (AEO)**:

- **AI crawler access:** a matrix of which AI bots (GPTBot, ClaudeBot, PerplexityBot,
  Google-Extended, OAI-SearchBot and others) your robots.txt and firewall allow or block.
- **`llms.txt`:** whether you publish a curated index for AI systems, and its quality.
- **Meta as AI context:** a description is often the first thing an AI reads about a page,
  so Scrawly flags descriptions too thin to understand and can draft an entity-rich one
  from the page's own content.
- **Entities and structured data:** the schema and named entities that help search engines
  and AI understand what a page is about.

## Fix WordPress issues safely

Connect a WordPress site with the lightweight **Scrawly Connector** plugin and Scrawly can
fix titles, meta descriptions, canonicals and redirects for you:

- a **rollback snapshot is saved before every change**, and every fix can be undone;
- changes to the live site always **ask for your confirmation first**;
- higher-risk issues are **never auto-applied**; they're flagged for a person to review.

See [docs/WORDPRESS_CONNECTOR.md](docs/WORDPRESS_CONNECTOR.md). Every other site (Shopify,
Wix, Webflow, Next.js, custom) gets the full read-only audit.

## Privacy: your audits stay on your computer

Scrawly has no accounts and no analytics. Your crawls, findings and reports are stored on
your computer only. Scrawly connects to:

- the websites **you** choose to audit;
- GitHub, to check for updates (turn off with `SCRAWLY_AUTO_UPDATE=0`);
- services **you** configure, such as PageSpeed Insights, Google Search Console or your AI provider;
- the feedback service, **only when you click Send** on a feedback note.

The app's local engine only accepts requests from the Scrawly window itself, so other
websites can't use it. Report security issues as described in [SECURITY.md](SECURITY.md).

## Frequently asked questions

**What is Scrawly?**
Scrawly is a free, open-source SEO crawler and technical site audit tool that runs as a
desktop app on macOS, Windows and Linux. It checks every page of a website for 250
technical SEO, GEO and agentic-web issues and explains how to fix them.

**Is there a free alternative to Screaming Frog?**
Yes. Scrawly is a free, open-source alternative to Screaming Frog SEO Spider and Sitebulb.
It has no page cap and no licence, and it adds AI-search (GEO) checks and safe WordPress fixes.

**Is Scrawly really free?**
Yes. Scrawly is free and open-source under the MIT License, with no account, subscription or
usage limit. Audits run on your own computer, so there is no per-crawl cost.

**Do I need to create an account?**
No. Install it and start auditing. There is no sign-up, login or approval.

**Does Scrawly work on websites that aren't WordPress?**
Yes. The audit works on any website. Only the one-click fixes are WordPress-specific.

**Can Scrawly check AI search and GEO readiness?**
Yes. It checks AI crawler access, `llms.txt`, whether titles and descriptions give AI enough
context, structured data, and how well AI agents can use the site.

**How many pages can Scrawly crawl?**
There is no fixed cap. You choose the limit per audit; how far you can go depends on your
computer and the website.

**Who made Scrawly?**
Scrawly was created by [Ilias Sami](https://iliassami.com/), an SEO consultant, as a free
contribution to the SEO community. Contact: [me@iliassami.com](mailto:me@iliassami.com).

## Documentation

- [docs/DESKTOP.md](docs/DESKTOP.md): install, update, Linux notes and troubleshooting
- [docs/WORDPRESS_CONNECTOR.md](docs/WORDPRESS_CONNECTOR.md): the WordPress fix plugin
- [docs/MCP.md](docs/MCP.md): use your audits from AI assistants (MCP)
- [docs/CHECK_MANIFEST.yaml](docs/CHECK_MANIFEST.yaml): the full check catalogue
- [CHANGELOG.md](CHANGELOG.md): what changed in each release

## Contributing and feedback

Scrawly gets better from community input:

- **In the app:** click the speech-bubble icon (**Send feedback**) at the bottom of the left
  bar. No GitHub account needed.
- **On GitHub:** [open an issue](https://github.com/IliasSami/scrawly-seo-crawler/issues) or
  a pull request. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License and credits

Scrawly is released under the [MIT License](LICENSE). Copyright (c) 2026
[Ilias Sami](https://iliassami.com/) ([me@iliassami.com](mailto:me@iliassami.com)).
If you use Scrawly in research or writing, see [CITATION.cff](CITATION.cff).

Built for the SEO community. If Scrawly helps you, a star on GitHub helps others find it.
