from __future__ import annotations

from typing import Optional

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


@register(
    CheckSpec(
        check_id="O01",
        domain="Mobile",
        title="Missing/incorrect viewport meta",
        description="Detects: Missing/incorrect viewport meta",
        why_it_matters="Not mobile-usable",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_O01(ctx: CrawlContext) -> Finding | None:
    if not ctx.raw_html:
        return None

    viewport_meta = None
    for m in ctx.dom().css("meta"):
        if (m.attributes.get("name") or "").lower() == "viewport":
            viewport_meta = m
            break

    if viewport_meta is None:
        return Finding(
            check_id="O01",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"viewport_meta": "Missing"},
            why_it_matters="Not mobile-usable",
            recommended_fix=(
                'Add a <meta name="viewport" content="width=device-width, '
                'initial-scale=1"> tag to the <head>.'
            ),
        )

    content = (viewport_meta.attributes.get("content") or "").lower()

    if "width=device-width" not in content or "initial-scale" not in content:
        return Finding(
            check_id="O01",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"viewport_meta": content},
            why_it_matters="Not mobile-usable",
            recommended_fix=(
                "Ensure the viewport meta tag contains width=device-width "
                "and initial-scale."
            ),
        )

    return None


@register(
    CheckSpec(
        check_id="O02",
        domain="Mobile",
        title="Tap targets too small / too close",
        description="Detects: Tap targets too small / too close",
        why_it_matters="Mobile UX; usability signal",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_O02(ctx: CrawlContext) -> Optional[Finding]:
    mc = getattr(ctx.url_row, "mobile_context", None) if ctx.url_row else None
    n = getattr(mc, "smallTapTargets", 0) if mc else 0
    if n >= 5:
        return Finding(
            check_id="O02",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"small_tap_targets": n},
            why_it_matters="Mobile UX; usability signal",
            recommended_fix="Make tap targets at least 44x44px with adequate spacing.",
        )
    return None


@register(
    CheckSpec(
        check_id="O03",
        domain="Mobile",
        title="Content wider than viewport (horizontal scroll)",
        description="Detects: Content wider than viewport (horizontal scroll)",
        why_it_matters="Mobile UX",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_O03(ctx: CrawlContext) -> Optional[Finding]:
    mc = getattr(ctx.url_row, "mobile_context", None) if ctx.url_row else None
    if mc is not None and getattr(mc, "contentWiderThanViewport", False):
        return Finding(
            check_id="O03",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"content_wider_than_viewport": True},
            why_it_matters="Mobile UX; horizontal scroll",
            recommended_fix="Use responsive layouts; avoid fixed widths beyond the viewport.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="O04",
        domain="Mobile",
        title="Font size too small on mobile",
        description="Detects: Font size too small on mobile",
        why_it_matters="Readability",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_O04(ctx: CrawlContext) -> Optional[Finding]:
    mc = getattr(ctx.url_row, "mobile_context", None) if ctx.url_row else None
    n = getattr(mc, "smallFonts", 0) if mc else 0
    if n >= 5:
        return Finding(
            check_id="O04",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"small_font_elements": n},
            why_it_matters="Readability",
            recommended_fix="Use a base font size of at least 12–16px on mobile.",
        )
    return None


@register(
    CheckSpec(
        check_id="O05",
        domain="Mobile",
        title="Mobile vs desktop content parity gap (mobile-first index)",
        description=(
            "Detects: Mobile vs desktop content parity gap (mobile-first index)"
        ),
        why_it_matters="Content missing on mobile render",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_O05(ctx: CrawlContext) -> Optional[Finding]:
    mc = getattr(ctx.url_row, "mobile_context", None) if ctx.url_row else None
    if mc is None:
        return None
    mobile_text = getattr(mc, "mobile_text", "") or ""
    desktop_text = getattr(ctx.url_row, "main_text", "") or ""
    if len(desktop_text) > 500 and len(mobile_text) < len(desktop_text) * 0.7:
        return Finding(
            check_id="O05",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"desktop_chars": len(desktop_text), "mobile_chars": len(mobile_text)},  # noqa: E501
            why_it_matters="Content missing on mobile render (mobile-first index)",
            recommended_fix="Ensure the mobile render exposes the same primary content as desktop.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="O06",
        domain="Mobile",
        title="Intrusive interstitials/pop-ups on mobile",
        description="Detects: Intrusive interstitials/pop-ups on mobile",
        why_it_matters="Ranking penalty risk",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_O06(ctx: CrawlContext) -> Optional[Finding]:
    mc = getattr(ctx.url_row, "mobile_context", None) if ctx.url_row else None
    if mc is not None and getattr(mc, "hasInterstitial", False):
        return Finding(
            check_id="O06",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"interstitial": True},
            why_it_matters="Ranking penalty risk",
            recommended_fix="Remove intrusive full-screen interstitials/pop-ups on mobile.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="O07",
        domain="Mobile",
        title="Blocked resources on mobile UA only",
        description="Detects: Blocked resources on mobile UA only",
        why_it_matters="Cloaked rendering issue",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_O07(ctx: CrawlContext) -> Optional[Finding]:
    mc = getattr(ctx.url_row, "mobile_context", None) if ctx.url_row else None
    blocked = getattr(mc, "blocked_resources", None) if mc else None
    if blocked:
        return Finding(
            check_id="O07",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"blocked_resources": list(blocked)[:10]},
            why_it_matters="Cloaked rendering issue on mobile UA",
            recommended_fix="Unblock resources needed to render for the mobile crawler.",
        )
    return None
