import re
from typing import Optional

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


@register(
    CheckSpec(
        check_id="M01",
        domain="Security",
        title="Site not on HTTPS",
        description="Detects: Site not on HTTPS",
        why_it_matters="Ranking + trust + browser warnings",
        default_severity="Critical",
        fix_tier="FLAG",
        data_source="Hd",
        fix_template=None,
    )
)
def check_M01(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url.startswith("http://"):
        return Finding(
            check_id="M01",
            severity="Critical",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"url": ctx.url},
            why_it_matters="Ranking + trust + browser warnings",
            recommended_fix="Migrate to HTTPS.",
        )
    return None


@register(
    CheckSpec(
        check_id="M02",
        domain="Security",
        title="Mixed content (HTTPS page loads HTTP assets)",
        description="Detects: Mixed content (HTTPS page loads HTTP assets)",
        why_it_matters="Security warnings, blocked resources",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_M02(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.url.startswith("https://") or not ctx.raw_html:
        return None
    mixed_assets = []

    tags = {
        "img": "src",
        "script": "src",
        "link": "href",
        "iframe": "src",
        "audio": "src",
        "video": "src",
        "source": "src",
    }

    tree = ctx.dom()
    for tag, attr in tags.items():
        for el in tree.css(tag):
            val = el.attributes.get(attr)
            if val and val.startswith("http://"):
                mixed_assets.append(val)

    if mixed_assets:
        return Finding(
            check_id="M02",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"mixed_assets": mixed_assets[:5]},
            why_it_matters="Security warnings, blocked resources",
            recommended_fix=(
                "Change HTTP asset links to HTTPS or protocol-relative URLs."
            ),
        )
    return None


@register(
    CheckSpec(
        check_id="M03",
        domain="Security",
        title="Missing HSTS header",
        description="Detects: Missing HSTS header",
        why_it_matters="Downgrade-attack window",
        default_severity="Medium",
        fix_tier="FLAG",
        data_source="Hd",
        fix_template=None,
    )
)
def check_M03(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.url.startswith("https://") or not ctx.url_row:
        return None
    headers = {k.lower() for k in (getattr(ctx.url_row, "headers", {}) or {})}
    if "strict-transport-security" not in headers:
        return Finding(
            check_id="M03",
            severity="Medium",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"strict_transport_security": "missing"},
            why_it_matters="Downgrade-attack window",
            recommended_fix="Add a Strict-Transport-Security response header.",
        )
    return None


@register(
    CheckSpec(
        check_id="M04",
        domain="Security",
        title="Expired / invalid / soon-expiring TLS cert",
        description="Detects: Expired / invalid / soon-expiring TLS cert",
        why_it_matters="Access failure risk",
        default_severity="Critical",
        fix_tier="FLAG",
        data_source="Hd",
        fix_template=None,
    )
)
def check_M04(ctx: CrawlContext) -> Optional[Finding]:
    # Intentionally deferred (status: deferred) — inert until its data source is wired.
    return None


@register(
    CheckSpec(
        check_id="M05",
        domain="Security",
        title="Protocol-relative resource links (`//host`)",
        description="Detects: Protocol-relative resource links (`//host`)",
        why_it_matters="Anti-pattern under HTTPS-everywhere",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_M05(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None
    pr_assets = []
    tags = {
        "img": "src",
        "script": "src",
        "link": "href",
        "iframe": "src",
    }
    tree = ctx.dom()
    for tag, attr in tags.items():
        for el in tree.css(tag):
            val = el.attributes.get(attr)
            if val and val.startswith("//"):
                pr_assets.append(val)

    if pr_assets:
        return Finding(
            check_id="M05",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"protocol_relative_assets": pr_assets[:5]},
            why_it_matters="Anti-pattern under HTTPS-everywhere",
            recommended_fix="Update protocol-relative URLs to use absolute HTTPS URLs.",
        )
    return None


@register(
    CheckSpec(
        check_id="M06",
        domain="Security",
        title=(
            "Missing security headers (CSP, X-Content-Type-Options, "
            "X-Frame-Options, Referrer-Policy)"
        ),
        description=(
            "Detects: Missing security headers (CSP, X-Content-Type-Options, "
            "X-Frame-Options, Referrer-Policy)"
        ),
        why_it_matters="Hardening + best-practice audit",
        default_severity="Low",
        fix_tier="FLAG",
        data_source="Hd",
        fix_template=None,
    )
)
def check_M06(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.url_row:
        return None
    headers = {k.lower() for k in (getattr(ctx.url_row, "headers", {}) or {})}
    want = {
        "content-security-policy",
        "x-content-type-options",
        "x-frame-options",
        "referrer-policy",
    }
    missing = sorted(want - headers)
    if missing:
        return Finding(
            check_id="M06",
            severity="Low",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"missing_headers": missing},
            why_it_matters="Hardening + best-practice audit",
            recommended_fix="Add the missing security headers (CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy).",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="M07",
        domain="Security",
        title="`target=_blank` tabnabbing (noopener)",
        description="Detects: `target=_blank` tabnabbing (noopener)",
        why_it_matters="Security",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_M07(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None
    vuln_links = []
    for a in ctx.dom().css('a[target="_blank"]'):
        rel_list = (a.attributes.get("rel") or "").split()
        if "noopener" in rel_list or "noreferrer" in rel_list:
            continue
        href = a.attributes.get("href")
        if href:
            vuln_links.append(href)

    if vuln_links:
        return Finding(
            check_id="M07",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"vulnerable_links": vuln_links[:5]},
            why_it_matters="Security",
            recommended_fix=(
                'Add rel="noopener" or rel="noreferrer" to target="_blank" links.'
            ),
        )
    return None


@register(
    CheckSpec(
        check_id="M08",
        domain="Security",
        title="Server/software version leakage in headers",
        description="Detects: Server/software version leakage in headers",
        why_it_matters="Info disclosure",
        default_severity="Low",
        fix_tier="FLAG",
        data_source="Hd",
        fix_template=None,
    )
)
def check_M08(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.url_row:
        return None
    headers = {k.lower(): str(v) for k, v in (getattr(ctx.url_row, "headers", {}) or {}).items()}  # noqa: E501
    leaks = {}
    for h in ("server", "x-powered-by"):
        val = headers.get(h, "")
        if re.search(r"\d+\.\d+", val):  # a version number is exposed
            leaks[h] = val
    if leaks:
        return Finding(
            check_id="M08",
            severity="Low",
            tier="FLAG",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"version_leaks": leaks},
            why_it_matters="Info disclosure",
            recommended_fix="Strip version numbers from Server / X-Powered-By headers.",
        )
    return None


@register(
    CheckSpec(
        check_id="M09",
        domain="Security",
        title="WordPress version exposed (generator meta / readme.html)",
        description="Detects: WordPress version exposed (generator meta / readme.html)",
        why_it_matters="Attack-surface disclosure",
        default_severity="Low",
        fix_tier="FLAG",
        data_source="C",
        fix_template=None,
    )
)
def check_M09(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html:
        return None

    if ctx.url.endswith("/readme.html"):
        if "WordPress" in ctx.raw_html:
            return Finding(
                check_id="M09",
                severity="Low",
                tier="FLAG",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"type": "readme.html"},
                why_it_matters="Attack-surface disclosure",
                recommended_fix="Remove readme.html and hide WP version.",
            )

    generator = None
    for m in ctx.dom().css("meta"):
        if (m.attributes.get("name") or "").lower() == "generator":
            generator = m
            break
    if generator is not None:
        content = generator.attributes.get("content") or ""
        if "WordPress" in content:
            return Finding(
                check_id="M09",
                severity="Low",
                tier="FLAG",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"generator": content},
                why_it_matters="Attack-surface disclosure",
                recommended_fix="Remove WordPress version from meta generator.",
            )

    return None


@register(
    CheckSpec(
        check_id="M10",
        domain="Security",
        title="XML-RPC / wp-json user enumeration open",
        description="Detects: XML-RPC / wp-json user enumeration open",
        why_it_matters="WP-specific hardening",
        default_severity="Medium",
        fix_tier="FLAG",
        data_source="Hd",
        fix_template=None,
    )
)
def check_M10(ctx: CrawlContext) -> Optional[Finding]:
    # Intentionally deferred (status: deferred) — inert until its data source is wired.
    return None
