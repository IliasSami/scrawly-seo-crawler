import re
from typing import Optional
from urllib.parse import urlparse

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


@register(
    CheckSpec(
        check_id="B01",
        domain="Response codes & redirects",
        title="4xx client errors (esp. 404)",
        description="Detects: 4xx client errors (esp. 404)",
        why_it_matters="Broken pages; wasted crawl; bad UX",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="Hd",
    )
)
def check_B01(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and 400 <= ctx.url_row.status < 500:
        sev = "High" if ctx.url_row.inlink_count else "Medium"
        return Finding(
            check_id="B01",
            severity=sev,
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={
                "status": ctx.url_row.status,
                "inlinks": ctx.url_row.inlink_count,
            },  # noqa: E501
            why_it_matters="Broken pages; wasted crawl; bad UX",
            recommended_fix="Fix or 301-redirect; update internal links.",
        )
    return None


@register(
    CheckSpec(
        check_id="B02",
        domain="Response codes & redirects",
        title="5xx server errors",
        description="Detects: 5xx server errors",
        why_it_matters="Server failing; severe if on key/many pages",
        default_severity="Critical",
        fix_tier="FLAG",
        data_source="Hd",
    )
)
def check_B02(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and ctx.url_row.status >= 500:
        return Finding(
            check_id="B02",
            severity="Critical",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"status": ctx.url_row.status},
            why_it_matters="Server failing; severe if on key/many pages",
            recommended_fix="Investigate server logs; restore 200.",
        )
    return None


_SOFT404_PHRASES = re.compile(
    r"\b(page not found|not found|no results|nothing found|404 error|"
    r"page (does\s?n.t|cannot be) found|sorry.{0,20}(couldn.t|can.t) find|"
    r"no longer (exists|available)|this page (has been|was) removed)\b",
    re.I,
)


@register(
    CheckSpec(
        check_id="B03",
        domain="Response codes & redirects",
        title='Soft 404 (200 status, "not found" content)',
        description='Detects: Soft 404 (200 status, "not found" content)',
        why_it_matters="Thin/empty page indexed as valid",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
    )
)
def check_B03(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.url_row or ctx.url_row.status != 200:
        return None

    title = ctx.title or ""
    main_text = ctx.raw_html or ""

    phrase = bool(_SOFT404_PHRASES.search(title)) or bool(
        _SOFT404_PHRASES.search(main_text[:2000])
    )
    thin = ctx.url_row.word_count < 100

    if phrase and (thin or _SOFT404_PHRASES.search(title)):
        return Finding(
            check_id="B03",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"word_count": ctx.url_row.word_count, "title": title},
            why_it_matters="Thin/empty page indexed as valid",
            recommended_fix="Return a real 404/410, or restore/replace the content.",
        )
    return None


@register(
    CheckSpec(
        check_id="B04",
        domain="Response codes & redirects",
        title="Broken internal links (→4xx/5xx)",
        description="Detects: Broken internal links (→4xx/5xx)",
        why_it_matters="Equity loss + UX; list inlink sources",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
    )
)
def check_B04(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="B05",
        domain="Response codes & redirects",
        title="Broken external (outbound) links",
        description="Detects: Broken external (outbound) links",
        why_it_matters="UX + trust signal degradation",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
    )
)
def check_B05(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="B06",
        domain="Response codes & redirects",
        title="Redirect chains (A→B→C…)",
        description="Detects: Redirect chains (A→B→C…)",
        why_it_matters="Wastes crawl, dilutes equity, slows load",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
    )
)
def check_B06(ctx: CrawlContext) -> Optional[Finding]:
    if (
        ctx.url_row
        and ctx.url_row.redirect_chain
        and len(ctx.url_row.redirect_chain) >= 2
    ):
        hops = list(ctx.url_row.redirect_chain) + [ctx.url]
        return Finding(
            check_id="B06",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"chain": hops},
            why_it_matters="Wastes crawl, dilutes equity, slows load",
            recommended_fix=(
                "Point the first URL directly at the "
                "final destination (single 301)."
            ),  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="B07",
        domain="Response codes & redirects",
        title="Redirect loops",
        description="Detects: Redirect loops",
        why_it_matters="Page unreachable",
        default_severity="Critical",
        fix_tier="FLAG",
        data_source="C",
    )
)
def check_B07(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and ctx.url_row.redirect_chain:
        seen = ctx.url_row.redirect_chain
        if len(seen) != len(set(seen)):
            return Finding(
                check_id="B07",
                severity="Critical",
                tier="FLAG",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"chain": seen},
                why_it_matters="Page unreachable",
                recommended_fix="Break the loop; map to a single final 200 URL.",
            )
    return None


