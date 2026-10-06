from typing import Optional

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


@register(
    CheckSpec(
        check_id="N01",
        domain="Performance / Core Web Vitals",
        title="LCP > 2.5s (good) / > 4s (poor)",
        description="Detects: LCP > 2.5s (good) / > 4s (poor)",
        why_it_matters="Slow perceived load; CWV",
        default_severity="High",
        fix_tier="FLAG",
        data_source="X",
        fix_template=None,
    )
)
def check_N01(ctx: CrawlContext) -> Optional[Finding]:
    lcp = getattr(ctx.url_row, "lcp_s", None) if ctx.url_row else None
    if lcp is None or lcp <= 2.5:  # good (needs a JS-render crawl to have data)
        return None
    return Finding(
        check_id="N01",
        severity="High" if lcp > 4.0 else "Medium",
        tier="FLAG",
        affected_urls=[ctx.url],
        wp_object_map={},
        evidence={"lcp_s": round(lcp, 2)},
        why_it_matters="Slow perceived load; Core Web Vital",
        recommended_fix="Optimize the LCP element (image, hosting, render-blocking).",
    )


@register(
    CheckSpec(
        check_id="N02",
        domain="Performance / Core Web Vitals",
        title="INP > 200ms (good) / > 500ms (poor)",
        description="Detects: INP > 200ms (good) / > 500ms (poor)",
        why_it_matters="Poor interactivity (replaced FID Mar-2024)",
        default_severity="High",
        fix_tier="FLAG",
        data_source="X",
        fix_template=None,
    )
)
def check_N02(ctx: CrawlContext) -> Optional[Finding]:
    # INP is field-only (real-user data via PSI/CrUX); fires only when present.
    inp = getattr(ctx.url_row, "inp_ms", None) if ctx.url_row else None
    if inp is None or inp <= 200:
        return None
    return Finding(
        check_id="N02",
        severity="High" if inp > 500 else "Medium",
        tier="FLAG",
        affected_urls=[ctx.url],
        wp_object_map={},
        evidence={"inp_ms": round(inp)},
        why_it_matters="Poor interactivity (replaced FID Mar-2024)",
        recommended_fix="Reduce main-thread work / long tasks; break up heavy JS.",
    )


@register(
    CheckSpec(
        check_id="N03",
        domain="Performance / Core Web Vitals",
        title="CLS > 0.1 (good) / > 0.25 (poor)",
        description="Detects: CLS > 0.1 (good) / > 0.25 (poor)",
        why_it_matters="Layout instability; also agentic-critical",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="X",
        fix_template=None,
    )
)
def check_N03(ctx: CrawlContext) -> Optional[Finding]:
    cls = getattr(ctx.url_row, "cls", None) if ctx.url_row else None
    if cls is None or cls <= 0.10:  # good
        return None
    return Finding(
        check_id="N03",
        severity="High" if cls > 0.25 else "Medium",
        tier="REVIEW",
        affected_urls=[ctx.url],
        wp_object_map={},
        evidence={"cls": round(cls, 3)},
        why_it_matters="Layout instability; also agentic-critical",
        recommended_fix="Set width/height on media, reserve space for late content.",
    )


@register(
    CheckSpec(
        check_id="N04",
        domain="Performance / Core Web Vitals",
        title="TTFB slow (>~0.8s)",
        description="Detects: TTFB slow (>~0.8s)",
        why_it_matters="Server/host bottleneck",
        default_severity="Medium",
        fix_tier="FLAG",
        data_source="Hd",
        fix_template=None,
    )
)
def check_N04(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and getattr(ctx.url_row, "ttfb", 0) > 0.8:
        return Finding(
            check_id="N04",
            severity="Medium",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"ttfb": getattr(ctx.url_row, "ttfb", 0)},
            why_it_matters="Server/host bottleneck",
            recommended_fix="Investigate server performance or caching.",
        )
    return None


