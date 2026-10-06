"""Tech-stack fingerprinting.

Given a page's URL, response headers and HTML, infer the CMS / framework / stack
so Scrawly can auto-apply the matching crawl preset (see ``crawl.presets``). The
matcher is a weighted signal engine (Wappalyzer-style but focused on the stacks
Scrawly ships presets for) — every stack contributes header, cookie, HTML and
``<meta generator>`` signals; the highest-scoring stack wins, and a normalized
confidence plus the list of matched signals is returned for transparency.

Pure and dependency-light: :func:`detect_from_response` does the reasoning on
already-fetched bytes (unit-testable, no I/O); :func:`detect_stack` is the async
convenience that fetches the homepage first.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Each stack maps to the preset key of the same name in ``crawl.presets``.
# A signal is (weight, kind, needle) where kind selects where we look. ``needle``
# is a lowercase substring except for kind="re" (a compiled-at-use regex on the
# original-case HTML) — some markers (``__NEXT_DATA__``) are case-sensitive.
_HTML = "html"        # lowercased HTML body
_HTML_RE = "re"       # regex against original-case HTML
_HEADER = "header"    # "name: substring" against lowercased response headers
_COOKIE = "cookie"    # substring against the Set-Cookie header(s)
_GEN = "gen"          # substring against the <meta name=generator> content

_SIGNALS: dict[str, list[tuple[int, str, str]]] = {
    "wordpress": [
        (5, _HTML, "/wp-content/"),
        (4, _HTML, "/wp-includes/"),
        (5, _HTML, "/wp-json"),
        (3, _HTML, "wp-emoji"),
        (4, _HTML, "api.w.org"),
        (3, _HEADER, "x-pingback:"),
        (5, _GEN, "wordpress"),
    ],
    "shopify": [
        (6, _HEADER, "x-shopify-stage:"),
        (6, _HEADER, "x-shopid:"),
        (5, _HEADER, "x-shardid:"),
        (5, _HTML, "cdn.shopify.com"),
        (4, _HTML, "shopify.theme"),
        (5, _HTML, "myshopify.com"),
        (4, _HTML, "/cdn/shop/"),
    ],
    "wix": [
        (6, _HEADER, "x-wix-request-id:"),
        (5, _HTML, "static.wixstatic.com"),
        (4, _HTML, "wix.com"),
        (4, _HTML, "_wixcssstates"),
        (5, _GEN, "wix.com"),
    ],
    "squarespace": [
        (5, _HTML, "static1.squarespace.com"),
        (5, _HTML, "squarespace-cdn.com"),
        (4, _HTML, "squarespace.com"),
        (6, _GEN, "squarespace"),
        (4, _HEADER, "x-servedby:"),
    ],
    "webflow": [
        (5, _HTML, "assets.website-files.com"),
        (5, _HTML, "assets-global.website-files.com"),
        (4, _HTML, "data-wf-page"),
        (3, _HTML, "webflow.js"),
        (6, _GEN, "webflow"),
    ],
    "framer": [
        (6, _HTML, "framerusercontent.com"),
        (4, _HTML, "framer.com"),
        (4, _HTML_RE, r"__framer"),
        (6, _GEN, "framer"),
    ],
    "nextjs": [
        (6, _HTML_RE, r"__NEXT_DATA__"),
        (5, _HTML, "/_next/static"),
        (4, _HTML, 'id="__next"'),
        (5, _HEADER, "x-powered-by: next.js"),
        (3, _HEADER, "x-nextjs-"),
    ],
    "react": [
        (3, _HTML, "data-reactroot"),
        (3, _HTML_RE, r"react(?:-dom)?(?:\.production)?\.min\.js"),
        (2, _HTML_RE, r"__reactContainer"),
    ],
    "laravel": [
        (6, _COOKIE, "laravel_session"),
        (4, _COOKIE, "xsrf-token"),
        (3, _HEADER, "x-powered-by: php"),
    ],
    "drupal": [
        (5, _HTML_RE, r"Drupal\.settings"),
        (4, _HTML, "/sites/default/files"),
        (4, _HTML, "/sites/all/"),
        (3, _HTML, "data-drupal"),
        (6, _HEADER, "x-generator: drupal"),
        (6, _GEN, "drupal"),
    ],
    "joomla": [
        (5, _HTML, "/media/jui/"),
        (4, _HTML, "/media/system/js/"),
        (4, _HTML, "option=com_"),
        (6, _GEN, "joomla"),
    ],
    "magento": [
        (5, _HTML, "/static/version"),
        (4, _HTML, "/mage/"),
        (4, _HTML_RE, r"Magento_"),
        (5, _COOKIE, "x-magento"),
        (5, _HEADER, "x-magento-"),
    ],
    "ghost": [
        (6, _GEN, "ghost"),
        (4, _HTML, "/content/images/"),
        (3, _HTML, "ghost-"),
        (4, _HTML_RE, r'name="generator" content="Ghost'),
    ],
}

# Sub-category detection: only WordPress ships sub-types today; WooCommerce is the
# one reliably fingerprintable from the front end.
_SUBCATEGORY_SIGNALS: dict[str, dict[str, list[tuple[int, str, str]]]] = {
    "wordpress": {
        "woocommerce": [
            (5, _HTML, "/plugins/woocommerce/"),
            (4, _HTML, "woocommerce-"),
            (3, _HTML, "wc-block"),
            (3, _HTML, "add-to-cart"),
        ],
    },
}

_GENERATOR_RE = re.compile(
    r"<meta[^>]+name=[\"']generator[\"'][^>]+content=[\"']([^\"']+)[\"']",
    re.I,
)


@dataclass
class DetectionResult:
    """Outcome of fingerprinting a single page."""

    stack: str = "generic"
    subcategory: str = ""
    confidence: float = 0.0
    signals: list[str] = field(default_factory=list)
    generator: str = ""
    server: str = ""
    powered_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "stack": self.stack,
            "subcategory": self.subcategory,
            "confidence": round(self.confidence, 2),
            "signals": self.signals,
            "generator": self.generator,
            "server": self.server,
            "powered_by": self.powered_by,
        }


def _match(kind: str, needle: str, html_lc: str, html: str, headers_blob: str,
           cookie_blob: str, generator_lc: str) -> bool:
    if kind == _HTML:
        return needle in html_lc
    if kind == _HTML_RE:
        return re.search(needle, html) is not None
    if kind == _HEADER:
        return needle in headers_blob
    if kind == _COOKIE:
        return needle in cookie_blob
    if kind == _GEN:
        return needle in generator_lc
    return False


def detect_from_response(
    url: str,
    headers: dict[str, str] | None,
    html: str,
) -> DetectionResult:
    """Fingerprint a stack from an already-fetched response. Pure, no I/O."""
    headers = headers or {}
    html = html or ""
    html_lc = html.lower()
    # Fold headers into a single lowercase "name: value\n" blob for substring rules.
    lc_headers = {str(k).lower(): str(v) for k, v in headers.items()}
    headers_blob = "\n".join(f"{k}: {v.lower()}" for k, v in lc_headers.items())
    cookie_blob = lc_headers.get("set-cookie", "").lower()
    gen_match = _GENERATOR_RE.search(html)
    generator = gen_match.group(1).strip() if gen_match else ""
    generator_lc = generator.lower()

    best_stack = "generic"
    best_score = 0
    best_signals: list[str] = []
    best_max = 1
    for stack, sigs in _SIGNALS.items():
        score = 0
        matched: list[str] = []
        for weight, kind, needle in sigs:
            if _match(kind, needle, html_lc, html, headers_blob, cookie_blob, generator_lc):
                score += weight
                matched.append(needle)
        if score > best_score:
            best_stack, best_score, best_signals = stack, score, matched
            best_max = sum(w for w, _, _ in sigs)

    # Sub-category (e.g. WordPress -> WooCommerce).
    subcategory = ""
    for sub, sigs in _SUBCATEGORY_SIGNALS.get(best_stack, {}).items():
        if any(
            _match(kind, needle, html_lc, html, headers_blob, cookie_blob, generator_lc)
            for _, kind, needle in sigs
        ):
            subcategory = sub
            break

    # Confidence: matched weight over a soft ceiling (full detection rarely fires
    # every signal, so cap the denominator so a couple of strong signals ~= high).
    confidence = 0.0
    if best_score:
        confidence = min(1.0, best_score / min(best_max, 10))

    return DetectionResult(
        stack=best_stack if best_score else "generic",
        subcategory=subcategory,
        confidence=confidence,
        signals=best_signals,
        generator=generator,
        server=lc_headers.get("server", ""),
        powered_by=lc_headers.get("x-powered-by", ""),
    )


async def detect_stack(
    url: str,
    user_agent: str = "ScrawlyBot/1.0 (+https://scrawly.app)",
    timeout: float = 12.0,
) -> DetectionResult:
    """Fetch ``url`` and fingerprint its stack. Network errors -> generic result."""
    import httpx

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": user_agent},
        ) as client:
            resp = await client.get(url)
            return detect_from_response(str(resp.url), dict(resp.headers), resp.text)
    except Exception:  # noqa: BLE001 - detection is best-effort; never fatal.
        return DetectionResult()
