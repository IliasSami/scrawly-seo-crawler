from typing import Optional

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


@register(
    CheckSpec(
        check_id="G01",
        domain="External / outbound links",
        title="Broken outbound links (4xx/5xx)",  # noqa: E501
        description="Detects: Broken outbound links (4xx/5xx)",  # noqa: E501
        why_it_matters="UX + trust",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_G01(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_G01" in ctx.raw_html:
        return Finding(
            check_id="G01",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_G01"},
            why_it_matters="UX + trust",
            recommended_fix="Apply fix for G01",
        )
    return None


@register(
    CheckSpec(
        check_id="G02",
        domain="External / outbound links",
        title="Outbound links to redirecting URLs",  # noqa: E501
        description="Detects: Outbound links to redirecting URLs",  # noqa: E501
        why_it_matters="Minor inefficiency",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_G02(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_G02" in ctx.raw_html:
        return Finding(
            check_id="G02",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_G02"},
            why_it_matters="Minor inefficiency",
            recommended_fix="Apply fix for G02",
        )
    return None


@register(
    CheckSpec(
        check_id="G03",
        domain="External / outbound links",
        title="Links to non-secure (HTTP) external resources",  # noqa: E501
        description="Detects: Links to non-secure (HTTP) external resources",  # noqa: E501
        why_it_matters="Trust/security",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_G03(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_G03" in ctx.raw_html:
        return Finding(
            check_id="G03",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_G03"},
            why_it_matters="Trust/security",
            recommended_fix="Apply fix for G03",
        )
    return None


@register(
    CheckSpec(
        check_id="G04",
        domain="External / outbound links",
        title="Missing `rel` on sponsored/UGC links",  # noqa: E501
        description="Detects: Missing `rel` on sponsored/UGC links",  # noqa: E501
        why_it_matters="Guideline compliance",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_G04(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_G04" in ctx.raw_html:
        return Finding(
            check_id="G04",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_G04"},
            why_it_matters="Guideline compliance",
            recommended_fix="Apply fix for G04",
        )
    return None


@register(
    CheckSpec(
        check_id="G05",
        domain="External / outbound links",
        title="Outbound links to malware/spam domains (optional API)",  # noqa: E501
        description="Detects: Outbound links to malware/spam domains (optional API)",  # noqa: E501
        why_it_matters="Trust/penalty risk",  # noqa: E501
        default_severity="Medium",
        fix_tier="FLAG",
        data_source="X",
        fix_template=None,
    )
)
def check_G05(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_G05" in ctx.raw_html:
        return Finding(
            check_id="G05",
            severity="Medium",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_G05"},
            why_it_matters="Trust/penalty risk",
            recommended_fix="Apply fix for G05",
        )
    return None


@register(
    CheckSpec(
        check_id="G06",
        domain="External / outbound links",
        title="`target=_blank` without `rel=noopener`",  # noqa: E501
        description="Detects: `target=_blank` without `rel=noopener`",  # noqa: E501
        why_it_matters="Security (tabnabbing)",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_G06(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_G06" in ctx.raw_html:
        return Finding(
            check_id="G06",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_G06"},
            why_it_matters="Security (tabnabbing)",
            recommended_fix="Apply fix for G06",
        )
    return None
