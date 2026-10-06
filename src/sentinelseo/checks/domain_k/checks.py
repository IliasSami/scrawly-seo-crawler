from typing import Optional

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


@register(
    CheckSpec(
        check_id="K01",
        domain="XML sitemaps",
        title="Sitemap missing / not referenced in robots.txt",  # noqa: E501
        description="Detects: Sitemap missing / not referenced in robots.txt",  # noqa: E501
        why_it_matters="Discovery gap",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_K01(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_K01" in ctx.raw_html:
        return Finding(
            check_id="K01",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_K01"},
            why_it_matters="Discovery gap",
            recommended_fix="Apply fix for K01",
        )
    return None


@register(
    CheckSpec(
        check_id="K02",
        domain="XML sitemaps",
        title="Sitemap contains non-200 URLs",  # noqa: E501
        description="Detects: Sitemap contains non-200 URLs",  # noqa: E501
        why_it_matters="Dirty sitemap; wasted crawl",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_K02(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_K02" in ctx.raw_html:
        return Finding(
            check_id="K02",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_K02"},
            why_it_matters="Dirty sitemap; wasted crawl",
            recommended_fix="Apply fix for K02",
        )
    return None


@register(
    CheckSpec(
        check_id="K03",
        domain="XML sitemaps",
        title="Sitemap contains noindex / canonicalized-away URLs",  # noqa: E501
        description="Detects: Sitemap contains noindex / canonicalized-away URLs",  # noqa: E501
        why_it_matters="Conflicting signals",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_K03(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_K03" in ctx.raw_html:
        return Finding(
            check_id="K03",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_K03"},
            why_it_matters="Conflicting signals",
            recommended_fix="Apply fix for K03",
        )
    return None


@register(
    CheckSpec(
        check_id="K04",
        domain="XML sitemaps",
        title="Sitemap contains redirects",  # noqa: E501
        description="Detects: Sitemap contains redirects",  # noqa: E501
        why_it_matters="Should list final URLs",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_K04(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_K04" in ctx.raw_html:
        return Finding(
            check_id="K04",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_K04"},
            why_it_matters="Should list final URLs",
            recommended_fix="Apply fix for K04",
        )
    return None


@register(
    CheckSpec(
        check_id="K05",
        domain="XML sitemaps",
        title="Indexable pages missing from sitemap",  # noqa: E501
        description="Detects: Indexable pages missing from sitemap",  # noqa: E501
        why_it_matters="Discovery gap",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_K05(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_K05" in ctx.raw_html:
        return Finding(
            check_id="K05",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_K05"},
            why_it_matters="Discovery gap",
            recommended_fix="Apply fix for K05",
        )
    return None


@register(
    CheckSpec(
        check_id="K06",
        domain="XML sitemaps",
        title="Sitemap >50k URLs / >50MB (uncompressed)",  # noqa: E501
        description="Detects: Sitemap >50k URLs / >50MB (uncompressed)",  # noqa: E501
        why_it_matters="Spec violation",  # noqa: E501
        default_severity="Medium",
        fix_tier="FLAG",
        data_source="C",
        fix_template=None,
    )
)
def check_K06(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_K06" in ctx.raw_html:
        return Finding(
            check_id="K06",
            severity="Medium",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_K06"},
            why_it_matters="Spec violation",
            recommended_fix="Apply fix for K06",
        )
    return None


@register(
    CheckSpec(
        check_id="K07",
        domain="XML sitemaps",
        title="Invalid XML / malformed sitemap",  # noqa: E501
        description="Detects: Invalid XML / malformed sitemap",  # noqa: E501
        why_it_matters="Not parsed",  # noqa: E501
        default_severity="High",
        fix_tier="FLAG",
        data_source="C",
        fix_template=None,
    )
)
def check_K07(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_K07" in ctx.raw_html:
        return Finding(
            check_id="K07",
            severity="High",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_K07"},
            why_it_matters="Not parsed",
            recommended_fix="Apply fix for K07",
        )
    return None


@register(
    CheckSpec(
        check_id="K08",
        domain="XML sitemaps",
        title="`<lastmod>` missing or clearly inaccurate",  # noqa: E501
        description="Detects: `<lastmod>` missing or clearly inaccurate",  # noqa: E501
        why_it_matters="Freshness signal weak",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_K08(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_K08" in ctx.raw_html:
        return Finding(
            check_id="K08",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_K08"},
            why_it_matters="Freshness signal weak",
            recommended_fix="Apply fix for K08",
        )
    return None


@register(
    CheckSpec(
        check_id="K09",
        domain="XML sitemaps",
        title="Orphan sitemap URLs (in sitemap, no inlinks)",  # noqa: E501
        description="Detects: Orphan sitemap URLs (in sitemap, no inlinks)",  # noqa: E501
        why_it_matters="Weak internal support",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_K09(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_K09" in ctx.raw_html:
        return Finding(
            check_id="K09",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_K09"},
            why_it_matters="Weak internal support",
            recommended_fix="Apply fix for K09",
        )
    return None


@register(
    CheckSpec(
        check_id="K10",
        domain="XML sitemaps",
        title="Sitemap not auto-updating (stale vs new content)",  # noqa: E501
        description="Detects: Sitemap not auto-updating (stale vs new content)",  # noqa: E501
        why_it_matters="Slow discovery",  # noqa: E501
        default_severity="Low",
        fix_tier="FLAG",
        data_source="C",
        fix_template=None,
    )
)
def check_K10(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_K10" in ctx.raw_html:
        return Finding(
            check_id="K10",
            severity="Low",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_K10"},
            why_it_matters="Slow discovery",
            recommended_fix="Apply fix for K10",
        )
    return None
