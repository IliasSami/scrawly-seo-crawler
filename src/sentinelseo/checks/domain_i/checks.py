from typing import Optional

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


@register(
    CheckSpec(
        check_id="I01",
        domain="Hreflang / international",
        title="Missing return (reciprocal) hreflang",  # noqa: E501
        description="Detects: Missing return (reciprocal) hreflang",  # noqa: E501
        why_it_matters="Cluster invalid",  # noqa: E501
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_I01(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_I01" in ctx.raw_html:
        return Finding(
            check_id="I01",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_I01"},
            why_it_matters="Cluster invalid",
            recommended_fix="Apply fix for I01",
        )
    return None


@register(
    CheckSpec(
        check_id="I02",
        domain="Hreflang / international",
        title="hreflang to non-canonical / non-200 URL",  # noqa: E501
        description="Detects: hreflang to non-canonical / non-200 URL",  # noqa: E501
        why_it_matters="Broken alternate",  # noqa: E501
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_I02(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_I02" in ctx.raw_html:
        return Finding(
            check_id="I02",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_I02"},
            why_it_matters="Broken alternate",
            recommended_fix="Apply fix for I02",
        )
    return None


@register(
    CheckSpec(
        check_id="I03",
        domain="Hreflang / international",
        title="Invalid language/region codes",  # noqa: E501
        description="Detects: Invalid language/region codes",  # noqa: E501
        why_it_matters="Ignored by Google",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_I03(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_I03" in ctx.raw_html:
        return Finding(
            check_id="I03",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_I03"},
            why_it_matters="Ignored by Google",
            recommended_fix="Apply fix for I03",
        )
    return None


@register(
    CheckSpec(
        check_id="I04",
        domain="Hreflang / international",
        title="Missing `x-default`",  # noqa: E501
        description="Detects: Missing `x-default`",  # noqa: E501
        why_it_matters="No fallback for unmatched locales",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_I04(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_I04" in ctx.raw_html:
        return Finding(
            check_id="I04",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_I04"},
            why_it_matters="No fallback for unmatched locales",
            recommended_fix="Apply fix for I04",
        )
    return None


@register(
    CheckSpec(
        check_id="I05",
        domain="Hreflang / international",
        title="hreflang + canonical conflict (canonical to different lang)",  # noqa: E501
        description="Detects: hreflang + canonical conflict (canonical to different lang)",  # noqa: E501
        why_it_matters="Contradictory",  # noqa: E501
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_I05(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_I05" in ctx.raw_html:
        return Finding(
            check_id="I05",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_I05"},
            why_it_matters="Contradictory",
            recommended_fix="Apply fix for I05",
        )
    return None


@register(
    CheckSpec(
        check_id="I06",
        domain="Hreflang / international",
        title="Multiple/duplicate hreflang entries for same locale",  # noqa: E501
        description="Detects: Multiple/duplicate hreflang entries for same locale",  # noqa: E501
        why_it_matters="Ambiguous",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_I06(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_I06" in ctx.raw_html:
        return Finding(
            check_id="I06",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_I06"},
            why_it_matters="Ambiguous",
            recommended_fix="Apply fix for I06",
        )
    return None


@register(
    CheckSpec(
        check_id="I07",
        domain="Hreflang / international",
        title="hreflang in HTML vs sitemap vs header inconsistency",  # noqa: E501
        description="Detects: hreflang in HTML vs sitemap vs header inconsistency",  # noqa: E501
        why_it_matters="Signal split",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_I07(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_I07" in ctx.raw_html:
        return Finding(
            check_id="I07",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_I07"},
            why_it_matters="Signal split",
            recommended_fix="Apply fix for I07",
        )
    return None


@register(
    CheckSpec(
        check_id="I08",
        domain="Hreflang / international",
        title="Self-referential hreflang missing",  # noqa: E501
        description="Detects: Self-referential hreflang missing",  # noqa: E501
        why_it_matters="Cluster incomplete",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_I08(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_I08" in ctx.raw_html:
        return Finding(
            check_id="I08",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_I08"},
            why_it_matters="Cluster incomplete",
            recommended_fix="Apply fix for I08",
        )
    return None
