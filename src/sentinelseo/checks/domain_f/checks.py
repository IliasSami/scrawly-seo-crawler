# ruff: noqa: E741
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register

# -- Helper logic to map CrawlContext to the detection logic concepts --

@dataclass
class LinkRef:
    href: str
    anchor: str
    rel: tuple[str, ...]
    is_internal: bool

def _extract_links(ctx: CrawlContext) -> list[LinkRef]:
    if not ctx.raw_html:
        return []
    base_domain = urlparse(ctx.url).netloc
    links = []
    for a in ctx.dom().css("a"):
        href = a.attributes.get("href")
        if not href:
            continue
        href_parsed = urlparse(href)
        is_internal = not href_parsed.netloc or href_parsed.netloc == base_domain

        # Get anchor text (including image alt)
        text = a.text(strip=True)
        if not text:
            for img in a.css("img"):
                alt = img.attributes.get("alt")
                if alt and alt.strip():
                    text = alt.strip()
                    break

        rel_attr = a.attributes.get("rel") or ""
        rel = tuple(r.lower() for r in rel_attr.split())

        links.append(LinkRef(href=href.strip(), anchor=text, rel=rel, is_internal=is_internal))  # noqa: E501
    return links

def _get_render_diff(ctx: CrawlContext) -> dict[str, str]:
    if hasattr(ctx, "render_diffs") and ctx.render_diffs:
        return {d.element: d.state for d in ctx.render_diffs}
    return {}


