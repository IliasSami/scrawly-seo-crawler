import re
from typing import Any, Optional
from urllib.parse import urlparse

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


def _basic_finding(
    ctx: CrawlContext,
    check_id: str,
    severity: str,
    tier: str,
    why: str,
    rec: str,
    evidence: dict[str, Any],
) -> Finding:
    return Finding(
        check_id=check_id,
        severity=severity,
        tier=tier,
        affected_urls=[ctx.url],
        wp_object_map={},
        evidence=evidence,
        why_it_matters=why,
        recommended_fix=rec,
    )


@register(
    CheckSpec(
        check_id="V01",
        domain="WordPress-specific",
        title="Default 'Uncategorized' category indexed",
        description="Detects: Default 'Uncategorized' category indexed",
        why_it_matters="Thin taxonomy page",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_V01(ctx: CrawlContext) -> Optional[Finding]:
    if "/category/uncategorized" in ctx.url.lower():
        return _basic_finding(
            ctx,
            "V01",
            "Low",
            "REVIEW",
            "Thin taxonomy page",
            "Rename or remove Uncategorized.",
            {},
        )
    return None


@register(
    CheckSpec(
        check_id="V02",
        domain="WordPress-specific",
        title="Tag/author/date archives indexed & thin/duplicate",
        description="Detects: Tag/author/date archives indexed & thin/duplicate",
        why_it_matters="Index bloat",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_V02(ctx: CrawlContext) -> Optional[Finding]:
    parsed = urlparse(ctx.url)
    if (
        "/tag/" in parsed.path
        or "/author/" in parsed.path
        or re.search(r"/\d{4}/\d{2}/", parsed.path)
    ):
        return _basic_finding(
            ctx,
            "V02",
            "Medium",
            "REVIEW",
            "Index bloat",
            "Noindex archives if not needed.",
            {"path": parsed.path},
        )
    return None


@register(
    CheckSpec(
        check_id="V03",
        domain="WordPress-specific",
        title="Attachment (media) pages indexed",
        description="Detects: Attachment (media) pages indexed",
        why_it_matters="Thin auto-generated pages",
        default_severity="Medium",
        fix_tier="AUTO",
        data_source="C",
        fix_template=None,
    )
)
def check_V03(ctx: CrawlContext) -> Optional[Finding]:
    parsed = urlparse(ctx.url)
    if "attachment_id=" in parsed.query:
        return _basic_finding(
            ctx,
            "V03",
            "Medium",
            "AUTO",
            "Thin auto-generated pages",
            "Redirect attachments to parent.",
            {},
        )
    return None


@register(
    CheckSpec(
        check_id="V04",
        domain="WordPress-specific",
        title="Paginated comment URLs (`/comment-page-`) indexed",
        description="Detects: Paginated comment URLs (`/comment-page-`) indexed",
        why_it_matters="Duplication",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_V04(ctx: CrawlContext) -> Optional[Finding]:
    if "/comment-page-" in ctx.url:
        return _basic_finding(
            ctx,
            "V04",
            "Low",
            "REVIEW",
            "Duplication",
            "Disable comment pagination.",
            {},
        )
    return None


@register(
    CheckSpec(
        check_id="V05",
        domain="WordPress-specific",
        title="Search results pages (`?s=`) indexable",
        description="Detects: Search results pages (`?s=`) indexable",
        why_it_matters="Infinite thin pages",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_V05(ctx: CrawlContext) -> Optional[Finding]:
    if "s=" in urlparse(ctx.url).query:
        return _basic_finding(
            ctx,
            "V05",
            "Medium",
            "REVIEW",
            "Infinite thin pages",
            "Noindex search results.",
            {},
        )
    return None


@register(
    CheckSpec(
        check_id="V06",
        domain="WordPress-specific",
        title="Both SEO plugins active (Yoast + RankMath)",
        description="Detects: Both SEO plugins active (Yoast + RankMath)",
        why_it_matters="Conflicting meta/schema output",
        default_severity="High",
        fix_tier="FLAG",
        data_source="C",
        fix_template=None,
    )
)
def check_V06(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None
    yoast = "Yoast SEO" in ctx.raw_html
    rankmath = "Rank Math" in ctx.raw_html
    if yoast and rankmath:
        return _basic_finding(
            ctx,
            "V06",
            "High",
            "FLAG",
            "Conflicting meta/schema output",
            "Deactivate one SEO plugin.",
            {},
        )
    return None


@register(
    CheckSpec(
        check_id="V07",
        domain="WordPress-specific",
        title="Missing/duplicate canonical from theme + plugin both emitting",
        description="Detects: Missing/duplicate canonical from theme + plugin both emitting",  # noqa: E501
        why_it_matters="Double canonical",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_V07(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None
    canonicals = len(
        re.findall(r'<link[^>]*rel=["\']?canonical["\']?', ctx.raw_html, re.I)
    )
    if canonicals > 1:
        return _basic_finding(
            ctx,
            "V07",
            "Medium",
            "REVIEW",
            "Double canonical",
            "Fix theme to not output canonical.",
            {"canonicals": canonicals},
        )
    return None


@register(
    CheckSpec(
        check_id="V08",
        domain="WordPress-specific",
        title="Auto-generated image sizes bloating media / no WebP",
        description="Detects: Auto-generated image sizes bloating media / no WebP",
        why_it_matters="Speed",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_V08(ctx: CrawlContext) -> Optional[Finding]:
    imgs = (getattr(ctx.url_row, "images", None) or ctx.images or [])
    legacy = [
        i for i in imgs
        if (getattr(i, "src", "") or "").lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    if len(legacy) >= 3:
        return Finding(
            check_id="V08",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"legacy_format_images": len(legacy)},
            why_it_matters="Speed",
            recommended_fix="Serve images as WebP/AVIF (e.g. a WP image-optimization plugin).",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="V09",
        domain="WordPress-specific",
        title="`?replytocom` / feed / trackback URLs crawlable",
        description="Detects: `?replytocom` / feed / trackback URLs crawlable",
        why_it_matters="Crawl waste",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_V09(ctx: CrawlContext) -> Optional[Finding]:
    parsed = urlparse(ctx.url)
    if (
        "replytocom=" in parsed.query
        or parsed.path.endswith("/feed/")
        or parsed.path.endswith("/trackback/")
    ):
        return _basic_finding(
            ctx, "V09", "Low", "REVIEW", "Crawl waste", "Disallow in robots.txt.", {}
        )
    return None


@register(
    CheckSpec(
        check_id="V10",
        domain="WordPress-specific",
        title="Staging/dev site indexable (noindex leaked to prod, or dev public)",
        description="Detects: Staging/dev site indexable (noindex leaked to prod, or dev public)",  # noqa: E501
        why_it_matters="Duplicate-site / leak disaster",
        default_severity="Critical",
        fix_tier="FLAG",
        data_source="C",
        fix_template=None,
    )
)
def check_V10(ctx: CrawlContext) -> Optional[Finding]:
    parsed = urlparse(ctx.url)
    if ("staging." in parsed.netloc or "dev." in parsed.netloc) and ctx.raw_html:
        if "noindex" not in ctx.raw_html.lower():
            return _basic_finding(
                ctx,
                "V10",
                "Critical",
                "FLAG",
                "Duplicate-site / leak disaster",
                "Noindex staging sites.",
                {},
            )
    return None


@register(
    CheckSpec(
        check_id="V11",
        domain="WordPress-specific",
        title="Heavy plugin count inflating render/requests",
        description="Detects: Heavy plugin count inflating render/requests",
        why_it_matters="Speed",
        default_severity="Medium",
        fix_tier="FLAG",
        data_source="R",
        fix_template=None,
    )
)
def check_V11(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None
    plugins = len(set(re.findall(r"wp-content/plugins/([^/]+)/", ctx.raw_html)))
    if plugins > 20:
        return _basic_finding(
            ctx,
            "V11",
            "Medium",
            "FLAG",
            "Speed",
            "Audit plugins.",
            {"plugin_count": plugins},
        )
    return None


@register(
    CheckSpec(
        check_id="V12",
        domain="WordPress-specific",
        title="REST API / feeds exposing more than intended",
        description="Detects: REST API / feeds exposing more than intended",
        why_it_matters="Hardening",
        default_severity="Low",
        fix_tier="FLAG",
        data_source="Hd",
        fix_template=None,
    )
)
def check_V12(ctx: CrawlContext) -> Optional[Finding]:
    if "/wp-json/wp/v2/users" in ctx.url:
        return _basic_finding(
            ctx,
            "V12",
            "Low",
            "FLAG",
            "Hardening",
            "Restrict REST API user endpoint.",
            {},
        )
    return None
