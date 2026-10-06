import re
from typing import Optional

from sentinelseo.checks._util import pixel_width
from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


def _headings_in_doc_order(ctx: CrawlContext) -> list[tuple[int, str]]:
    if not ctx.raw_html:
        return []
    tags = re.findall(r'<h([1-6])[^>]*>(.*?)</h\1>', ctx.raw_html, re.IGNORECASE | re.DOTALL)
    return [(int(lvl), txt) for lvl, txt in tags]

@register(
    CheckSpec(
        check_id="D01",
        domain="Titles, meta and headings",
        title="Missing page title",
        description="Detects: Missing page title",
        why_it_matters="No primary relevance/CTR signal",
        default_severity="High",
        fix_tier="AUTO",
        data_source="C",
        fix_template=None,
    )
)
def check_D01(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and ctx.url_row.status == 200 and ctx.url_row.indexable and not (ctx.title and ctx.title.strip()):
        return Finding(
            check_id="D01",
            severity="High",
            tier="AUTO",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={},
            why_it_matters="No primary relevance/CTR signal",
            recommended_fix="Add a unique, descriptive title tag."
        )
    return None

@register(
    CheckSpec(
        check_id="D02",
        domain="Titles, meta and headings",
        title="Duplicate titles (across URLs)",
        description="Detects: Duplicate titles (across URLs)",
        why_it_matters="Cannibalization, unclear target",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_D02(ctx: CrawlContext) -> Optional[Finding]:
    return None

@register(
    CheckSpec(
        check_id="D03",
        domain="Titles, meta and headings",
        title="Title too long (>~60 chars / ~575px)",
        description="Detects: Title too long (>~60 chars / ~575px)",
        why_it_matters="Truncated in SERP",
        default_severity="Low",
        fix_tier="AUTO",
        data_source="C",
        fix_template=None,
    )
)
def check_D03(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.title:
        px = pixel_width(ctx.title)
        if px > 561:
            return Finding(
                check_id="D03",
                severity="Low",
                tier="AUTO",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"pixels": px, "title": ctx.title},
                why_it_matters="Truncated in SERP",
                recommended_fix="Shorten to avoid truncation."
            )
    return None

@register(
    CheckSpec(
        check_id="D04",
        domain="Titles, meta and headings",
        title="Title too short (<~30 chars)",
        description="Detects: Title too short (<~30 chars)",
        why_it_matters="Under-optimized",
        default_severity="Low",
        fix_tier="AUTO",
        data_source="C",
        fix_template=None,
    )
)
def check_D04(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.title:
        px = pixel_width(ctx.title)
        if px < 200:
            return Finding(
                check_id="D04",
                severity="Low",
                tier="AUTO",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"pixels": px},
                why_it_matters="Under-optimized",
                recommended_fix="Expand the title to use available space."
            )
    return None

@register(
    CheckSpec(
        check_id="D05",
        domain="Titles, meta and headings",
        title="Multiple `<title>` elements",
        description="Detects: Multiple `<title>` elements",
        why_it_matters="Invalid; ambiguous",
        default_severity="Medium",
        fix_tier="AUTO",
        data_source="C",
        fix_template=None,
    )
)
def check_D05(ctx: CrawlContext) -> Optional[Finding]:
    title_count = ctx.raw_html.lower().count("<title")
    if title_count > 1:
        return Finding(
            check_id="D05",
            severity="Medium",
            tier="AUTO",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"count": title_count},
            why_it_matters="Invalid; ambiguous",
            recommended_fix="Keep a single title tag."
        )
    return None

@register(
    CheckSpec(
        check_id="D06",
        domain="Titles, meta and headings",
        title="Title same as H1 (exact) on all pages",
        description="Detects: Title same as H1 (exact) on all pages",
        why_it_matters="Missed keyword coverage",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_D06(ctx: CrawlContext) -> Optional[Finding]:
    return None

@register(
    CheckSpec(
        check_id="D07",
        domain="Titles, meta and headings",
        title="Missing meta description",
        description="Detects: Missing meta description",
        why_it_matters="Google auto-generates; lost CTR control",
        default_severity="Medium",
        fix_tier="AUTO",
        data_source="C",
        fix_template=None,
    )
)
def check_D07(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and ctx.url_row.status == 200 and ctx.url_row.indexable and ctx.url_row.meta_desc is None:
        return Finding(
            check_id="D07",
            severity="Medium",
            tier="AUTO",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={},
            why_it_matters="Google auto-generates; lost CTR control",
            recommended_fix="Add a detailed description (about 120 to 320 characters) "
                            "that summarizes the page and names its key products, "
                            "services and topics, so search engines and AI assistants "
                            "understand it."
        )
    return None

@register(
    CheckSpec(
        check_id="D08",
        domain="Titles, meta and headings",
        title="Duplicate meta descriptions",
        description="Detects: Duplicate meta descriptions",
        why_it_matters="Weak differentiation",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_D08(ctx: CrawlContext) -> Optional[Finding]:
    return None

@register(
    CheckSpec(
        check_id="D09",
        domain="Titles, meta and headings",
        title="Meta description too thin for AI",
        description="Detects: meta description present but too short to give AI or "
                    "searchers useful context",
        why_it_matters="Little context for AI assistants and searchers",
        default_severity="Low",
        fix_tier="AUTO",
        data_source="C",
        fix_template=None,
    )
)
def check_D09(ctx: CrawlContext) -> Optional[Finding]:
    # A detailed description is the first thing AI assistants read about a page, so
    # flag ones that are present but too thin to give real context. Length is no
    # longer penalised: a long, well-summarised description is good, so there is no
    # upper limit here (about 120 characters is a healthy floor).
    if ctx.url_row and ctx.url_row.meta_desc:
        chars = len(ctx.url_row.meta_desc.strip())
        if 0 < chars < 120:
            return Finding(
                check_id="D09",
                severity="Low",
                tier="AUTO",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"chars": chars},
                why_it_matters="Little context for AI assistants and searchers",
                recommended_fix="Expand it into a detailed summary that names the key "
                                "products, services and topics on the page, so AI and "
                                "searchers understand it."
            )
    return None

@register(
    CheckSpec(
        check_id="D10",
        domain="Titles, meta and headings",
        title="Meta description too short",
        description="Detects: (folded into D09 — meta description too thin for AI)",
        why_it_matters="Under-used real estate",
        default_severity="Low",
        fix_tier="AUTO",
        data_source="C",
        fix_template=None,
    )
)
def check_D10(ctx: CrawlContext) -> Optional[Finding]:
    # Folded into D09 (meta description too thin for AI) so a short description is
    # flagged once, not twice. Kept registered so existing precedence/suppression
    # rules stay stable; it no longer emits its own finding.
    return None

@register(
    CheckSpec(
        check_id="D11",
        domain="Titles, meta and headings",
        title="Multiple meta descriptions",
        description="Detects: Multiple meta descriptions",
        why_it_matters="Ambiguous",
        default_severity="Low",
        fix_tier="AUTO",
        data_source="C",
        fix_template=None,
    )
)
def check_D11(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.raw_html:
        count = len(re.findall(r'<meta[^>]+name=["\']description["\']', ctx.raw_html, re.IGNORECASE))
        if count > 1:
            return Finding(
                check_id="D11",
                severity="Low",
                tier="AUTO",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"count": count},
                why_it_matters="Ambiguous",
                recommended_fix="Ensure only one meta description exists."
            )
    return None

@register(
    CheckSpec(
        check_id="D12",
        domain="Titles, meta and headings",
        title="Missing H1",
        description="Detects: Missing H1",
        why_it_matters="Lost relevance signal",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_D12(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and ctx.url_row.status == 200 and not ctx.url_row.h1:
        return Finding(
            check_id="D12",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={},
            why_it_matters="Lost relevance signal",
            recommended_fix="Add one descriptive H1."
        )
    return None

@register(
    CheckSpec(
        check_id="D13",
        domain="Titles, meta and headings",
        title="Multiple H1s",
        description="Detects: Multiple H1s",
        why_it_matters="Diluted primary topic (context-dependent)",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_D13(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and ctx.url_row.h1 and len(ctx.url_row.h1) > 1:
        return Finding(
            check_id="D13",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"count": len(ctx.url_row.h1)},
            why_it_matters="Diluted primary topic (context-dependent)",
            recommended_fix="Prefer a single H1 (context-dependent)."
        )
    return None

@register(
    CheckSpec(
        check_id="D14",
        domain="Titles, meta and headings",
        title="Duplicate H1 across URLs",
        description="Detects: Duplicate H1 across URLs",
        why_it_matters="Cannibalization",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_D14(ctx: CrawlContext) -> Optional[Finding]:
    return None

@register(
    CheckSpec(
        check_id="D15",
        domain="Titles, meta and headings",
        title="Broken heading order (skips H2→H4)",
        description="Detects: Broken heading order (skips H2→H4)",
        why_it_matters="Accessibility + structure signal",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_D15(ctx: CrawlContext) -> Optional[Finding]:
    ordered = _headings_in_doc_order(ctx)
    prev = 0
    jumped = False
    for lvl, _txt in ordered:
        if prev and lvl > prev + 1:
            jumped = True
            break
        prev = lvl
    if jumped:
        return Finding(
            check_id="D15",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={},
            why_it_matters="Accessibility + structure signal",
            recommended_fix="Keep heading hierarchy sequential."
        )
    return None

@register(
    CheckSpec(
        check_id="D16",
        domain="Titles, meta and headings",
        title="Empty heading tags",
        description="Detects: Empty heading tags",
        why_it_matters="Structural noise",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_D16(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row:
        headings = {
            1: ctx.url_row.h1 or [],
            2: ctx.url_row.h2 or [],
            3: ctx.url_row.h3 or [],
            4: ctx.url_row.h4 or [],
            5: ctx.url_row.h5 or [],
            6: ctx.url_row.h6 or [],
        }
        empties = [lvl for lvl, texts in headings.items() for t in texts if not t.strip()]
        if empties:
            return Finding(
                check_id="D16",
                severity="Low",
                tier="REVIEW",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={},
                why_it_matters="Structural noise",
                recommended_fix="Remove empty headings or add text."
            )
    return None

@register(
    CheckSpec(
        check_id="D17",
        domain="Titles, meta and headings",
        title="Title/description created or modified by JS only",
        description="Detects: Title/description created or modified by JS only",
        why_it_matters="Render-dependent metadata",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_D17(ctx: CrawlContext) -> Optional[Finding]:
    render_diff = {d.element: d.state for d in ctx.render_diffs} if ctx.render_diffs else {}
    changed = [k for k in ("title", "meta_desc") if render_diff.get(k) in ("created", "modified")]
    if changed:
        return Finding(
            check_id="D17",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"changed": changed},
            why_it_matters="Render-dependent metadata",
            recommended_fix="Render metadata server-side."
        )
    return None

@register(
    CheckSpec(
        check_id="D18",
        domain="Titles, meta and headings",
        title="Meta keywords tag present",
        description="Detects: Meta keywords tag present",
        why_it_matters="Legacy/ignored; sometimes spam signal",
        default_severity="Low",
        fix_tier="AUTO",
        data_source="C",
        fix_template=None,
    )
)
def check_D18(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.raw_html and bool(re.search(r'<meta[^>]+name=["\']keywords["\']', ctx.raw_html, re.IGNORECASE)):
        return Finding(
            check_id="D18",
            severity="Low",
            tier="AUTO",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={},
            why_it_matters="Legacy/ignored; sometimes spam signal",
            recommended_fix="Remove the meta keywords tag."
        )
    return None

@register(
    CheckSpec(
        check_id="D19",
        domain="Titles, meta and headings",
        title="Missing/incorrect OG + Twitter Card tags",
        description="Detects: Missing/incorrect OG + Twitter Card tags",
        why_it_matters="Poor social/preview rendering",
        default_severity="Low",
        fix_tier="AUTO",
        data_source="C",
        fix_template=None,
    )
)
def check_D19(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.raw_html and ctx.url_row and getattr(ctx.url_row, "indexable", True):
        missing = []
        if not re.search(r'<meta[^>]+property=["\']og:title["\']', ctx.raw_html, re.IGNORECASE):
            missing.append("og:title")
        if not re.search(r'<meta[^>]+property=["\']og:description["\']', ctx.raw_html, re.IGNORECASE):
            missing.append("og:description")
        if not re.search(r'<meta[^>]+property=["\']og:image["\']', ctx.raw_html, re.IGNORECASE):
            missing.append("og:image")

        if missing:
            return Finding(
                check_id="D19",
                severity="Low",
                tier="AUTO",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"missing": missing},
                why_it_matters="Poor social/preview rendering",
                recommended_fix="Add OG + Twitter Card tags for rich previews."
            )
    return None

@register(
    CheckSpec(
        check_id="D20",
        domain="Titles, meta and headings",
        title="Missing viewport meta",
        description="Detects: Missing viewport meta",
        why_it_matters="Mobile rendering broken",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_D20(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and ctx.url_row.status == 200 and ctx.raw_html:
        if not re.search(r'<meta[^>]+name=["\']viewport["\']', ctx.raw_html, re.IGNORECASE):
            return Finding(
                check_id="D20",
                severity="High",
                tier="REVIEW",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={},
                why_it_matters="Mobile rendering broken",
                recommended_fix="Add <meta name=viewport content='width=device-width, initial-scale=1'>."
            )
    return None

@register(
    CheckSpec(
        check_id="D21",
        domain="Titles, meta and headings",
        title="Heading over 70 characters",
        description="Detects: Heading over 70 characters",
        why_it_matters="Too long for readability",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_D21(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row:
        headings = {
            1: ctx.url_row.h1 or [],
            2: ctx.url_row.h2 or [],
        }
        long_h = [(lvl, t) for lvl in (1, 2) for t in headings.get(lvl, []) if len(t) > 70]
        if long_h:
            return Finding(
                check_id="D21",
                severity="Low",
                tier="REVIEW",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"examples": [t for _, t in long_h[:3]]},
                why_it_matters="Too long for readability",
                recommended_fix="Tighten long headings."
            )
    return None

