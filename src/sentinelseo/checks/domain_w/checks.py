import re
from typing import Any, Optional

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
        check_id="W01",
        domain="Analytics, tracking & config (context, mostly info)",
        title="Missing/duplicate GA4 or GTM tags",
        description="Detects: Missing/duplicate GA4 or GTM tags",
        why_it_matters="Measurement gap",
        default_severity="Low",
        fix_tier="FLAG",
        data_source="R",
        fix_template=None,
    )
)
def check_W01(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None
    gtm_tags = len(re.findall(r"googletagmanager\.com/gtm\.js", ctx.raw_html))
    gtag_tags = len(re.findall(r"googletagmanager\.com/gtag/js", ctx.raw_html))
    if gtm_tags == 0 and gtag_tags == 0:
        return _basic_finding(
            ctx, "W01", "Low", "FLAG", "Measurement gap", "Install GA4 or GTM.", {}
        )
    if gtm_tags > 1 or gtag_tags > 1:
        return _basic_finding(
            ctx, "W01", "Low", "FLAG", "Measurement gap", "Remove duplicate tags.", {}
        )
    return None


@register(
    CheckSpec(
        check_id="W02",
        domain="Analytics, tracking & config (context, mostly info)",
        title="Missing GSC verification",
        description="Detects: Missing GSC verification",
        why_it_matters="No Search Console data",
        default_severity="Low",
        fix_tier="FLAG",
        data_source="C",
        fix_template=None,
    )
)
def check_W02(ctx: CrawlContext) -> Optional[Finding]:
    from urllib.parse import urlparse
    if urlparse(ctx.url).path not in ("", "/") or not ctx.raw_html:
        return None  # only meaningful on the homepage
    if ctx.dom().css_first('meta[name="google-site-verification"]') is None:
        return Finding(
            check_id="W02",
            severity="Low",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"google_site_verification": "missing"},
            why_it_matters="No Search Console data",
            recommended_fix="Verify the site in Search Console (meta tag or DNS).",
        )
    return None


@register(
    CheckSpec(
        check_id="W03",
        domain="Analytics, tracking & config (context, mostly info)",
        title="Favicon missing / broken",
        description="Detects: Favicon missing / broken",
        why_it_matters="Branding + SERP display",
        default_severity="Low",
        fix_tier="AUTO",
        data_source="C",
        fix_template=None,
    )
)
def check_W03(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None
    if not re.search(
        r'<link[^>]*rel=["\']?(?:shortcut )?icon["\']?', ctx.raw_html, re.I
    ):
        return _basic_finding(
            ctx, "W03", "Low", "AUTO", "Branding + SERP display", "Add a favicon.", {}
        )
    return None


@register(
    CheckSpec(
        check_id="W04",
        domain="Analytics, tracking & config (context, mostly info)",
        title="Missing 404 template / unhelpful 404",
        description="Detects: Missing 404 template / unhelpful 404",
        why_it_matters="UX + recovery",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_W04(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="W05",
        domain="Analytics, tracking & config (context, mostly info)",
        title="Multiple homepage versions resolve 200 (/, /index.php, /home)",
        description="Detects: Multiple homepage versions resolve 200 (/, /index.php, /home)",  # noqa: E501
        why_it_matters="Duplication",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_W05(ctx: CrawlContext) -> Optional[Finding]:
    return None
