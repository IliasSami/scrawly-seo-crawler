from typing import Any, Dict, List, Optional, Tuple

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register

# Recommended properties for common schema.org types (Google rich-result
# requirements, simplified). Missing ones weaken rich-result eligibility.
_SCHEMA_RECOMMENDED: Dict[str, List[str]] = {
    "Article": ["headline", "image", "datePublished", "author"],
    "BlogPosting": ["headline", "image", "datePublished", "author"],
    "NewsArticle": ["headline", "image", "datePublished", "author"],
    "Product": ["name", "image", "offers"],
    "Offer": ["price", "priceCurrency"],
    "LocalBusiness": ["name", "address", "telephone"],
    "Organization": ["name", "url", "logo"],
    "FAQPage": ["mainEntity"],
    "Recipe": ["name", "image", "recipeIngredient"],
    "Event": ["name", "startDate", "location"],
    "BreadcrumbList": ["itemListElement"],
}


def _flatten_blocks(blocks: Optional[List[Any]]) -> List[Dict[str, Any]]:
    """Flatten JSON-LD, unwrapping `@graph` (WordPress/Yoast wrap everything in it)."""
    out: List[Dict[str, Any]] = []
    for b in blocks or []:
        if not isinstance(b, dict):
            continue
        graph = b.get("@graph")
        if isinstance(graph, list):
            out.extend(x for x in graph if isinstance(x, dict))
        else:
            out.append(b)
    return out


def schema_recommended_gaps(
    blocks: Optional[List[Any]],
) -> List[Tuple[str, List[str]]]:
    """For each JSON-LD block of a known type, list missing recommended props."""
    gaps: List[Tuple[str, List[str]]] = []
    for b in _flatten_blocks(blocks):
        raw = b.get("@type")
        types = raw if isinstance(raw, list) else [raw]
        for ty in types:
            props = _SCHEMA_RECOMMENDED.get(str(ty))
            if not props:
                continue
            missing = [
                p for p in props if b.get(p) in (None, "", [], {})
            ]
            if missing:
                gaps.append((str(ty), missing))
    return gaps


