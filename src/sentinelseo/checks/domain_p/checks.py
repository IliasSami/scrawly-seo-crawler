from typing import Any, Optional
from urllib.parse import urlparse

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


def _meta_content(tree: Any, name: str) -> Optional[str]:
    for m in tree.css("meta"):
        if (m.attributes.get("name") or "").lower() == name:
            content = m.attributes.get("content")
            return None if content is None else str(content)
    return None


def _canonical(tree: Any) -> Optional[str]:
    node = tree.css_first('link[rel="canonical"]')
    return node.attributes.get("href") if node else None


def _title(tree: Any) -> Optional[str]:
    node = tree.css_first("title")
    return (node.text(strip=True) or None) if node else None


@register(
    CheckSpec(
        check_id="P01",
        domain="JavaScript rendering (response vs render)",
        title="Primary content only in rendered DOM (not in response HTML)",
        description="Detects: Primary content only in rendered DOM (not in response HTML)",  # noqa: E501
        why_it_matters="AI crawlers (no JS) miss it; Google delay",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_P01(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html or not ctx.rendered_html:
        return None

    raw_body = ctx.dom().css_first("body")
    render_body = ctx.dom(use_rendered=True).css_first("body")

    raw_text = raw_body.text(separator=" ", strip=True) if raw_body else ""
    render_text = render_body.text(separator=" ", strip=True) if render_body else ""

    if len(raw_text) < 200 and len(render_text) > 500:
        return Finding(
            check_id="P01",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={
                "raw_body_length": len(raw_text),
                "rendered_body_length": len(render_text),
            },
            why_it_matters="AI crawlers (no JS) miss it; Google delay",
            recommended_fix="Implement SSR or prerendering so primary content is in the raw HTML response.",  # noqa: E501
        )

    return None


@register(
    CheckSpec(
        check_id="P02",
        domain="JavaScript rendering (response vs render)",
        title="Internal links injected only by JS",
        description="Detects: Internal links injected only by JS",
        why_it_matters="Discovery via render only",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_P02(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html or not ctx.rendered_html:
        return None

    raw_links = {
        a.attributes.get("href") for a in ctx.dom().css("a[href]")
        if a.attributes.get("href")
    }
    render_links = {
        a.attributes.get("href") for a in ctx.dom(use_rendered=True).css("a[href]")
        if a.attributes.get("href")
    }

    added_links = render_links - raw_links
    if not added_links:
        return None

    domain = urlparse(ctx.url).netloc

    internal_added = []
    for link in added_links:
        parsed = urlparse(str(link))
        if str(link).startswith("/") or parsed.netloc == domain:
            internal_added.append(str(link))

    if internal_added:
        return Finding(
            check_id="P02",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"injected_internal_links": sorted(internal_added)[:10]},
            why_it_matters="Discovery via render only",
            recommended_fix="Include internal links in the raw HTML response for better crawler discovery.",  # noqa: E501
        )

    return None


@register(
    CheckSpec(
        check_id="P03",
        domain="JavaScript rendering (response vs render)",
        title="Title/meta/canonical/robots differ response vs render",
        description="Detects: Title/meta/canonical/robots differ response vs render",
        why_it_matters="Indexing ambiguity",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_P03(ctx: CrawlContext) -> Optional[Finding]:  # noqa: C901
    if not ctx.raw_html or not ctx.rendered_html:
        return None

    raw_tree = ctx.dom()
    render_tree = ctx.dom(use_rendered=True)

    raw_title = _title(raw_tree)
    render_title = _title(render_tree)

    raw_meta_desc = _meta_content(raw_tree, "description")
    render_meta_desc = _meta_content(render_tree, "description")

    raw_robots = _meta_content(raw_tree, "robots")
    render_robots = _meta_content(render_tree, "robots")

    raw_canonical = _canonical(raw_tree)
    render_canonical = _canonical(render_tree)

    diffs = {}
    if raw_title != render_title:
        diffs["title"] = {"raw": raw_title, "rendered": render_title}
    if raw_meta_desc != render_meta_desc:
        diffs["meta_description"] = {"raw": raw_meta_desc, "rendered": render_meta_desc}
    if raw_robots != render_robots:
        diffs["robots"] = {"raw": raw_robots, "rendered": render_robots}
    if raw_canonical != render_canonical:
        diffs["canonical"] = {"raw": raw_canonical, "rendered": render_canonical}

    if diffs:
        return Finding(
            check_id="P03",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"diffs": diffs},
            why_it_matters="Indexing ambiguity",
            recommended_fix="Ensure title, meta description, robots, and canonical tags match exactly between raw and rendered HTML.",  # noqa: E501
        )

    return None


@register(
    CheckSpec(
        check_id="P04",
        domain="JavaScript rendering (response vs render)",
        title="Render blocked by JS error / failed resource",
        description="Detects: Render blocked by JS error / failed resource",
        why_it_matters="Blank/partial render",
        default_severity="High",
        fix_tier="FLAG",
        data_source="R",
        fix_template=None,
    )
)
def check_P04(ctx: CrawlContext) -> Optional[Finding]:
    ac = getattr(ctx.url_row, "agentic_context", None) if ctx.url_row else None
    errors = getattr(ac, "js_errors", None) if ac else None
    if errors:
        return Finding(
            check_id="P04",
            severity="High",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"js_errors": errors[:3]},
            why_it_matters="Blank/partial render",
            recommended_fix="Fix the JavaScript errors preventing a clean render.",
        )
    return None


@register(
    CheckSpec(
        check_id="P05",
        domain="JavaScript rendering (response vs render)",
        title="Long render/hydration time",
        description="Detects: Long render/hydration time",
        why_it_matters="Slow indexing + agentic latency",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_P05(ctx: CrawlContext) -> Optional[Finding]:
    render_ms = getattr(ctx.url_row, "render_ms", None) if ctx.url_row else None
    if render_ms is not None and render_ms > 3000:
        return Finding(
            check_id="P05",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"render_ms": round(render_ms)},
            why_it_matters="Slow indexing + agentic latency",
            recommended_fix="Reduce hydration/render time (code-split, defer non-critical JS).",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="P06",
        domain="JavaScript rendering (response vs render)",
        title="Client-side-only routing without SSR/prerender",
        description="Detects: Client-side-only routing without SSR/prerender",
        why_it_matters="Whole-site render dependency",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_P06(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html or not ctx.rendered_html:
        return None
    raw_body = ctx.dom().css_first("body")
    ren_body = ctx.dom(use_rendered=True).css_first("body")
    raw_text = raw_body.text(strip=True) if raw_body else ""
    ren_text = ren_body.text(strip=True) if ren_body else ""
    spa_root = ctx.dom().css_first("#root, #app, [ng-app], [data-reactroot]")
    if spa_root is not None and len(raw_text) < 200 and len(ren_text) > 500:
        return Finding(
            check_id="P06",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"raw_len": len(raw_text), "rendered_len": len(ren_text)},
            why_it_matters="Whole-site render dependency",
            recommended_fix="Add SSR/prerendering so content is present in the response HTML.",  # noqa: E501
        )
    return None
