import re
from typing import Optional

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register

_PARAM_JUNK = re.compile(r'[?&](utm_|sessionid|sid|replytocom|orderby|filter|fbclid|gclid|sort)', re.I)  # noqa: E501

@register(
    CheckSpec(
        check_id="A01",
        domain="Crawlability & Indexability",
        title="Blocked by robots.txt",
        description="Detects: Blocked by robots.txt",
        why_it_matters="Important URL disallowed; content never crawled/indexed",
        default_severity="Critical",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_A01(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="A02",
        domain="Crawlability & Indexability",
        title="Robots.txt disallows CSS/JS",
        description="Detects: Robots.txt disallows CSS/JS",
        why_it_matters="Blocks rendering resources → Google can't render page",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_A02(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="A03",
        domain="Crawlability & Indexability",
        title="Robots.txt missing / returns 5xx",
        description="Detects: Robots.txt missing / returns 5xx",
        why_it_matters="Crawlers may treat whole site as disallowed on 5xx",
        default_severity="Critical",
        fix_tier="FLAG",
        data_source="Hd",
        fix_template=None,
    )
)
def check_A03(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="A04",
        domain="Crawlability & Indexability",
        title="Meta robots `noindex` on key page",
        description="Detects: Meta robots `noindex` on key page",
        why_it_matters="Page dropped from index",
        default_severity="Critical",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_A04(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and ctx.url_row.meta_robots and ctx.url_row.status == 200:
        meta_robots = ctx.url_row.meta_robots.lower()
        if "noindex" in meta_robots:
            return Finding(
                check_id="A04",
                severity="Critical",
                tier="REVIEW",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"meta_robots": [r.strip() for r in meta_robots.split(",") if r.strip()]},  # noqa: E501
                why_it_matters="Page dropped from index",
                recommended_fix="Remove noindex if this page should rank."
            )
    return None


@register(
    CheckSpec(
        check_id="A05",
        domain="Crawlability & Indexability",
        title="X-Robots-Tag `noindex` (header)",
        description="Detects: X-Robots-Tag `noindex` (header)",
        why_it_matters="Header-level noindex, easy to miss",
        default_severity="Critical",
        fix_tier="REVIEW",
        data_source="Hd",
        fix_template=None,
    )
)
def check_A05(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and ctx.url_row.x_robots and ctx.url_row.status == 200:
        x_robots = ctx.url_row.x_robots.lower()
        if "noindex" in x_robots:
            return Finding(
                check_id="A05",
                severity="Critical",
                tier="REVIEW",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"x_robots": [r.strip() for r in x_robots.split(",") if r.strip()]},  # noqa: E501
                why_it_matters="Header-level noindex, easy to miss",
                recommended_fix="Remove noindex from the X-Robots-Tag response header."
            )
    return None


@register(
    CheckSpec(
        check_id="A06",
        domain="Crawlability & Indexability",
        title="`noindex` + `follow` vs `noindex,nofollow` mismatch",
        description="Detects: `noindex` + `follow` vs `noindex,nofollow` mismatch",
        why_it_matters="Link equity handling differs; misconfig",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_A06(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and ctx.url_row.meta_robots:
        mr = [r.strip() for r in ctx.url_row.meta_robots.lower().split(",") if r.strip()]  # noqa: E501
        if "noindex" in mr and "nofollow" in mr:
            return Finding(
                check_id="A06",
                severity="Medium",
                tier="REVIEW",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"meta_robots": mr},
                why_it_matters="Link equity handling differs; misconfig",
                recommended_fix="Confirm you intend to block link-following too; 'noindex,follow' is usually safer."  # noqa: E501
            )
    return None


@register(
    CheckSpec(
        check_id="A07",
        domain="Crawlability & Indexability",
        title="Conflicting index signals (meta vs header vs canonical)",
        description="Detects: Conflicting index signals (meta vs header vs canonical)",
        why_it_matters="Ambiguous directives; unpredictable indexing",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C+Hd",
        fix_template=None,
    )
)
def check_A07(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.url_row:
        return None
    mr_raw = (ctx.url_row.meta_robots or "").strip()
    xr_raw = (ctx.url_row.x_robots or "").strip()
    # A genuine conflict needs BOTH a meta-robots AND an X-Robots-Tag present and
    # disagreeing on noindex. An *absent* header is not a conflicting signal —
    # that false-positived on every page of a site with meta-only robots.
    if not mr_raw or not xr_raw:
        return None
    meta_noindex = "noindex" in mr_raw.lower()
    hdr_noindex = "noindex" in xr_raw.lower()
    if meta_noindex != hdr_noindex:
        return Finding(
            check_id="A07",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"meta_robots": mr_raw, "x_robots": xr_raw},
            why_it_matters="Meta robots and X-Robots-Tag disagree; unpredictable indexing.",
            recommended_fix="Make the meta robots and X-Robots-Tag header agree for this URL.",
        )
    return None


@register(
    CheckSpec(
        check_id="A08",
        domain="Crawlability & Indexability",
        title="`noindex` present in response but removed by JS (or vice-versa)",
        description=(
            "Detects: `noindex` present in response but removed by JS (or vice-versa)"
        ),
        why_it_matters="Render-dependent indexing risk",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_A08(ctx: CrawlContext) -> Optional[Finding]:
    render_diff = {d.element: d.state for d in ctx.render_diffs} if getattr(ctx, "render_diffs", None) else {}  # noqa: E501
    if render_diff.get("meta_robots") in ("created", "modified", "deleted", "added"):
        state = render_diff.get("meta_robots")
        return Finding(
            check_id="A08",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"render_diff": state},
            why_it_matters="Render-dependent indexing risk",
            recommended_fix="Emit the final robots directive in the server HTML."
        )
    return None


@register(
    CheckSpec(
        check_id="A09",
        domain="Crawlability & Indexability",
        title="Orphan URL (in sitemap/GSC but no internal inlinks)",
        description="Detects: Orphan URL (in sitemap/GSC but no internal inlinks)",
        why_it_matters="Not discoverable via crawl; wasted page",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C+X",
        fix_template=None,
    )
)
def check_A09(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and ctx.url_row.status == 200 and getattr(ctx.url_row, "indexable", False) and getattr(ctx.url_row, "inlink_count", -1) == 0:  # noqa: E501
        in_sitemap = getattr(ctx.url_row, "in_sitemap", True)
        if in_sitemap:
            return Finding(
                check_id="A09",
                severity="Medium",
                tier="REVIEW",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"inlinks": 0, "in_sitemap": in_sitemap},
                why_it_matters="Not discoverable via crawl; wasted page",
                recommended_fix="Add internal links from relevant pages."
            )
    return None


@register(
    CheckSpec(
        check_id="A10",
        domain="Crawlability & Indexability",
        title="Excessive crawl depth (>4 clicks from home)",
        description="Detects: Excessive crawl depth (>4 clicks from home)",
        why_it_matters="Deep pages crawled/indexed less",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_A10(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and getattr(ctx.url_row, "indexable", False):
        depth = getattr(ctx.url_row, "depth", getattr(ctx.url_row, "crawl_depth", None))
        if depth is not None and depth > 4:
            return Finding(
                check_id="A10",
                severity="Medium",
                tier="REVIEW",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"depth": depth},
                why_it_matters="Deep pages crawled/indexed less",
                recommended_fix="Flatten the path / add contextual internal links."
            )
    return None


@register(
    CheckSpec(
        check_id="A11",
        domain="Crawlability & Indexability",
        title="Crawl-budget waste: many low-value indexable URLs (params, faceted)",
        description=(
            "Detects: Crawl-budget waste: many low-value indexable URLs "
            "(params, faceted)"
        ),
        why_it_matters="Dilutes crawl of important pages",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_A11(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and getattr(ctx.url_row, "indexable", False) and _PARAM_JUNK.search(ctx.url):  # noqa: E501
        return Finding(
            check_id="A11",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"url": ctx.url},
            why_it_matters="Dilutes crawl of important pages",
            recommended_fix="Canonicalize to the clean URL or block the parameter pattern."  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="A12",
        domain="Crawlability & Indexability",
        title="Non-indexable page receiving internal links",
        description="Detects: Non-indexable page receiving internal links",
        why_it_matters="Link equity leaking to dead ends",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_A12(ctx: CrawlContext) -> Optional[Finding]:
    if (
        ctx.url_row
        and ctx.url_row.status == 200
        and not getattr(ctx.url_row, "indexable", True)
        and getattr(ctx.url_row, "inlink_count", 0) > 0
    ):
        return Finding(
            check_id="A12",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"inlinks": ctx.url_row.inlink_count,
                      "reason": ctx.url_row.indexability_reason},
            why_it_matters="Link equity leaking to dead ends",
            recommended_fix="Remove internal links to non-indexable pages, or make the page indexable.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="A13",
        domain="Crawlability & Indexability",
        title="Nofollowed internal links to important pages",
        description="Detects: Nofollowed internal links to important pages",
        why_it_matters="Blocks equity/discovery internally",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_A13(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.raw_html:
        nofollow_links = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']nofollow["\'][^>]*>', ctx.raw_html, re.IGNORECASE)  # noqa: E501
        nofollow_links_2 = re.findall(r'<a\s+[^>]*rel=["\']nofollow["\'][^>]*href=["\']([^"\']+)["\'][^>]*>', ctx.raw_html, re.IGNORECASE)  # noqa: E501
        nofollowed = nofollow_links + nofollow_links_2
        if nofollowed:
            return Finding(
                check_id="A13",
                severity="Medium",
                tier="REVIEW",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"targets": nofollowed[:20]},
                why_it_matters="Blocks equity/discovery internally",
                recommended_fix="Remove nofollow from internal links you want crawled."
            )
    return None


@register(
    CheckSpec(
        check_id="A14",
        domain="Crawlability & Indexability",
        title="Meta robots `nosnippet`/`noarchive`/`max-snippet` unexpected",
        description=(
            "Detects: Meta robots `nosnippet`/`noarchive`/`max-snippet` unexpected"
        ),
        why_it_matters="Suppresses SERP display features",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_A14(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and getattr(ctx.url_row, "meta_robots", None) and getattr(ctx.url_row, "indexable", False):  # noqa: E501
        mr = [r.strip() for r in ctx.url_row.meta_robots.lower().split(",")]
        flags = [t for t in mr if t.startswith(('nosnippet', 'noarchive', 'max-snippet', 'max-image-preview'))]  # noqa: E501
        if flags:
            return Finding(
                check_id="A14",
                severity="Low",
                tier="REVIEW",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"directives": flags},
                why_it_matters="Suppresses SERP display features",
                recommended_fix="Confirm you intend to suppress snippet/preview features."  # noqa: E501
            )
    return None


@register(
    CheckSpec(
        check_id="A15",
        domain="Crawlability & Indexability",
        title="Disallowed URL still internally linked",
        description="Detects: Disallowed URL still internally linked",
        why_it_matters="Confusing signals; wasted links",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_A15(ctx: CrawlContext) -> Optional[Finding]:
    return None