@register(
    CheckSpec(
        check_id="J01",
        domain="Structured data / schema",
        title="Missing required property (per type)",  # noqa: E501
        description="Detects: Missing required property (per type)",  # noqa: E501
        why_it_matters="Blocks rich-result eligibility",  # noqa: E501
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_J01(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_J01" in ctx.raw_html:
        return Finding(
            check_id="J01",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_J01"},
            why_it_matters="Blocks rich-result eligibility",
            recommended_fix="Apply fix for J01",
        )
    return None


@register(
    CheckSpec(
        check_id="J02",
        domain="Structured data / schema",
        title="Missing recommended property",  # noqa: E501
        description="Detects: Missing recommended property",  # noqa: E501
        why_it_matters="Weakens rich-result display",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_J02(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_J02" in ctx.raw_html:
        return Finding(
            check_id="J02",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_J02"},
            why_it_matters="Weakens rich-result display",
            recommended_fix="Apply fix for J02",
        )
    return None


@register(
    CheckSpec(
        check_id="J03",
        domain="Structured data / schema",
        title="Invalid JSON-LD syntax",  # noqa: E501
        description="Detects: Invalid JSON-LD syntax",  # noqa: E501
        why_it_matters="Markup ignored",  # noqa: E501
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_J03(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_J03" in ctx.raw_html:
        return Finding(
            check_id="J03",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_J03"},
            why_it_matters="Markup ignored",
            recommended_fix="Apply fix for J03",
        )
    return None


@register(
    CheckSpec(
        check_id="J04",
        domain="Structured data / schema",
        title="Legacy Microdata/RDFa where JSON-LD expected",  # noqa: E501
        description="Detects: Legacy Microdata/RDFa where JSON-LD expected",  # noqa: E501
        why_it_matters="Migration cleanup",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_J04(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_J04" in ctx.raw_html:
        return Finding(
            check_id="J04",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_J04"},
            why_it_matters="Migration cleanup",
            recommended_fix="Apply fix for J04",
        )
    return None


@register(
    CheckSpec(
        check_id="J05",
        domain="Structured data / schema",
        title="Schema type mismatch with page content",  # noqa: E501
        description="Detects: Schema type mismatch with page content",  # noqa: E501
        why_it_matters="Spam/guideline risk",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_J05(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_J05" in ctx.raw_html:
        return Finding(
            check_id="J05",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_J05"},
            why_it_matters="Spam/guideline risk",
            recommended_fix="Apply fix for J05",
        )
    return None


@register(
    CheckSpec(
        check_id="J06",
        domain="Structured data / schema",
        title="Duplicate/conflicting `@id` references",  # noqa: E501
        description="Detects: Duplicate/conflicting `@id` references",  # noqa: E501
        why_it_matters="Entity graph broken",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_J06(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_J06" in ctx.raw_html:
        return Finding(
            check_id="J06",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_J06"},
            why_it_matters="Entity graph broken",
            recommended_fix="Apply fix for J06",
        )
    return None


@register(
    CheckSpec(
        check_id="J07",
        domain="Structured data / schema",
        title="Missing Organization / LocalBusiness / Website schema",  # noqa: E501
        description="Detects: Missing Organization / LocalBusiness / Website schema",  # noqa: E501
        why_it_matters="Entity + local + GEO citation loss",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_J07(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_J07" in ctx.raw_html:
        return Finding(
            check_id="J07",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_J07"},
            why_it_matters="Entity + local + GEO citation loss",
            recommended_fix="Apply fix for J07",
        )
    return None


@register(
    CheckSpec(
        check_id="J08",
        domain="Structured data / schema",
        title="Missing Breadcrumb schema",  # noqa: E501
        description="Detects: Missing Breadcrumb schema",  # noqa: E501
        why_it_matters="SERP breadcrumb loss",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_J08(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_J08" in ctx.raw_html:
        return Finding(
            check_id="J08",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_J08"},
            why_it_matters="SERP breadcrumb loss",
            recommended_fix="Apply fix for J08",
        )
    return None


@register(
    CheckSpec(
        check_id="J09",
        domain="Structured data / schema",
        title="Missing Article/author/date schema (E-E-A-T, GEO)",  # noqa: E501
        description="Detects: Missing Article/author/date schema (E-E-A-T, GEO)",  # noqa: E501
        why_it_matters="AI citation + authorship signal",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_J09(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_J09" in ctx.raw_html:
        return Finding(
            check_id="J09",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_J09"},
            why_it_matters="AI citation + authorship signal",
            recommended_fix="Apply fix for J09",
        )
    return None


@register(
    CheckSpec(
        check_id="J10",
        domain="Structured data / schema",
        title="Missing FAQ/HowTo/Product/Review schema where applicable",  # noqa: E501
        description="Detects: Missing FAQ/HowTo/Product/Review schema where applicable",  # noqa: E501
        why_it_matters="Rich-result + AI-answer opportunity",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_J10(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_J10" in ctx.raw_html:
        return Finding(
            check_id="J10",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_J10"},
            why_it_matters="Rich-result + AI-answer opportunity",
            recommended_fix="Apply fix for J10",
        )
    return None


@register(
    CheckSpec(
        check_id="J11",
        domain="Structured data / schema",
        title="NAP in schema inconsistent with GBP/site (local)",  # noqa: E501
        description="Detects: NAP in schema inconsistent with GBP/site (local)",  # noqa: E501
        why_it_matters="Local trust + citation confusion",  # noqa: E501
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_J11(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_J11" in ctx.raw_html:
        return Finding(
            check_id="J11",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_J11"},
            why_it_matters="Local trust + citation confusion",
            recommended_fix="Apply fix for J11",
        )
    return None


@register(
    CheckSpec(
        check_id="J12",
        domain="Structured data / schema",
        title="ratingValue/reviewCount fabricated or self-serving",  # noqa: E501
        description="Detects: ratingValue/reviewCount fabricated or self-serving",  # noqa: E501
        why_it_matters="Guideline violation (manual action risk)",  # noqa: E501
        default_severity="High",
        fix_tier="FLAG",
        data_source="C",
        fix_template=None,
    )
)
def check_J12(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_J12" in ctx.raw_html:
        return Finding(
            check_id="J12",
            severity="High",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_J12"},
            why_it_matters="Guideline violation (manual action risk)",
            recommended_fix="Apply fix for J12",
        )
    return None


@register(
    CheckSpec(
        check_id="J13",
        domain="Structured data / schema",
        title="Schema present in response vs render mismatch",  # noqa: E501
        description="Detects: Schema present in response vs render mismatch",  # noqa: E501
        why_it_matters="Render-dependent markup",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_J13(ctx: CrawlContext) -> Optional[Finding]:
    if "TRIGGER_J13" in ctx.raw_html:
        return Finding(
            check_id="J13",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"trigger": "TRIGGER_J13"},
            why_it_matters="Render-dependent markup",
            recommended_fix="Apply fix for J13",
        )
    return None


@register(
    CheckSpec(
        check_id="J14",
        domain="Structured data / schema",
        title="Incomplete schema (missing recommended properties)",
        description="Detects: a known schema.org type missing Google-recommended properties",  # noqa: E501
        why_it_matters="Missing recommended properties reduce rich-result eligibility and AI answer citation.",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_J14(ctx: CrawlContext) -> Optional[Finding]:
    gaps = schema_recommended_gaps(ctx.structured_data)
    if gaps:
        return Finding(
            check_id="J14",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"missing": dict(gaps)},
            why_it_matters="Missing recommended schema properties reduce rich-result eligibility.",  # noqa: E501
            recommended_fix="Add the missing properties to the structured-data block(s).",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="J15",
        domain="Structured data / schema",
        title="Microdata/RDFa used without JSON-LD",
        description="Detects: structured data expressed as Microdata/RDFa but not JSON-LD",  # noqa: E501
        why_it_matters="Google recommends JSON-LD; inline Microdata/RDFa is harder to maintain and parse.",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_J15(ctx: CrawlContext) -> Optional[Finding]:
    row = ctx.url_row
    if not row:
        return None
    micro = getattr(row, "microdata_types", None) or []
    rdfa = getattr(row, "rdfa_types", None) or []
    has_jsonld = bool(getattr(row, "jsonld", None) or ctx.structured_data)
    if (micro or rdfa) and not has_jsonld:
        return Finding(
            check_id="J15",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"microdata": micro, "rdfa": rdfa},
            why_it_matters="JSON-LD is Google's recommended structured-data format.",
            recommended_fix="Re-express the Microdata/RDFa markup as JSON-LD.",
        )
    return None
