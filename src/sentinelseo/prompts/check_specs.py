"""Fix prompts for the page-level check registry (245 checks).

Hand-writing 245 specs would produce 245 mediocre ones. Instead this derives a
spec for every registered check from three layers:

  1. **Domain family** — all 23 check domains map to a family that knows which
     artefact the fix touches (robots / templates / headers / assets …), how to
     verify it, and the guidance common to that class of defect. This is what
     makes the prompt land in the right file for the detected stack.
  2. **The check itself** — title and why_it_matters from the registry.
  3. **The finding at runtime** — the Issue's own `recommended_fix`, evidence and
     affected URLs, which is where the real specificity comes from.

Coverage is therefore total by construction: a newly registered check inherits
its family's prompt automatically instead of silently having none.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .engine import PromptSpec


@dataclass(frozen=True)
class Family:
    """Shared shape for one class of defect."""

    artefact: str
    guidance: str
    acceptance: List[str]
    verify: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)


_PAGE_VERIFY = ["curl -sS https://<domain>/<path> | head -40"]
_HEAD_VERIFY = ["curl -sSI https://<domain>/<path>"]

# Keyed by CheckSpec.domain exactly as the registry reports it.
FAMILIES: Dict[str, Family] = {
    "Crawlability & Indexability": Family(
        artefact="robots",
        guidance="Decide deliberately whether each affected URL should be "
                 "crawlable and indexable, then make robots.txt, meta robots and "
                 "X-Robots-Tag agree. Conflicting signals are the usual cause: a "
                 "page allowed in robots.txt but carrying `noindex`, or blocked "
                 "in robots.txt so the `noindex` can never even be read.",
        acceptance=[
            "Each affected URL's robots.txt rule, meta robots tag and "
            "X-Robots-Tag header agree with the intended indexing decision",
            "URLs meant to be indexed return no noindex from any source",
            "URLs meant to stay out are noindex (not merely disallowed)",
        ],
        verify=["curl -sSI https://<domain>/<path> | grep -i x-robots-tag",
                "curl -sS https://<domain>/<path> | grep -i 'name=\"robots\"'"],
    ),
    "Robots directives (file-level)": Family(
        artefact="robots",
        guidance="Fix the directive at its source. Remember robots.txt controls "
                 "crawling, not indexing — a disallowed URL can still be indexed "
                 "from external links, and its noindex will never be seen.",
        acceptance=["robots.txt parses cleanly and its rules match intent",
                    "No rule blocks a URL you need indexed"],
        verify=["curl -sS https://<domain>/robots.txt"],
    ),
    "Response codes & redirects": Family(
        artefact="headers",
        guidance="Resolve each broken or chained response at its source: restore "
                 "the page, or point a single permanent redirect straight at the "
                 "final destination. Never leave a chain — each extra hop loses "
                 "signal and slows both users and crawlers.",
        acceptance=[
            "Every affected URL returns its intended status in ONE hop",
            "No redirect chains (A→B→C) and no redirect loops remain",
            "Permanent moves use 301/308, temporary ones use 302/307",
            "Internal links point at the final destination, not the redirect",
        ],
        verify=["curl -sSIL https://<domain>/<path> | grep -E '^HTTP|^location'"],
    ),
    "Titles, meta and headings": Family(
        artefact="static",
        guidance="Fix these in the template or CMS field that generates them, "
                 "not by hand-editing rendered HTML — otherwise the next content "
                 "change reverts it. Write for the specific page: unique, "
                 "descriptive, and accurate to what the page actually says.",
        acceptance=[
            "Every affected page has exactly one title and one H1",
            "Titles and meta descriptions are unique across the site",
            "They describe the page accurately and are not truncated in SERPs",
            "The change is made in the template/CMS field, so it persists",
        ],
        verify=["curl -sS https://<domain>/<path> | grep -iE '<title>|<h1|name=\"description\"'"],
    ),
    "Content quality": Family(
        artefact="static",
        guidance="Decide per URL: consolidate duplicates behind one canonical, "
                 "expand thin pages into something genuinely useful, or remove "
                 "them and redirect. Do not mass-generate filler text to hit a "
                 "word count — that makes the quality problem worse.",
        acceptance=[
            "Each duplicate cluster resolves to one canonical URL",
            "Remaining pages carry substantive, non-templated content",
            "Removed pages 301 to the closest relevant surviving page",
        ],
        constraints=["Do not auto-generate padding content to inflate word count."],
    ),
    "Canonicalization": Family(
        artefact="static",
        guidance="Every indexable page needs exactly one self-referencing "
                 "canonical unless it is deliberately consolidating into another "
                 "URL. Canonicals must be absolute, return 200, and not chain.",
        acceptance=[
            "Each page has exactly one rel=canonical",
            "It is an absolute https URL that returns 200",
            "It does not point at a redirect, a 404, or a noindex page",
            "Canonical and sitemap/internal links agree on the same URL",
        ],
        verify=["curl -sS https://<domain>/<path> | grep -i 'rel=\"canonical\"'"],
    ),
    "Internal linking & architecture": Family(
        artefact="static",
        guidance="Fix in navigation, templates or content links. Aim to shorten "
                 "the click path to important pages and to give orphaned pages a "
                 "real editorial link from somewhere relevant.",
        acceptance=[
            "No important page is orphaned (zero internal inlinks)",
            "Key pages are reachable within a small number of clicks from home",
            "Internal links point at canonical, 200-returning URLs",
        ],
    ),
    "XML sitemaps": Family(
        artefact="sitemap",
        guidance="The sitemap must list only canonical, indexable, 200-returning "
                 "URLs, and robots.txt must point at it. A sitemap full of "
                 "redirects and 404s actively wastes crawl budget.",
        acceptance=[
            "Sitemap contains only canonical, indexable URLs returning 200",
            "No noindex, redirected or 404 URLs are listed",
            "robots.txt has a `Sitemap:` directive pointing at it",
        ],
        verify=["curl -sS https://<domain>/sitemap.xml | head -30"],
    ),
    "Structured data / schema": Family(
        artefact="static",
        guidance="Emit valid JSON-LD from the template that renders the page, "
                 "with values that match what a user actually sees. Never mark up "
                 "content that is not on the page — that is a manual-action risk.",
        acceptance=[
            "JSON-LD parses and validates against schema.org for its @type",
            "All required properties for the type are present",
            "Marked-up values match the visible page content",
        ],
        verify=["curl -sS https://<domain>/<path> | grep -A5 'application/ld+json'"],
        constraints=["Never mark up content that is not visible on the page."],
    ),
    "Images & media": Family(
        artefact="static",
        guidance="Fix at the template/asset-pipeline level: meaningful alt text "
                 "for content images, empty alt for decorative ones, modern "
                 "formats, explicit dimensions, and lazy-loading below the fold.",
        acceptance=[
            "Content images have descriptive alt text; decorative use alt=\"\"",
            "Images have explicit width/height to prevent layout shift",
            "Oversized images are resized/compressed and served responsively",
        ],
    ),
    "Performance / Core Web Vitals": Family(
        artefact="headers",
        guidance="Address the specific metric: LCP usually means the hero image "
                 "or a render-blocking resource; CLS means missing dimensions or "
                 "late-injected content; INP means long main-thread tasks. Measure "
                 "before and after — do not guess.",
        acceptance=[
            "The affected metric improves into the 'good' band on mobile",
            "No render-blocking resources remain in the critical path",
            "Static assets carry long cache lifetimes and compression",
        ],
        verify=["curl -sSI https://<domain>/<path> | grep -iE 'cache-control|content-encoding'"],
        constraints=["Measure the metric before and after; do not assume a fix worked."],
    ),
    "Mobile": Family(
        artefact="static",
        guidance="Fix responsively in CSS/templates rather than shipping a "
                 "separate mobile page. Check tap-target size, font size, viewport "
                 "meta and horizontal overflow at a 375px viewport.",
        acceptance=[
            "A correct viewport meta tag is present",
            "No horizontal overflow at 375px width",
            "Tap targets are at least ~44x44px and body text >= 12px",
        ],
    ),
    "Security": Family(
        artefact="headers",
        guidance="Set security headers at the server/CDN edge so they apply to "
                 "every response. Roll out CSP in report-only mode first — a "
                 "strict policy applied blind will break the site.",
        acceptance=[
            "The affected security header is present on all HTML responses",
            "HTTPS is enforced and mixed content is eliminated",
            "No functionality regressions after the header is applied",
        ],
        verify=["curl -sSI https://<domain>/ | grep -iE 'strict-transport|content-security|x-frame|x-content-type'"],
        constraints=["Deploy Content-Security-Policy in report-only mode first and "
                     "review violation reports before enforcing it."],
    ),
    "Hreflang / international": Family(
        artefact="static",
        guidance="hreflang must be reciprocal: every URL in a cluster links to "
                 "every other, including itself, plus an x-default. Use valid "
                 "ISO language/region codes and absolute canonical URLs.",
        acceptance=[
            "Every hreflang cluster is fully reciprocal, including self-reference",
            "An x-default is declared",
            "All codes are valid and all URLs are absolute, canonical and 200",
        ],
    ),
    "Pagination": Family(
        artefact="static",
        guidance="Paginated pages should self-canonicalise (not to page 1) and "
                 "remain crawlable, with each page linking clearly to the next "
                 "and previous.",
        acceptance=[
            "Each paginated page self-canonicalises",
            "Paginated URLs are crawlable and internally linked",
        ],
    ),
    "URL structure & hygiene": Family(
        artefact="headers",
        guidance="Fix at the routing/rewrite layer. Settle on one canonical URL "
                 "form (case, trailing slash, protocol, host) and permanently "
                 "redirect every variant to it.",
        acceptance=[
            "One canonical URL form is enforced site-wide",
            "All variants 301 to it in a single hop",
            "Internal links use the canonical form directly",
        ],
        verify=["curl -sSIL https://<domain>/<path> | grep -E '^HTTP|^location'"],
    ),
    "External / outbound links": Family(
        artefact="static",
        guidance="Repair or remove dead outbound links, and set rel attributes "
                 "deliberately (sponsored for paid, ugc for user content, "
                 "nofollow where you do not vouch for the target).",
        acceptance=["No outbound links return 4xx/5xx",
                    "Paid and user-generated links carry the correct rel value"],
    ),
    "JavaScript rendering (response vs render)": Family(
        artefact="static",
        guidance="Primary content, links and meta must exist in the server "
                 "response, not only after hydration. Move critical content to "
                 "SSR/SSG — AI crawlers in particular often do not execute JS.",
        acceptance=[
            "Primary content and internal links are present in the raw HTML",
            "Title, meta description and canonical are server-rendered",
            "`curl` of the page shows the main content without running JS",
        ],
        verify=["curl -sS https://<domain>/<path> | grep -c '<a '",
                "curl -sS https://<domain>/<path> | head -60"],
    ),
    "Accessibility": Family(
        artefact="static",
        guidance="Fix the underlying markup rather than papering over it with "
                 "ARIA: real landmarks, labelled controls, sufficient contrast and "
                 "a sane heading order. This also makes the page legible to agents "
                 "that navigate via the accessibility tree.",
        acceptance=[
            "Every interactive control has an accessible name",
            "Landmarks and heading order are correct and sequential",
            "Colour contrast meets WCAG AA",
            "The violation no longer appears in an axe-core run",
        ],
        constraints=["Prefer native semantic HTML over ARIA attributes."],
    ),
    "AI search readiness (GEO)": Family(
        artefact="robots",
        guidance="Make AI access an explicit decision. Separate training crawlers "
                 "from search/answer crawlers — blocking the latter removes you "
                 "from AI answers and citations. Then make the content itself "
                 "quotable: a direct answer up front, clear headings, visible "
                 "author and dates.",
        acceptance=[
            "AI crawler access is explicitly declared, not accidental",
            "Search/answer crawlers are allowed unless deliberately excluded",
            "Key pages lead with a direct, self-contained answer",
            "Author and freshness signals are visible and marked up",
        ],
        verify=["curl -sS https://<domain>/robots.txt"],
    ),
    "Agentic-web experience (Lighthouse 13.3 Agentic Browsing + beyond)": Family(
        artefact="static",
        guidance="Make the site operable by an agent, not just readable: stable "
                 "accessible names, no post-load layout shifts that move controls "
                 "under a click, and machine-readable entry points for key flows.",
        acceptance=[
            "Interactive elements expose stable, meaningful accessible names",
            "No significant layout shift after load settles",
            "Key flows can be completed without relying on visual-only cues",
        ],
    ),
    "WordPress-specific": Family(
        artefact="static",
        guidance="Make the change in a child theme or a must-use plugin so it "
                 "survives updates. If an SEO plugin owns the setting, change it "
                 "there — a theme-level override will be shadowed.",
        acceptance=[
            "The change persists across theme and plugin updates",
            "No WordPress core file was modified",
            "The setting is not being overridden by an SEO plugin",
        ],
        constraints=["Never edit WordPress core files.",
                     "Take a database/file backup before bulk content changes."],
    ),
    "Analytics, tracking & config (context, mostly info)": Family(
        artefact="static",
        guidance="Fix the measurement setup so the data is trustworthy: one "
                 "analytics instance, correct property, no duplicate tags.",
        acceptance=["Tracking fires exactly once per page view",
                    "The correct property/measurement ID is in use"],
    ),
}

# Fallback for a domain the map has not seen yet, so coverage can never regress
# to "no prompt" when someone registers a new check domain.
DEFAULT_FAMILY = Family(
    artefact="static",
    guidance="Fix the issue at the template, configuration or content source "
             "that produces it, so the change persists across rebuilds.",
    acceptance=["The reported issue no longer occurs on any affected URL",
                "The fix is made at the source, not in generated output"],
    verify=_PAGE_VERIFY,
)


def family_for(domain: str) -> Family:
    return FAMILIES.get(domain, DEFAULT_FAMILY)


def spec_for_check(
    check_id: str,
    title: str,
    domain: str,
    why_it_matters: str = "",
    recommended_fix: str = "",
    severity: str = "",
) -> PromptSpec:
    """Build a PromptSpec for any registered check.

    `recommended_fix` comes from the Issue produced at audit time and is the most
    specific input available, so it leads the body when present.
    """
    fam = family_for(domain)
    problem = title if not why_it_matters else f"{title}. {why_it_matters}."
    if severity:
        problem = f"[{severity}] {problem}"
    body = fam.guidance
    if recommended_fix:
        body = f"**Recommended fix for this finding:** {recommended_fix}\n\n{fam.guidance}"
    return PromptSpec(
        check_id=check_id,
        title=f"Fix: {title}",
        problem=problem,
        artefact=fam.artefact,
        body=body,
        acceptance=fam.acceptance,
        verify=fam.verify or _PAGE_VERIFY,
        constraints=fam.constraints,
    )


def spec_from_registry(check_id: str, **overrides: Any) -> Optional[PromptSpec]:
    """Look the check up in the live registry and derive its spec."""
    from sentinelseo.checks import load_all_checks
    from sentinelseo.checks.registry import get_all_checks

    load_all_checks()
    entry = get_all_checks().get(check_id)
    if entry is None:
        return None
    cs = entry[0]
    return spec_for_check(
        check_id=cs.check_id,
        title=overrides.get("title") or cs.title,
        domain=cs.domain,
        why_it_matters=overrides.get("why_it_matters") or cs.why_it_matters or "",
        recommended_fix=overrides.get("recommended_fix") or "",
        severity=overrides.get("severity") or cs.default_severity or "",
    )
