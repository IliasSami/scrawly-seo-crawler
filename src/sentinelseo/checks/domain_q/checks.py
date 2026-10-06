from typing import Any, Optional

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


def _best_tree(ctx: CrawlContext) -> Any:
    """Parse the rendered DOM if present, else the raw response (cached once)."""
    return ctx.dom(bool(ctx.rendered_html))


@register(
    CheckSpec(
        check_id="Q01",
        domain="Accessibility",
        title="Interactive element missing accessible name/label",
        description="Detects: Interactive element missing accessible name/label",
        why_it_matters="Fails agentic a11y tree + screen readers",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_Q01(ctx: CrawlContext) -> Optional[Finding]:
    if not (ctx.rendered_html or ctx.raw_html):
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
            check_id="Q01",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"elements": issues[:5]},
            why_it_matters="Fails agentic a11y tree + screen readers",
            recommended_fix="Provide text content or aria-label for interactive elements.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="Q02",
        domain="Accessibility",
        title="Invalid/unsupported ARIA attributes",
        description="Detects: Invalid/unsupported ARIA attributes",
        why_it_matters="Breaks a11y tree (fails agentic audit)",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_Q02(ctx: CrawlContext) -> Optional[Finding]:
    if not (ctx.rendered_html or ctx.raw_html):
        return None

    issues = []
    valid_arias = {
        "aria-activedescendant",
        "aria-atomic",
        "aria-autocomplete",
        "aria-busy",
        "aria-checked",
        "aria-colcount",
        "aria-colindex",
        "aria-colspan",
        "aria-controls",
        "aria-current",
        "aria-describedby",
        "aria-details",
        "aria-disabled",
        "aria-dropeffect",
        "aria-errormessage",
        "aria-expanded",
        "aria-flowto",
        "aria-grabbed",
        "aria-haspopup",
        "aria-hidden",
        "aria-invalid",
        "aria-keyshortcuts",
        "aria-label",
        "aria-labelledby",
        "aria-level",
        "aria-live",
        "aria-modal",
        "aria-multiline",
        "aria-multiselectable",
        "aria-orientation",
        "aria-owns",
        "aria-placeholder",
        "aria-posinset",
        "aria-pressed",
        "aria-readonly",
        "aria-relevant",
        "aria-required",
        "aria-roledescription",
        "aria-rowcount",
        "aria-rowindex",
        "aria-rowspan",
        "aria-selected",
        "aria-setsize",
        "aria-sort",
        "aria-valuemax",
        "aria-valuemin",
        "aria-valuenow",
        "aria-valuetext",
    }

    for el in _best_tree(ctx).css("*"):
        for attr in el.attributes:
            if attr.startswith("aria-") and attr not in valid_arias:
                issues.append(f"{attr} on {el.tag}")

    if issues:
        return Finding(
            check_id="Q02",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"invalid_attributes": issues[:5]},
            why_it_matters="Breaks a11y tree (fails agentic audit)",
            recommended_fix="Use valid ARIA attributes.",
        )
    return None