@register(
    CheckSpec(
        check_id="B08",
        domain="Response codes & redirects",
        title="Temporary redirect (302/307) that should be 301/308",
        description="Detects: Temporary redirect (302/307) that should be 301/308",
        why_it_matters="Equity may not fully pass",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="Hd",
    )
)
def check_B08(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and ctx.url_row.status in (302, 307):
        return Finding(
            check_id="B08",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"status": ctx.url_row.status},
            why_it_matters="Equity may not fully pass",
            recommended_fix="Use 301/308 for permanent moves to pass equity.",
        )
    return None


@register(
    CheckSpec(
        check_id="B09",
        domain="Response codes & redirects",
        title="Internal links pointing to redirects",
        description="Detects: Internal links pointing to redirects",
        why_it_matters="Should link final URL directly",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
    )
)
def check_B09(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="B10",
        domain="Response codes & redirects",
        title="Canonical → redirected URL",
        description="Detects: Canonical → redirected URL",
        why_it_matters="Canonical target itself redirects",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
    )
)
def check_B10(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="B11",
        domain="Response codes & redirects",
        title="Redirect to 4xx/5xx (broken redirect target)",
        description="Detects: Redirect to 4xx/5xx (broken redirect target)",
        why_it_matters="Dead redirect",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
    )
)
def check_B11(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and ctx.url_row.redirect_chain and ctx.url_row.status >= 400:
        return Finding(
            check_id="B11",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={
                "final_status": ctx.url_row.status,
                "chain": ctx.url_row.redirect_chain,
            },  # noqa: E501
            why_it_matters="Dead redirect",
            recommended_fix="Redirect to a working 200 URL.",
        )
    return None


_METAREFRESH = re.compile(r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]+url=', re.I)


@register(
    CheckSpec(
        check_id="B12",
        domain="Response codes & redirects",
        title="Meta-refresh / JS redirect",
        description="Detects: Meta-refresh / JS redirect",
        why_it_matters="Non-standard redirect; weaker signal",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="R",
    )
)
def check_B12(ctx: CrawlContext) -> Optional[Finding]:
    render_diff = {d.element: d.state for d in ctx.render_diffs}
    if _METAREFRESH.search(ctx.raw_html or "") or render_diff.get("_js_redirect"):
        return Finding(
            check_id="B12",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={},
            why_it_matters="Non-standard redirect; weaker signal",
            recommended_fix="Replace with a server-side 301.",
        )
    return None


@register(
    CheckSpec(
        check_id="B13",
        domain="Response codes & redirects",
        title="HTTP → HTTPS redirect missing",
        description="Detects: HTTP → HTTPS redirect missing",
        why_it_matters="Insecure access path",
        default_severity="High",
        fix_tier="FLAG",
        data_source="Hd",
    )
)
def check_B13(ctx: CrawlContext) -> Optional[Finding]:
    if urlparse(ctx.url).scheme == "http" and ctx.url_row and ctx.url_row.status == 200:
        return Finding(
            check_id="B13",
            severity="High",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"url": ctx.url},
            why_it_matters="Insecure access path",
            recommended_fix="301-redirect all HTTP to HTTPS.",
        )
    return None


@register(
    CheckSpec(
        check_id="B14",
        domain="Response codes & redirects",
        title="Mixed redirect status across templates (migration check)",
        description="Detects: Mixed redirect status across templates (migration check)",
        why_it_matters="Inconsistent migration mapping",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
    )
)
def check_B14(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and ctx.url_row.indexability_reason == "mixed_redirect":
        return Finding(
            check_id="B14",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"reason": ctx.url_row.indexability_reason},
            why_it_matters="Inconsistent migration mapping",
            recommended_fix="Ensure redirects consistently use the same status code.",
        )
    return None
