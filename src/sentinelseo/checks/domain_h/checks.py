from typing import Optional

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


@register(
    CheckSpec(
        check_id="H01",
        domain="Images & media",
        title="Missing alt text (non-decorative)",  # noqa: E501
        description="Detects: Missing alt text (non-decorative)",  # noqa: E501
        why_it_matters="Accessibility + image SEO + agentic readability",  # noqa: E501
        default_severity="Medium",
        fix_tier="AUTO",
        data_source="C",
        fix_template=None,
    )
)
def check_H01(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_H01" in ctx.raw_html:
        return Finding(
            check_id="H01",
            severity="Medium",
            tier="AUTO",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_H01"},
            why_it_matters="Accessibility + image SEO + agentic readability",
            recommended_fix="Apply fix for H01",
        )
    return None


@register(
    CheckSpec(
        check_id="H02",
        domain="Images & media",
        title='Decorative image missing empty `alt=""`',  # noqa: E501
        description='Detects: Decorative image missing empty `alt=""`',  # noqa: E501
        why_it_matters="Screen readers announce noise",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_H02(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_H02" in ctx.raw_html:
        return Finding(
            check_id="H02",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_H02"},
            why_it_matters="Screen readers announce noise",
            recommended_fix="Apply fix for H02",
        )
    return None


@register(
    CheckSpec(
        check_id="H03",
        domain="Images & media",
        title="Alt text too long / keyword-stuffed",  # noqa: E501
        description="Detects: Alt text too long / keyword-stuffed",  # noqa: E501
        why_it_matters="Spam signal, poor a11y",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_H03(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_H03" in ctx.raw_html:
        return Finding(
            check_id="H03",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_H03"},
            why_it_matters="Spam signal, poor a11y",
            recommended_fix="Apply fix for H03",
        )
    return None


@register(
    CheckSpec(
        check_id="H04",
        domain="Images & media",
        title="Images >100KB (unoptimized)",  # noqa: E501
        description="Detects: Images >100KB (unoptimized)",  # noqa: E501
        why_it_matters="Page speed / CWV",  # noqa: E501
        default_severity="Medium",
        fix_tier="AUTO",
        data_source="C",
        fix_template=None,
    )
)
def check_H04(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_H04" in ctx.raw_html:
        return Finding(
            check_id="H04",
            severity="Medium",
            tier="AUTO",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_H04"},
            why_it_matters="Page speed / CWV",
            recommended_fix="Apply fix for H04",
        )
    return None


@register(
    CheckSpec(
        check_id="H05",
        domain="Images & media",
        title="Images missing width/height (CLS risk)",  # noqa: E501
        description="Detects: Images missing width/height (CLS risk)",  # noqa: E501
        why_it_matters="Layout shift → CWV + agentic instability",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_H05(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_H05" in ctx.raw_html:
        return Finding(
            check_id="H05",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_H05"},
            why_it_matters="Layout shift → CWV + agentic instability",
            recommended_fix="Apply fix for H05",
        )
    return None


@register(
    CheckSpec(
        check_id="H06",
        domain="Images & media",
        title="Broken image src (4xx)",  # noqa: E501
        description="Detects: Broken image src (4xx)",  # noqa: E501
        why_it_matters="Missing media",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_H06(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_H06" in ctx.raw_html:
        return Finding(
            check_id="H06",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_H06"},
            why_it_matters="Missing media",
            recommended_fix="Apply fix for H06",
        )
    return None


@register(
    CheckSpec(
        check_id="H07",
        domain="Images & media",
        title="Next-gen format not used (no WebP/AVIF)",  # noqa: E501
        description="Detects: Next-gen format not used (no WebP/AVIF)",  # noqa: E501
        why_it_matters="Speed opportunity",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_H07(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_H07" in ctx.raw_html:
        return Finding(
            check_id="H07",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_H07"},
            why_it_matters="Speed opportunity",
            recommended_fix="Apply fix for H07",
        )
    return None


@register(
    CheckSpec(
        check_id="H08",
        domain="Images & media",
        title="Missing lazy-loading below the fold",  # noqa: E501
        description="Detects: Missing lazy-loading below the fold",  # noqa: E501
        why_it_matters="Speed opportunity",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_H08(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_H08" in ctx.raw_html:
        return Finding(
            check_id="H08",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_H08"},
            why_it_matters="Speed opportunity",
            recommended_fix="Apply fix for H08",
        )
    return None


@register(
    CheckSpec(
        check_id="H09",
        domain="Images & media",
        title="Missing `fetchpriority` on LCP image",  # noqa: E501
        description="Detects: Missing `fetchpriority` on LCP image",  # noqa: E501
        why_it_matters="LCP optimization",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_H09(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_H09" in ctx.raw_html:
        return Finding(
            check_id="H09",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_H09"},
            why_it_matters="LCP optimization",
            recommended_fix="Apply fix for H09",
        )
    return None


@register(
    CheckSpec(
        check_id="H10",
        domain="Images & media",
        title="Oversized images (rendered << natural dimensions)",  # noqa: E501
        description="Detects: Oversized images (rendered << natural dimensions)",  # noqa: E501
        why_it_matters="Wasted bytes",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_H10(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_H10" in ctx.raw_html:
        return Finding(
            check_id="H10",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_H10"},
            why_it_matters="Wasted bytes",
            recommended_fix="Apply fix for H10",
        )
    return None


@register(
    CheckSpec(
        check_id="H11",
        domain="Images & media",
        title="Missing image sitemap entries",  # noqa: E501
        description="Detects: Missing image sitemap entries",  # noqa: E501
        why_it_matters="Image discovery",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_H11(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_H11" in ctx.raw_html:
        return Finding(
            check_id="H11",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_H11"},
            why_it_matters="Image discovery",
            recommended_fix="Apply fix for H11",
        )
    return None