@register(
    CheckSpec(
        check_id="N05",
        domain="Performance / Core Web Vitals",
        title="Render-blocking CSS/JS",
        description="Detects: Render-blocking CSS/JS",
        why_it_matters="Delays first paint",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_N05(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None

    tree = ctx.dom()
    blocking_assets = []

    for link in tree.css('link[rel="stylesheet"]'):
        media = (link.attributes.get("media") or "").lower()
        if "print" not in media and "max-width" not in media:
            blocking_assets.append(link.attributes.get("href") or "")

    head = tree.css_first("head")
    if head:
        for script in head.css("script"):
            src = script.attributes.get("src")
            if src and "async" not in script.attributes and "defer" not in script.attributes:  # noqa: E501
                blocking_assets.append(src)

    blocking_assets = [a for a in blocking_assets if a]
    if blocking_assets:
        return Finding(
            check_id="N05",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"blocking_assets": blocking_assets[:10]},
            why_it_matters="Delays first paint",
            recommended_fix="Add async/defer to scripts, inline critical CSS.",
        )
    return None


@register(
    CheckSpec(
        check_id="N06",
        domain="Performance / Core Web Vitals",
        title="Unminified CSS/JS",
        description="Detects: Unminified CSS/JS",
        why_it_matters="Wasted bytes",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_N06(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None
    unmin = []
    for el in ctx.dom().css('link[rel="stylesheet"][href], script[src]'):
        src = (el.attributes.get("href") or el.attributes.get("src") or "").lower()
        if src.endswith((".css", ".js")) and ".min." not in src:
            unmin.append(src)
    if len(unmin) >= 3:
        return Finding(
            check_id="N06",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"unminified_assets": unmin[:5]},
            why_it_matters="Wasted bytes",
            recommended_fix="Minify CSS/JS (e.g. a WP caching/optimization plugin).",
        )
    return None


@register(
    CheckSpec(
        check_id="N07",
        domain="Performance / Core Web Vitals",
        title="No compression (gzip/brotli)",
        description="Detects: No compression (gzip/brotli)",
        why_it_matters="Wasted bytes",
        default_severity="Medium",
        fix_tier="FLAG",
        data_source="Hd",
        fix_template=None,
    )
)
def check_N07(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.url_row:
        return None
    headers = {k.lower() for k in (getattr(ctx.url_row, "headers", {}) or {})}
    if "content-encoding" not in headers and (getattr(ctx.url_row, "size", 0) or 0) > 5000:
        return Finding(
            check_id="N07",
            severity="Medium",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"content_encoding": "none"},
            why_it_matters="Wasted bytes",
            recommended_fix="Enable gzip/brotli compression on the server/CDN.",
        )
    return None


@register(
    CheckSpec(
        check_id="N08",
        domain="Performance / Core Web Vitals",
        title="No/short cache headers on static assets",
        description="Detects: No/short cache headers on static assets",
        why_it_matters="Repeat-visit speed",
        default_severity="Low",
        fix_tier="FLAG",
        data_source="Hd",
        fix_template=None,
    )
)
def check_N08(ctx: CrawlContext) -> Optional[Finding]:
    # Heuristic: a page that references many static assets but sets no caching
    # directives at all suggests the server isn't configuring asset caching.
    if not ctx.raw_html or not ctx.url_row:
        return None
    headers = {k.lower() for k in (getattr(ctx.url_row, "headers", {}) or {})}
    if "cache-control" in headers or "expires" in headers:
        return None
    static = len(ctx.dom().css('link[rel="stylesheet"][href], script[src], img[src]'))
    if static >= 5:
        return Finding(
            check_id="N08",
            severity="Low",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"cache_headers": "none", "static_assets": static},
            why_it_matters="Repeat-visit speed",
            recommended_fix="Set long-lived Cache-Control/Expires on static assets.",
        )
    return None


@register(
    CheckSpec(
        check_id="N09",
        domain="Performance / Core Web Vitals",
        title="Excessive DOM size (agentic + perf)",
        description="Detects: Excessive DOM size (agentic + perf)",
        why_it_matters="Slow render, harder machine parse",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_N09(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None

    total_elements = len(ctx.dom().css("*"))

    if total_elements > 1500:
        return Finding(
            check_id="N09",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"dom_elements_count": total_elements},
            why_it_matters="Slow render, harder machine parse",
            recommended_fix="Reduce DOM complexity.",
        )
    return None


@register(
    CheckSpec(
        check_id="N10",
        domain="Performance / Core Web Vitals",
        title="Large total page weight (>~2–3MB)",
        description="Detects: Large total page weight (>~2–3MB)",
        why_it_matters="Speed",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_N10(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row and getattr(ctx.url_row, "size", 0) > 2_500_000:
        return Finding(
            check_id="N10",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"page_size_bytes": getattr(ctx.url_row, "size", 0)},
            why_it_matters="Speed",
            recommended_fix="Compress images, minify assets, and reduce payload.",
        )
    return None


@register(
    CheckSpec(
        check_id="N11",
        domain="Performance / Core Web Vitals",
        title="Excessive HTTP requests",
        description="Detects: Excessive HTTP requests",
        why_it_matters="Speed",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_N11(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None

    tree = ctx.dom()
    reqs = (
        len(tree.css("img[src]"))
        + len(tree.css("script[src]"))
        + len(tree.css("link[href]"))
    )

    if reqs > 100:
        return Finding(
            check_id="N11",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"estimated_requests": reqs},
            why_it_matters="Speed",
            recommended_fix="Combine files, lazy-load images.",
        )
    return None


@register(
    CheckSpec(
        check_id="N12",
        domain="Performance / Core Web Vitals",
        title="Missing preconnect/preload for critical origins",
        description="Detects: Missing preconnect/preload for critical origins",
        why_it_matters="Speed opportunity",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_N12(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None
    from urllib.parse import urlparse

    tree = ctx.dom()
    has_hint = bool(
        tree.css('link[rel="preconnect"], link[rel="preload"], link[rel="dns-prefetch"]')
    )
    base = urlparse(ctx.url).netloc
    ext_origins = set()
    for el in tree.css("script[src], link[href]"):
        src = el.attributes.get("src") or el.attributes.get("href") or ""
        netloc = urlparse(src).netloc
        if netloc and netloc != base:
            ext_origins.add(netloc)
    if ext_origins and not has_hint:
        return Finding(
            check_id="N12",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"external_origins": sorted(ext_origins)[:5]},
            why_it_matters="Speed opportunity",
            recommended_fix="Add <link rel=preconnect/preload> for critical third-party origins.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="N13",
        domain="Performance / Core Web Vitals",
        title="Font loading causes FOIT/FOUT / no font-display",
        description="Detects: Font loading causes FOIT/FOUT / no font-display",
        why_it_matters="Perceived speed + CLS",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_N13(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None

    tree = ctx.dom()
    font_issues = []

    for link in tree.css("link[href]"):
        href = link.attributes.get("href") or ""
        if "fonts.googleapis.com" in href and "display=swap" not in href.lower():
            font_issues.append(href)

    for style in tree.css("style"):
        content = style.text() or ""
        if "@font-face" in content and "font-display" not in content:
            font_issues.append("Inline @font-face without font-display")

    if font_issues:
        return Finding(
            check_id="N13",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"font_issues": font_issues[:5]},
            why_it_matters="Perceived speed + CLS",
            recommended_fix="Use font-display: swap.",
        )
    return None


@register(
    CheckSpec(
        check_id="N14",
        domain="Performance / Core Web Vitals",
        title="Third-party script bloat (analytics/chat/ads)",
        description="Detects: Third-party script bloat (analytics/chat/ads)",
        why_it_matters="Main-thread blocking",
        default_severity="Medium",
        fix_tier="FLAG",
        data_source="R",
        fix_template=None,
    )
)
def check_N14(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None

    third_party_scripts = []

    bloat_domains = [
        "google-analytics.com",
        "googletagmanager.com",
        "hotjar.com",
        "facebook.net",
        "tiktok.com",
        "clarity.ms",
    ]

    for script in ctx.dom().css("script[src]"):
        src = (script.attributes.get("src") or "").lower()
        if any(d in src for d in bloat_domains):
            third_party_scripts.append(src)

    if len(third_party_scripts) >= 3:
        return Finding(
            check_id="N14",
            severity="Medium",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"third_party_scripts": third_party_scripts},
            why_it_matters="Main-thread blocking",
            recommended_fix="Defer third-party scripts.",
        )
    return None
