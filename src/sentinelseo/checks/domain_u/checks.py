import re
from typing import Any, Optional
from urllib.parse import urlparse

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


def _basic_finding(
    ctx: CrawlContext,
    check_id: str,
    severity: str,
    why: str,
    rec: str,
    evidence: dict[str, Any],
) -> Finding:
    return Finding(
        check_id=check_id,
        severity=severity,
        tier="REVIEW",
        affected_urls=[ctx.url],
        wp_object_map={},
        evidence=evidence,
        why_it_matters=why,
        recommended_fix=rec,
    )


@register(
    CheckSpec(
        check_id="U01",
        domain="Pagination",
        title="Paginated pages `noindex`'d",
        description="Detects: Paginated pages `noindex`'d",
        why_it_matters="Google stops following -> products lost",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_U01(ctx: CrawlContext) -> Optional[Finding]:
    parsed = urlparse(ctx.url)
    is_paginated = (
        "page=" in parsed.query or "p=" in parsed.query or "/page/" in parsed.path
    )
    if is_paginated and ctx.raw_html and "noindex" in ctx.raw_html.lower():
        if re.search(
            r'<meta[^>]*name=["\']?robots["\']?[^>]*content=["\']?[^>]*noindex',
            ctx.raw_html,
            re.I,
        ):
            return _basic_finding(
                ctx,
                "U01",
                "Medium",
                "Google stops following",
                "Remove noindex from paginated pages.",
                {},
            )
    return None


@register(
    CheckSpec(
        check_id="U02",
        domain="Pagination",
        title="Multiple rel=next/prev on one page",
        description="Detects: Multiple rel=next/prev on one page",
        why_it_matters="Invalid pagination markup",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_U02(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None
    next_tags = len(re.findall(r'<link[^>]*rel=["\']?next["\']?', ctx.raw_html, re.I))
    prev_tags = len(re.findall(r'<link[^>]*rel=["\']?prev["\']?', ctx.raw_html, re.I))
    if next_tags > 1 or prev_tags > 1:
        return _basic_finding(
            ctx,
            "U02",
            "Low",
            "Invalid pagination markup",
            "Ensure only one next/prev tag.",
            {"next": next_tags, "prev": prev_tags},
        )
    return None


@register(
    CheckSpec(
        check_id="U03",
        domain="Pagination",
        title="Page 2+ canonicalized to page 1",
        description="Detects: Page 2+ canonicalized to page 1",
        why_it_matters="Component pages dropped",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_U03(ctx: CrawlContext) -> Optional[Finding]:
    parsed = urlparse(ctx.url)
    is_paginated = "page=" in parsed.query or "/page/" in parsed.path
    if not is_paginated or not ctx.raw_html:
        return None
    match = re.search(
        r'<link[^>]*rel=["\']?canonical["\']?[^>]*href=["\']?([^"\'>]+)["\']?',
        ctx.raw_html,
        re.I,
    )
    if match:
        canonical = match.group(1)
        if "page=" not in canonical and "/page/" not in canonical:
            return _basic_finding(
                ctx,
                "U03",
                "Medium",
                "Component pages dropped",
                "Self-canonicalize paginated pages.",
                {"canonical": canonical},
            )
    return None


@register(
    CheckSpec(
        check_id="U04",
        domain="Pagination",
        title="Infinite scroll with no paginated URLs",
        description="Detects: Infinite scroll with no paginated URLs",
        why_it_matters="Content undiscoverable",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_U04(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None
    html = (ctx.rendered_html or ctx.raw_html).lower()
    has_infinite = any(k in html for k in (
        "infinite-scroll", "infinitescroll", "load-more", "load_more", "data-infinite",
    ))
    has_next = 'rel="next"' in html or "rel='next'" in html
    if has_infinite and not has_next:
        return Finding(
            check_id="U04",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"infinite_scroll": True, "paginated_urls": False},
            why_it_matters="Content undiscoverable",
            recommended_fix="Provide crawlable paginated URLs alongside infinite scroll.",
        )
    return None


@register(
    CheckSpec(
        check_id="U05",
        domain="Pagination",
        title="Missing 'view-all' or crawl path for deep lists",
        description="Detects: Missing 'view-all' or crawl path for deep lists",
        why_it_matters="Deep items uncrawled",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_U05(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None
    html = (ctx.rendered_html or ctx.raw_html).lower()
    is_paginated = 'rel="next"' in html or "/page/" in ctx.url.lower()
    has_view_all = any(k in html for k in ("view all", "view-all", "show all", "see all"))
    if is_paginated and not has_view_all:
        return Finding(
            check_id="U05",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"paginated": True, "view_all": False},
            why_it_matters="Deep items uncrawled",
            recommended_fix="Offer a 'view all' page or a crawl path to deep list items.",
        )
    return None