@register(
    CheckSpec(
        check_id="Q03",
        domain="Accessibility",
        title="Form field without associated label",
        description="Detects: Form field without associated label",
        why_it_matters="Agents/screen readers can't operate",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_Q03(ctx: CrawlContext) -> Optional[Finding]:
    if not (ctx.rendered_html or ctx.raw_html):
        return None

    tree = _best_tree(ctx)
    issues = []
    label_fors = {label.attributes.get("for") for label in tree.css("label[for]")}

    for el in tree.css("input, textarea, select"):
        if el.tag == "input" and el.attributes.get("type") in [
            "hidden",
            "submit",
            "button",
            "reset",
            "image",
        ]:
            continue

        has_label = bool(
            el.attributes.get("aria-label")
            or el.attributes.get("aria-labelledby")
            or el.attributes.get("title")
        )

        if not has_label:
            parent = el.parent
            while parent is not None:
                if parent.tag == "label":
                    has_label = True
                    break
                parent = parent.parent

        if not has_label and el.attributes.get("id") in label_fors:
            has_label = True

        if not has_label:
            issues.append(el.html[:100])

    if issues:
        return Finding(
            check_id="Q03",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"elements": issues[:5]},
            why_it_matters="Agents/screen readers can't operate",
            recommended_fix="Add <label> elements or aria-label attributes to form fields.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="Q04",
        domain="Accessibility",
        title="Insufficient color contrast",
        description="Detects: Insufficient color contrast",
        why_it_matters="WCAG fail",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_Q04(ctx: CrawlContext) -> Optional[Finding]:
    # Uses axe-core's computed-contrast result captured during the render pass.
    ac = getattr(ctx.url_row, "agentic_context", None) if ctx.url_row else None
    violations = getattr(ac, "axe_violations", None) if ac else None
    if violations and "color-contrast" in violations:
        return Finding(
            check_id="Q04",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"axe": "color-contrast"},
            why_it_matters="WCAG fail",
            recommended_fix="Increase text/background contrast to meet WCAG AA (4.5:1).",
        )
    return None


@register(
    CheckSpec(
        check_id="Q05",
        domain="Accessibility",
        title="Content interactive but hidden from a11y tree",
        description="Detects: Content interactive but hidden from a11y tree",
        why_it_matters="Agent can't perceive actionable element",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_Q05(ctx: CrawlContext) -> Optional[Finding]:
    if not (ctx.rendered_html or ctx.raw_html):
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
            check_id="Q05",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"elements": issues[:5]},
            why_it_matters="Agent can't perceive actionable element",
            recommended_fix="Remove aria-hidden from interactive elements or make them non-interactive.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="Q06",
        domain="Accessibility",
        title="Improper role/parent-child nesting (tree integrity)",
        description="Detects: Improper role/parent-child nesting (tree integrity)",
        why_it_matters="Machine misreads structure",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_Q06(ctx: CrawlContext) -> Optional[Finding]:
    if not (ctx.rendered_html or ctx.raw_html):
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
            check_id="Q06",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"elements": issues[:5]},
            why_it_matters="Machine misreads structure",
            recommended_fix="Ensure proper ARIA role nesting.",
        )
    return None


@register(
    CheckSpec(
        check_id="Q07",
        domain="Accessibility",
        title="Missing document language attribute",
        description="Detects: Missing document language attribute",
        why_it_matters="a11y + international",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_Q07(ctx: CrawlContext) -> Optional[Finding]:
    if not (ctx.rendered_html or ctx.raw_html):
        return None

    html_tag = _best_tree(ctx).css_first("html")

    if html_tag and not html_tag.attributes.get("lang"):
        return Finding(
            check_id="Q07",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={},
            why_it_matters="a11y + international",
            recommended_fix="Add lang attribute to <html> tag.",
        )
    return None


@register(
    CheckSpec(
        check_id="Q08",
        domain="Accessibility",
        title="Non-semantic markup for interactive controls (div-as-button)",
        description="Detects: Non-semantic markup for interactive controls (div-as-button)",  # noqa: E501
        why_it_matters="Agents/AT can't identify actions",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_Q08(ctx: CrawlContext) -> Optional[Finding]:
    if not (ctx.rendered_html or ctx.raw_html):
        return None

    issues = []
    for el in _best_tree(ctx).css("div, span"):
        if "onclick" in el.attributes and el.attributes.get("role") != "button":
            issues.append(el.html[:100])

    if issues:
        return Finding(
            check_id="Q08",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"elements": issues[:5]},
            why_it_matters="Agents/AT can't identify actions",
            recommended_fix="Use <button> for interactive elements or add role='button' and tabindex.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="Q09",
        domain="Accessibility",
        title="Missing skip links / landmark regions",
        description="Detects: Missing skip links / landmark regions",
        why_it_matters="Navigation structure",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_Q09(ctx: CrawlContext) -> Optional[Finding]:
    if not (ctx.rendered_html or ctx.raw_html):
        return None

    tree = _best_tree(ctx)
    has_main = tree.css_first("main") or tree.css_first('[role="main"]')
    has_nav = tree.css_first("nav") or tree.css_first('[role="navigation"]')

    if not has_main and not has_nav:
        return Finding(
            check_id="Q09",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={},
            why_it_matters="Navigation structure",
            recommended_fix="Add semantic landmark regions like <main> and <nav>.",
        )
    return None
