import json
import re
from typing import Any, Optional

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


def _best_tree(ctx: CrawlContext) -> Any:
    """Parse the rendered DOM if present, else the raw response (cached once)."""
    return ctx.dom(bool(ctx.rendered_html))


@register(
    CheckSpec(
        check_id="S01",
        domain="Agentic-web experience (Lighthouse 13.3 Agentic Browsing + beyond)",
        title="Missing `llms.txt` at root",
        description="Detects: Missing `llms.txt` at root",
        why_it_matters="Lighthouse informational; curated AI index absent",
        default_severity="Info",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_S01(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="S02",
        domain="Agentic-web experience (Lighthouse 13.3 Agentic Browsing + beyond)",
        title="`llms.txt` present but missing H1 / too short / no links",
        description="Detects: `llms.txt` present but missing H1 / too short / no links",
        why_it_matters="Fails Lighthouse llms.txt sub-checks",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_S02(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.url.endswith("/llms.txt"):
        return None

    html = ctx.rendered_html or ctx.raw_html
    if not html:
        return None

    tree = _best_tree(ctx)
    has_h1 = tree.css_first("h1") is not None
    links = tree.css("a")

    if not has_h1 or len(html) < 50 or len(links) == 0:
        return Finding(
            check_id="S02",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"has_h1": has_h1, "length": len(html), "link_count": len(links)},
            why_it_matters="Fails Lighthouse llms.txt sub-checks",
            recommended_fix="Ensure llms.txt has a primary H1, adequate content, and links.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="S03",
        domain="Agentic-web experience (Lighthouse 13.3 Agentic Browsing + beyond)",
        title="`llms.txt` is a link dump (800–1200 unsorted links)",
        description="Detects: `llms.txt` is a link dump (800–1200 unsorted links)",
        why_it_matters="Low-signal; aim 20–50 high-value links",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_S03(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.url.endswith("/llms.txt"):
        return None

    html = ctx.rendered_html or ctx.raw_html
    if not html:
        return None

    links = _best_tree(ctx).css("a")

    if len(links) > 800:
        return Finding(
            check_id="S03",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"link_count": len(links)},
            why_it_matters="Low-signal; aim 20–50 high-value links",
            recommended_fix="Reduce links in llms.txt to high-value curated list.",
        )
    return None


@register(
    CheckSpec(
        check_id="S04",
        domain="Agentic-web experience (Lighthouse 13.3 Agentic Browsing + beyond)",
        title="Optional `llms-full.txt` absent (large-doc sites)",
        description="Detects: Optional `llms-full.txt` absent (large-doc sites)",
        why_it_matters="Full-content AI index missing",
        default_severity="Info",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_S04(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="S05",
        domain="Agentic-web experience (Lighthouse 13.3 Agentic Browsing + beyond)",
        title="Accessibility tree fails agent-centric names/labels",
        description="Detects: Accessibility tree fails agent-centric names/labels",
        why_it_matters="Agents can't identify interactive elements (fails agentic audit)",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_S05(ctx: CrawlContext) -> Optional[Finding]:
    html = ctx.rendered_html or ctx.raw_html
    if not html:
        return None

    issues = []
    for el in _best_tree(ctx).css("button, a"):
        if el.tag == "a" and "href" not in el.attributes:
            continue

        text = el.text(strip=True)
        aria_label = (el.attributes.get("aria-label") or "").strip()
        aria_labelledby = (el.attributes.get("aria-labelledby") or "").strip()
        title = (el.attributes.get("title") or "").strip()

        if not (text or aria_label or aria_labelledby or title):
            issues.append(el.html[:100])

    if issues:
        return Finding(
            check_id="S05",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"elements": issues[:5]},
            why_it_matters="Agents can't identify interactive elements (fails agentic audit)",  # noqa: E501
            recommended_fix="Provide text content or aria-label for interactive elements.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="S06",
        domain="Agentic-web experience (Lighthouse 13.3 Agentic Browsing + beyond)",
        title="Accessibility tree integrity fail (roles/relationships)",
        description="Detects: Accessibility tree integrity fail (roles/relationships)",
        why_it_matters="Agents misread page structure",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_S06(ctx: CrawlContext) -> Optional[Finding]:
    html = ctx.rendered_html or ctx.raw_html
    if not html:
        return None

    issues = []
    for el in _best_tree(ctx).css('[role="listitem"]'):
        found = False
        parent = el.parent
        while parent is not None:
            if parent.attributes.get("role") == "list" or parent.tag in ("ul", "ol"):
                found = True
                break
            parent = parent.parent
        if not found:
            issues.append(el.html[:100])

    if issues:
        return Finding(
            check_id="S06",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"elements": issues[:5]},
            why_it_matters="Agents misread page structure",
            recommended_fix="Ensure proper ARIA role nesting.",
        )
    return None


@register(
    CheckSpec(
        check_id="S07",
        domain="Agentic-web experience (Lighthouse 13.3 Agentic Browsing + beyond)",
        title="Interactive-but-invisible-to-a11y-tree elements",
        description="Detects: Interactive-but-invisible-to-a11y-tree elements",
        why_it_matters="Agent can't act on them",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_S07(ctx: CrawlContext) -> Optional[Finding]:
    html = ctx.rendered_html or ctx.raw_html
    if not html:
        return None

    issues = []
    for el in _best_tree(ctx).css("button, a, input, select, textarea"):
        hidden = False
        current: Any = el
        while current is not None:
            if current.attributes.get("aria-hidden") == "true":
                hidden = True
                break
            current = current.parent

        if hidden:
            if el.tag == "input" and el.attributes.get("type") == "hidden":
                continue
            issues.append(el.html[:100])

    if issues:
        return Finding(
            check_id="S07",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"elements": issues[:5]},
            why_it_matters="Agent can't act on them",
            recommended_fix="Remove aria-hidden from interactive elements or make them non-interactive.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="S08",
        domain="Agentic-web experience (Lighthouse 13.3 Agentic Browsing + beyond)",
        title="**Post-load CLS** (menus/late banners shift after settle)",
        description="Detects: **Post-load CLS** (menus/late banners shift after settle)",  # noqa: E501
        why_it_matters="Agent clicks stale coordinates → task fails; lab CLS misses this",  # noqa: E501
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_S08(ctx: CrawlContext) -> Optional[Finding]:
    ac = getattr(ctx.url_row, "agentic_context", None) if ctx.url_row else None
    cls = getattr(ac, "post_load_cls", None) if ac else None
    if cls is not None and cls > 0.10:
        return Finding(
            check_id="S08",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"post_load_cls": round(cls, 3)},
            why_it_matters="Agent clicks stale coordinates → task fails; lab CLS misses this",  # noqa: E501
            recommended_fix="Stabilize late-shifting menus/banners after load settles.",
        )
    return None


@register(
    CheckSpec(
        check_id="S09",
        domain="Agentic-web experience (Lighthouse 13.3 Agentic Browsing + beyond)",
        title="Forms lack WebMCP declarative annotations",
        description="Detects: Forms lack WebMCP declarative annotations",
        why_it_matters="Agents parse pixels instead of calling tools",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_S09(ctx: CrawlContext) -> Optional[Finding]:
    html = ctx.rendered_html or ctx.raw_html
    if not html:
        return None

    forms = _best_tree(ctx).css("form")

    if not forms:
        return None

    for form in forms:
        has_mcp = any(attr.startswith("data-mcp") for attr in form.attributes)
        if not has_mcp:
            return Finding(
                check_id="S09",
                severity="Low",
                tier="REVIEW",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"form_action": form.attributes.get("action")},
                why_it_matters="Agents parse pixels instead of calling tools",
                recommended_fix="Add WebMCP declarative data attributes to forms.",
            )
    return None


@register(
    CheckSpec(
        check_id="S10",
        domain="Agentic-web experience (Lighthouse 13.3 Agentic Browsing + beyond)",
        title="WebMCP tool schema invalid / incomplete (if registered)",
        description="Detects: WebMCP tool schema invalid / incomplete (if registered)",
        why_it_matters="Registered tools unusable by agents",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_S10(ctx: CrawlContext) -> Optional[Finding]:
    html = ctx.rendered_html or ctx.raw_html
    if not html:
        return None

    issues = []
    for el in _best_tree(ctx).css("[data-mcp]"):
        data_mcp = el.attributes.get("data-mcp")
        try:
            if data_mcp:
                json.loads(data_mcp)
        except json.JSONDecodeError:
            issues.append(el.html[:100])

    if issues:
        return Finding(
            check_id="S10",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"elements": issues[:5]},
            why_it_matters="Registered tools unusable by agents",
            recommended_fix="Ensure data-mcp attributes contain valid JSON.",
        )
    return None


@register(
    CheckSpec(
        check_id="S11",
        domain="Agentic-web experience (Lighthouse 13.3 Agentic Browsing + beyond)",
        title="Key flows (checkout/booking/contact) not agent-completable",
        description="Detects: Key flows (checkout/booking/contact) not agent-completable",  # noqa: E501
        why_it_matters="AI-visibility leakage on money actions",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_S11(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None
    text = (ctx.url + " " + (ctx.title or "")).lower()
    key_flow = any(k in text for k in (
        "checkout", "cart", "booking", "book-now", "contact", "appointment",
        "register", "signup", "sign-up", "quote",
    ))
    forms = _best_tree(ctx).css("form")
    if forms and key_flow:
        annotated = any("data-mcp" in f.attributes for f in forms)
        if not annotated:
            return Finding(
                check_id="S11",
                severity="Medium",
                tier="REVIEW",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"key_flow_form": True, "webmcp": False},
                why_it_matters="AI-visibility leakage on money actions",
                recommended_fix="Annotate key-flow forms (checkout/booking/contact) for agent completion.",  # noqa: E501
            )
    return None


@register(
    CheckSpec(
        check_id="S12",
        domain="Agentic-web experience (Lighthouse 13.3 Agentic Browsing + beyond)",
        title="Dynamic JS tool/element registration timing issues",
        description="Detects: Dynamic JS tool/element registration timing issues",
        why_it_matters="Agents miss elements during snapshot",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_S12(ctx: CrawlContext) -> Optional[Finding]:
    # Interactive content injected only by JS (render diff) can be missed by an
    # agent snapshotting the page before hydration completes.
    diff = {d.element: d.state for d in (getattr(ctx, "render_diffs", None) or [])}
    if diff.get("internal_links") in ("created", "modified"):
        return Finding(
            check_id="S12",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"js_added_links": diff.get("internal_links")},
            why_it_matters="Agents miss elements during snapshot",
            recommended_fix="Register interactive elements/links server-side or early in load.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="S13",
        domain="Agentic-web experience (Lighthouse 13.3 Agentic Browsing + beyond)",
        title="No AI-assistant traffic channel/attribution set up (GA4)",
        description="Detects: No AI-assistant traffic channel/attribution set up (GA4)",
        why_it_matters="Can't measure agentic/AI referral traffic",
        default_severity="Info",
        fix_tier="FLAG",
        data_source="X",
        fix_template=None,
    )
)
def check_S13(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None
    has_ga4 = bool(
        re.search(r"G-[A-Z0-9]{6,}", ctx.raw_html)
        or "googletagmanager.com/gtag" in ctx.raw_html
    )
    if has_ga4:
        return Finding(
            check_id="S13",
            severity="Info",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"ga4_present": True},
            why_it_matters="Can't measure agentic/AI referral traffic",
            recommended_fix="Add a GA4 channel/segment for AI-assistant referral traffic.",  # noqa: E501
        )
    return None
