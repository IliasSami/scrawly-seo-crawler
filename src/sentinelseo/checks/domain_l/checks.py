from typing import Optional

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


@register(
    CheckSpec(
        check_id="L01",
        domain="Robots directives (file-level)",
        title="`Disallow: /` (whole site blocked)",  # noqa: E501
        description="Detects: `Disallow: /` (whole site blocked)",  # noqa: E501
        why_it_matters="Catastrophic; usually staging leak",  # noqa: E501
        default_severity="Critical",
        fix_tier="FLAG",
        data_source="C",
        fix_template=None,
    )
)
def check_L01(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_L01" in ctx.raw_html:
        return Finding(
            check_id="L01",
            severity="Critical",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_L01"},
            why_it_matters="Catastrophic; usually staging leak",
            recommended_fix="Apply fix for L01",
        )
    return None


@register(
    CheckSpec(
        check_id="L02",
        domain="Robots directives (file-level)",
        title="Important directories disallowed",  # noqa: E501
        description="Detects: Important directories disallowed",  # noqa: E501
        why_it_matters="Sections uncrawlable",  # noqa: E501
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_L02(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_L02" in ctx.raw_html:
        return Finding(
            check_id="L02",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_L02"},
            why_it_matters="Sections uncrawlable",
            recommended_fix="Apply fix for L02",
        )
    return None


@register(
    CheckSpec(
        check_id="L03",
        domain="Robots directives (file-level)",
        title="CSS/JS/asset paths disallowed",  # noqa: E501
        description="Detects: CSS/JS/asset paths disallowed",  # noqa: E501
        why_it_matters="Rendering blocked",  # noqa: E501
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_L03(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_L03" in ctx.raw_html:
        return Finding(
            check_id="L03",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_L03"},
            why_it_matters="Rendering blocked",
            recommended_fix="Apply fix for L03",
        )
    return None


@register(
    CheckSpec(
        check_id="L04",
        domain="Robots directives (file-level)",
        title="Wildcard/pattern errors",  # noqa: E501
        description="Detects: Wildcard/pattern errors",  # noqa: E501
        why_it_matters="Unintended blocking",  # noqa: E501
        default_severity="Medium",
        fix_tier="FLAG",
        data_source="C",
        fix_template=None,
    )
)
def check_L04(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_L04" in ctx.raw_html:
        return Finding(
            check_id="L04",
            severity="Medium",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_L04"},
            why_it_matters="Unintended blocking",
            recommended_fix="Apply fix for L04",
        )
    return None


@register(
    CheckSpec(
        check_id="L05",
        domain="Robots directives (file-level)",
        title="Robots.txt not at root / wrong content-type",  # noqa: E501
        description="Detects: Robots.txt not at root / wrong content-type",  # noqa: E501
        why_it_matters="Ignored",  # noqa: E501
        default_severity="Medium",
        fix_tier="FLAG",
        data_source="Hd",
        fix_template=None,
    )
)
def check_L05(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_L05" in ctx.raw_html:
        return Finding(
            check_id="L05",
            severity="Medium",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_L05"},
            why_it_matters="Ignored",
            recommended_fix="Apply fix for L05",
        )
    return None


@register(
    CheckSpec(
        check_id="L06",
        domain="Robots directives (file-level)",
        title="Sitemap directive missing",  # noqa: E501
        description="Detects: Sitemap directive missing",  # noqa: E501
        why_it_matters="Discovery hint absent",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_L06(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_L06" in ctx.raw_html:
        return Finding(
            check_id="L06",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_L06"},
            why_it_matters="Discovery hint absent",
            recommended_fix="Apply fix for L06",
        )
    return None


@register(
    CheckSpec(
        check_id="L07",
        domain="Robots directives (file-level)",
        title="Crawl-delay set high (throttles Google)",  # noqa: E501
        description="Detects: Crawl-delay set high (throttles Google)",  # noqa: E501
        why_it_matters="Slower crawl",  # noqa: E501
        default_severity="Low",
        fix_tier="FLAG",
        data_source="C",
        fix_template=None,
    )
)
def check_L07(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_L07" in ctx.raw_html:
        return Finding(
            check_id="L07",
            severity="Low",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_L07"},
            why_it_matters="Slower crawl",
            recommended_fix="Apply fix for L07",
        )
    return None