@register(
    CheckSpec(
        check_id="F01",
        domain="Internal linking & architecture",
        title="Orphan pages (no internal inlinks)",
        description="Detects: Orphan pages (no internal inlinks)",
        why_it_matters="Undiscoverable, low authority",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_F01(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.url_row:
        return None
    # A09 logic: if ctx.status == 200 and ctx.indexable and ctx.inlinks_internal == 0 and ctx.in_sitemap:  # noqa: E501
    # We omit in_sitemap because it's not in url_row, just checking indexable and inlinks == 0  # noqa: E501
    if ctx.url_row.status == 200 and ctx.url_row.indexable and ctx.url_row.inlink_count == 0:  # noqa: E501
        return Finding(
            check_id="F01",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"inlinks": 0},
            why_it_matters="Undiscoverable, low authority",
            recommended_fix="Add relevant internal links pointing to this page."
        )
    return None


@register(
    CheckSpec(
        check_id="F02",
        domain="Internal linking & architecture",
        title="Pages with only 1 internal inlink",
        description="Detects: Pages with only 1 internal inlink",
        why_it_matters="Weak internal authority",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_F02(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.url_row:
        return None
    if ctx.url_row.indexable and ctx.url_row.inlink_count == 1:
        return Finding(
            check_id="F02",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"inlinks": 1},
            why_it_matters="Weak internal authority",
            recommended_fix="Add contextual internal links from related pages."
        )
    return None


@register(
    CheckSpec(
        check_id="F03",
        domain="Internal linking & architecture",
        title="Excessive on-page links (>~100–150)",
        description="Detects: Excessive on-page links (>~100–150)",
        why_it_matters="Equity dilution, crawl noise",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_F03(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.url_row:
        return None
    # site.thresholds.max_links_on_page is default 150
    if ctx.url_row.outlink_count > 150:
        return Finding(
            check_id="F03",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"link_count": ctx.url_row.outlink_count},
            why_it_matters="Equity dilution, crawl noise",
            recommended_fix="Reduce link count; dilution + crawl noise."
        )
    return None


@register(
    CheckSpec(
        check_id="F04",
        domain="Internal linking & architecture",
        title="Deep pages (>3–4 clicks from home)",
        description="Detects: Deep pages (>3–4 clicks from home)",
        why_it_matters="Reduced crawl/rank priority",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_F04(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.url_row:
        return None
    depth = getattr(ctx.url_row, "depth", None)
    # site.thresholds.max_crawl_depth is default 4
    if depth is not None and depth > 4 and ctx.url_row.indexable:
        return Finding(
            check_id="F04",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"depth": depth},
            why_it_matters="Reduced crawl/rank priority",
            recommended_fix="Flatten the path / add contextual internal links."
        )
    return None


@register(
    CheckSpec(
        check_id="F05",
        domain="Internal linking & architecture",
        title="Broken/empty anchor text",
        description="Detects: Broken/empty anchor text",
        why_it_matters="Lost relevance context",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_F05(ctx: CrawlContext) -> Optional[Finding]:
    links = _extract_links(ctx)
    empty = [lnk.href for lnk in links if not (lnk.anchor or "").strip()]
    if empty:
        return Finding(
            check_id="F05",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"targets": empty[:20]},
            why_it_matters="Lost relevance context",
            recommended_fix="Add descriptive anchor text (or alt text if image links)."
        )
    return None


_GENERIC = {"click here", "read more", "here", "more", "link", "this", "learn more", "continue"}  # noqa: E501

@register(
    CheckSpec(
        check_id="F06",
        domain="Internal linking & architecture",
        title='Generic anchors ("click here", "read more") at scale',
        description='Detects: Generic anchors ("click here", "read more") at scale',
        why_it_matters="Weak topical signal",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_F06(ctx: CrawlContext) -> Optional[Finding]:
    links = _extract_links(ctx)
    gen = [lnk.href for lnk in links if (lnk.anchor or "").strip().lower() in _GENERIC]
    if len(gen) >= 5:
        return Finding(
            check_id="F06",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"count": len(gen)},
            why_it_matters="Weak topical signal",
            recommended_fix="Use descriptive, topical anchor text."
        )
    return None


@register(
    CheckSpec(
        check_id="F07",
        domain="Internal linking & architecture",
        title="Internal links to non-canonical / redirected URLs",
        description="Detects: Internal links to non-canonical / redirected URLs",
        why_it_matters="Equity misdirected",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_F07(ctx: CrawlContext) -> Optional[Finding]:
    # Adaptation without `site.pages`: flip to the receiving end (same as original implementation)  # noqa: E501
    if not ctx.url_row:
        return None
    is_redirect = ctx.url_row.status in (301, 302, 307, 308)
    is_non_canonical = bool(ctx.url_row.canonical and ctx.url_row.canonical != ctx.url_row.address)  # noqa: E501

    if (is_redirect or is_non_canonical) and ctx.url_row.inlink_count > 0:
        return Finding(
            check_id="F07",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"status": ctx.url_row.status, "inlink_count": ctx.url_row.inlink_count},  # noqa: E501
            why_it_matters="Equity misdirected",
            recommended_fix="Link directly to the canonical URL."
        )
    return None


_JS_NAV = re.compile(r'<(?:a|div|span|button)[^>]*(?:onclick=|data-href=|role=["\']link["\'])[^>]*>', re.I)  # noqa: E501

@register(
    CheckSpec(
        check_id="F08",
        domain="Internal linking & architecture",
        title="Uncrawlable links (JS onclick, buttons, no `href`)",
        description="Detects: Uncrawlable links (JS onclick, buttons, no `href`)",
        why_it_matters="Bots can't follow",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_F08(ctx: CrawlContext) -> Optional[Finding]:
    html = ctx.rendered_html or ctx.raw_html or ""
    hits = len(_JS_NAV.findall(html))
    anchors_no_href = len(re.findall(r'<a(?![^>]*\bhref=)[^>]*>', html, re.I))
    total = hits + anchors_no_href
    if total >= 3:
        return Finding(
            check_id="F08",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"js_nav": hits, "anchors_without_href": anchors_no_href},
            why_it_matters="Bots can't follow",
            recommended_fix="Use <a href> for navigation so crawlers and agents can follow it."
        )
    return None


@register(
    CheckSpec(
        check_id="F09",
        domain="Internal linking & architecture",
        title="Internal `nofollow` sculpting (unintended)",
        description="Detects: Internal `nofollow` sculpting (unintended)",
        why_it_matters="Blocks equity flow",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_F09(ctx: CrawlContext) -> Optional[Finding]:
    links = _extract_links(ctx)
    nofollowed = [lnk.href for lnk in links if lnk.is_internal and 'nofollow' in lnk.rel]
    if nofollowed:
        return Finding(
            check_id="F09",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"targets": nofollowed[:20]},
            why_it_matters="Blocks equity flow",
            recommended_fix="Remove nofollow from internal links you want crawled."
        )
    return None


@register(
    CheckSpec(
        check_id="F10",
        domain="Internal linking & architecture",
        title="Links created/removed only by JS (response vs render)",
        description="Detects: Links created/removed only by JS (response vs render)",
        why_it_matters="Render-dependent discovery",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_F10(ctx: CrawlContext) -> Optional[Finding]:
    render_diff = _get_render_diff(ctx)
    if render_diff.get("internal_links") == "created":
        return Finding(
            check_id="F10",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={},
            why_it_matters="Render-dependent discovery",
            recommended_fix="Emit internal links in the server HTML."
        )
    return None


@register(
    CheckSpec(
        check_id="F11",
        domain="Internal linking & architecture",
        title="No breadcrumb / weak hierarchical linking",
        description="Detects: No breadcrumb / weak hierarchical linking",
        why_it_matters="Structure + rich-result loss",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_F11(ctx: CrawlContext) -> Optional[Finding]:
    jsonld = [
        sd if isinstance(sd, dict) else getattr(sd, "__dict__", {})
        for sd in (getattr(ctx, "structured_data", None) or [])
    ]
    has_bc = any(isinstance(b, dict) and 'BreadcrumbList' in str(b.get("type", "")) for b in jsonld) or bool(re.search(r'(class|aria-label)=["\'][^"\']*breadcrumb', ctx.rendered_html or ctx.raw_html or "", re.I))  # noqa: E501
    depth = (getattr(ctx.url_row, "depth", None) or 0) if ctx.url_row else 0
    if not has_bc and depth >= 2:
        return Finding(
            check_id="F11",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"depth": depth},
            why_it_matters="Structure + rich-result loss",
            recommended_fix="Add breadcrumbs with BreadcrumbList schema."
        )
    return None


@register(
    CheckSpec(
        check_id="F12",
        domain="Internal linking & architecture",
        title="Internal link to HTTP (from HTTPS page)",
        description="Detects: Internal link to HTTP (from HTTPS page)",
        why_it_matters="Mixed-content / insecure hop",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_F12(ctx: CrawlContext) -> Optional[Finding]:
    if urlparse(ctx.url).scheme != "https":
        return None
    links = _extract_links(ctx)
    http_links = [lnk.href for lnk in links if lnk.is_internal and urlparse(lnk.href).scheme == "http"]  # noqa: E501
    if http_links:
        return Finding(
            check_id="F12",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"targets": http_links[:20]},
            why_it_matters="Mixed-content / insecure hop",
            recommended_fix="Update links to https://."
        )
    return None
