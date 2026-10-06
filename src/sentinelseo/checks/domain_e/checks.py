import re
from typing import Optional

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


@register(
    CheckSpec(
        check_id="E01",
        domain="Content quality",
        title="Exact duplicate content (MD5 body hash)",
        description="Detects: Exact duplicate content (MD5 body hash)",
        why_it_matters="Panda-class quality risk; index dilution",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_E01(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="E02",
        domain="Content quality",
        title="Near-duplicate content (similarity threshold)",
        description="Detects: Near-duplicate content (similarity threshold)",
        why_it_matters="Product variants, boilerplate pages",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_E02(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="E03",
        domain="Content quality",
        title="Technically duplicate URLs (same path+query, dup content)",
        description=(
            "Detects: Technically duplicate URLs (same path+query, dup content)"
        ),
        why_it_matters="Parameter/case duplication",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_E03(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="E04",
        domain="Content quality",
        title="Thin content (low word count / low main-content ratio)",
        description="Detects: Thin content (low word count / low main-content ratio)",
        why_it_matters="Weak page, may not rank/be cited",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_E04(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and ctx.url_row.status == 200 and ctx.url_row.indexable and ctx.url_row.word_count < 200:  # noqa: E501
        sev = "Medium" if ctx.url_row.word_count >= 100 else "High"
        return Finding(
            check_id="E04",
            severity=sev,
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"word_count": ctx.url_row.word_count},
            why_it_matters="Weak page, may not rank/be cited",
            recommended_fix="Expand with useful, unique content or consolidate.",
        )
    return None


@register(
    CheckSpec(
        check_id="E05",
        domain="Content quality",
        title="Duplicate title + meta description pair",
        description="Detects: Duplicate title + meta description pair",
        why_it_matters="Strong duplication signal",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_E05(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="E06",
        domain="Content quality",
        title="Keyword cannibalization (same H1/title competing)",
        description="Detects: Keyword cannibalization (same H1/title competing)",
        why_it_matters="Pages compete for same query",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_E06(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="E07",
        domain="Content quality",
        title="Boilerplate-heavy pages (nav/footer >> main content)",
        description="Detects: Boilerplate-heavy pages (nav/footer >> main content)",
        why_it_matters="Low unique value",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_E07(ctx: CrawlContext) -> Optional[Finding]:
    word_count = ctx.url_row.word_count if ctx.url_row else 0
    if word_count == 0:
        return None

    text_only = re.sub(r'<[^>]+>', ' ', ctx.raw_html or '')
    word_re = re.compile(r"\b\w[\w'-]*\b", re.UNICODE)
    full = len(word_re.findall(text_only))

    if full and (word_count / full) < 0.30 and full > 200:
        return Finding(
            check_id="E07",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"main_words": word_count, "total_words": full},
            why_it_matters="Low unique value",
            recommended_fix="Increase unique main content relative to nav/footer.",
        )
    return None


_LOREM = re.compile(
    r'\b(lorem ipsum|dolor sit amet|consectetur adipiscing|'
    r'placeholder text|your text here|sample text|insert text here)\b',
    re.I
)
# Strip <script>/<style> bodies so minified code/data can't false-positive.
_SCRIPT_STYLE = re.compile(r'(?is)<(script|style)[^>]*>.*?</\1>')

@register(
    CheckSpec(
        check_id="E08",
        domain="Content quality",
        title="Lorem ipsum / placeholder text detected",
        description="Detects: Lorem ipsum / placeholder text detected",
        why_it_matters="Unfinished content shipped",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_E08(ctx: CrawlContext) -> Optional[Finding]:
    html = _SCRIPT_STYLE.sub(' ', ctx.raw_html or '')
    text_only = re.sub(r'<[^>]+>', ' ', html)
    m = _LOREM.search(text_only)
    if m:
        return Finding(
            check_id="E08",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"match": m.group(0)},
            why_it_matters="Unfinished content shipped",
            recommended_fix="Replace placeholder text before launch.",
        )
    return None


@register(
    CheckSpec(
        check_id="E09",
        domain="Content quality",
        title="Spelling/grammar density anomalies (optional, LLM)",
        description="Detects: Spelling/grammar density anomalies (optional, LLM)",
        why_it_matters="Quality/E-E-A-T signal",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_E09(ctx: CrawlContext) -> Optional[Finding]:
    word_count = ctx.url_row.word_count if ctx.url_row else 0
    if word_count < 100:
        return None
    try:
        import textstat  # type: ignore[import-not-found]
    except ImportError:
        return None

    text_only = re.sub(r'<[^>]+>', ' ', ctx.raw_html or '')
    score = textstat.flesch_reading_ease(text_only)
    if score < 30:
        return Finding(
            check_id="E09",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"flesch": round(score, 1)},
            why_it_matters="Quality/E-E-A-T signal",
            recommended_fix="Shorten sentences; simplify vocabulary.",
        )
    return None


@register(
    CheckSpec(
        check_id="E10",
        domain="Content quality",
        title="Low text-to-HTML ratio",
        description="Detects: Low text-to-HTML ratio",
        why_it_matters="Bloat / thin main content",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_E10(ctx: CrawlContext) -> Optional[Finding]:
    html_bytes = ctx.url_row.size if ctx.url_row else 0
    if html_bytes:
        text_bytes = len(re.sub(r'<[^>]+>', ' ', ctx.raw_html or '').encode('utf-8'))
        ratio = text_bytes / html_bytes
        if ratio < 0.10:
            return Finding(
                check_id="E10",
                severity="Low",
                tier="REVIEW",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"ratio": round(ratio, 4)},
                why_it_matters="Bloat / thin main content",
                recommended_fix="Reduce markup bloat / increase content.",
            )
    return None


_HIDDEN_SEL = re.compile(
    r'(class=["\'][^"\']*\b(tab-pane|accordion-collapse|collapse|is-hidden)\b|'
    r'\bhidden\b|style=["\'][^"\']*display\s*:\s*none)',
    re.I
)

@register(
    CheckSpec(
        check_id="E11",
        domain="Content quality",
        title="Content hidden behind tabs/accordions/JS interactions",
        description="Detects: Content hidden behind tabs/accordions/JS interactions",
        why_it_matters="Invisible to AI crawlers & partially discounted",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_E11(ctx: CrawlContext) -> Optional[Finding]:
    html = ctx.rendered_html or ctx.raw_html or ""
    hits = len(_HIDDEN_SEL.findall(html))
    word_count = ctx.url_row.word_count if ctx.url_row else 0
    if hits >= 3 and word_count > 100:
        return Finding(
            check_id="E11",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"hidden_regions": hits},
            why_it_matters="Invisible to AI crawlers & partially discounted",
            recommended_fix="Ensure key content is visible on load or in server HTML.",
        )
    return None


@register(
    CheckSpec(
        check_id="E12",
        domain="Content quality",
        title="Missing/duplicate publish + modified dates",
        description="Detects: Missing/duplicate publish + modified dates",
        why_it_matters="Freshness signal weak (matters for GEO)",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_E12(ctx: CrawlContext) -> Optional[Finding]:
    has_date = any(
        k in (b.get("@type", "") if isinstance(b, dict) else "")
        for b in ctx.structured_data for k in ("Article", "BlogPosting", "NewsArticle")
    ) and any(
        b.get("datePublished") for b in ctx.structured_data if isinstance(b, dict)
    )
    word_count = ctx.url_row.word_count if ctx.url_row else 0
    if not has_date and word_count > 300:
        return Finding(
            check_id="E12",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={},
            why_it_matters="Freshness signal weak (matters for GEO)",
            recommended_fix="Expose publish and modified dates in markup.",
        )
    return None
