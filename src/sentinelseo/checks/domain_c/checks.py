import re
from typing import Optional
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


def norm_url(base: str, href: str) -> str:
    """Absolute + normalized: lowercase scheme/host, strip fragment, collapse //"""
    absu = urljoin(base, (href or "").strip())
    s = urlsplit(absu)
    path = re.sub(r'/{2,}', '/', s.path) or '/'
    return urlunsplit((s.scheme.lower(), s.netloc.lower(), path, s.query, ''))


def same_registrable_domain(a: str, b: str) -> bool:
    ha, hb = urlparse(a).netloc.lower(), urlparse(b).netloc.lower()
    return ha.split(':')[0].split('.')[-2:] == hb.split(':')[0].split('.')[-2:]


def has_fragment(raw: Optional[str]) -> bool:
    return bool(raw) and raw is not None and '#' in raw


def is_absolute(raw: Optional[str]) -> bool:
    return bool(raw) and bool(urlparse(raw).scheme)


def _canon_target(ctx: CrawlContext) -> Optional[str]:
    canonical = getattr(ctx.url_row, "canonical", None) if ctx.url_row else None
    return norm_url(ctx.url, canonical) if canonical else None


@register(
    CheckSpec(
        check_id="C01",
        domain="Canonicalization",
        title="Missing canonical",
        description="Detects: Missing canonical",
        why_it_matters="No consolidation signal on dup-prone URLs",
        default_severity="Medium",
        fix_tier="AUTO",
        data_source="C",
        fix_template=None,
    )
)
def check_C01(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row:
        status = getattr(ctx.url_row, "status", None)
        canonical = getattr(ctx.url_row, "canonical", None)
        meta_robots = getattr(ctx.url_row, "meta_robots", "") or ""

        if status == 200 and canonical is None and 'noindex' not in str(meta_robots):
            return Finding(
                check_id="C01",
                severity="Medium",
                tier="AUTO",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={},
                why_it_matters="No consolidation signal on dup-prone URLs",
                recommended_fix="Add a self-referential canonical.",
            )
    return None


@register(
    CheckSpec(
        check_id="C02",
        domain="Canonicalization",
        title="Non-self-referential canonical (unintended)",
        description="Detects: Non-self-referential canonical (unintended)",
        why_it_matters="Page canonicalizes away, drops from index",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_C02(ctx: CrawlContext) -> Optional[Finding]:
    r = ctx.url_row
    if not r or r.status != 200 or not r.canonical:
        return None
    page = urlunsplit(urlsplit(ctx.url)._replace(fragment=""))
    canon = urljoin(ctx.url, r.canonical)
    same_host = urlparse(page).netloc == urlparse(canon).netloc
    if same_host and canon.rstrip("/") != page.rstrip("/"):
        return Finding(
            check_id="C02",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"canonical": r.canonical, "page": ctx.url},
            why_it_matters="Page canonicalizes away, may drop from index",
            recommended_fix="Point the canonical at this URL unless consolidation is intended.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="C03",
        domain="Canonicalization",
        title="Canonical to non-indexable (noindex) URL",
        description="Detects: Canonical to non-indexable (noindex) URL",
        why_it_matters="Contradictory signals",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_C03(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="C04",
        domain="Canonicalization",
        title="Canonical to 4xx/5xx/redirect",
        description="Detects: Canonical to 4xx/5xx/redirect",
        why_it_matters="Broken canonical target",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_C04(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row:
        canonical = getattr(ctx.url_row, "canonical", None)
        status = getattr(ctx.url_row, "status", None)
        if canonical == ctx.url and status is not None and status >= 300:
            return Finding(
                check_id="C04",
                severity="High",
                tier="REVIEW",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"canonical": canonical, "status": status},
                why_it_matters="Broken canonical target",
                recommended_fix="Ensure canonical points to a 200 OK URL.",
            )
    return None


@register(
    CheckSpec(
        check_id="C05",
        domain="Canonicalization",
        title="Multiple conflicting canonicals on one page",
        description="Detects: Multiple conflicting canonicals on one page",
        why_it_matters="Google may ignore all",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_C05(ctx: CrawlContext) -> Optional[Finding]:
    canonical_count = 0
    if ctx.raw_html:
        hrefs = re.findall(
            r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',
            ctx.raw_html,
            re.IGNORECASE,
        )
        hrefs2 = re.findall(
            r'<link[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']',
            ctx.raw_html,
            re.IGNORECASE,
        )
        canonical_count = len(set(hrefs + hrefs2))

    if canonical_count > 1:
        return Finding(
            check_id="C05",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"count": canonical_count},
            why_it_matters="Google may ignore all",
            recommended_fix="Keep exactly one canonical.",
        )
    return None


@register(
    CheckSpec(
        check_id="C06",
        domain="Canonicalization",
        title="Canonical set only in HTTP header vs HTML mismatch",
        description="Detects: Canonical set only in HTTP header vs HTML mismatch",
        why_it_matters="Conflicting canonical sources",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C+Hd",
        fix_template=None,
    )
)
def check_C06(ctx: CrawlContext) -> Optional[Finding]:
    headers = getattr(ctx.url_row, "headers", {}) if ctx.url_row else {}
    hdr = headers.get("link", "")
    m = re.search(r'<([^>]+)>\s*;\s*rel=["\']?canonical', hdr, re.I)
    canonical = getattr(ctx.url_row, "canonical", None) if ctx.url_row else None

    if m and canonical and norm_url(ctx.url, m.group(1)) != _canon_target(ctx):
        return Finding(
            check_id="C06",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"header": m.group(1), "html": canonical},
            why_it_matters="Conflicting canonical sources",
            recommended_fix="Make both agree.",
        )
    return None


@register(
    CheckSpec(
        check_id="C07",
        domain="Canonicalization",
        title="Canonical changed/added/removed by JS (response vs render)",
        description="Detects: Canonical changed by JS (response vs render)",
        why_it_matters="Render-dependent canonical",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_C07(ctx: CrawlContext) -> Optional[Finding]:
    render_diff = {
        getattr(d, "element", ""): getattr(d, "state", "") for d in ctx.render_diffs
    }

    can_state = render_diff.get("canonical")
    link_state = render_diff.get("link")

    if can_state in ("created", "modified", "deleted") or \
       link_state in ("created", "modified", "deleted"):
        val = can_state or link_state
        return Finding(
            check_id="C07",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"render_diff": val},
            why_it_matters="Render-dependent canonical",
            recommended_fix="Emit the final canonical in server HTML.",
        )
    return None


@register(
    CheckSpec(
        check_id="C08",
        domain="Canonicalization",
        title="Cross-domain canonical (unintended)",
        description="Detects: Cross-domain canonical (unintended)",
        why_it_matters="Consolidates to another domain",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_C08(ctx: CrawlContext) -> Optional[Finding]:
    t = _canon_target(ctx)
    if t and not same_registrable_domain(t, ctx.url):
        return Finding(
            check_id="C08",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"canonical": t},
            why_it_matters="Consolidates to another domain",
            recommended_fix="Confirm intentional; usually canonical stays on-domain.",
        )
    return None


@register(
    CheckSpec(
        check_id="C09",
        domain="Canonicalization",
        title="Canonical uses relative / protocol-relative / non-absolute URL",
        description="Detects: Canonical uses relative / non-absolute URL",
        why_it_matters="Fragile, misparsed",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_C09(ctx: CrawlContext) -> Optional[Finding]:
    raw = None
    canonical_in_head = True
    if ctx.url_row:
        raw = getattr(ctx.url_row, "canonical_raw", None)
        if raw is None:
            raw = getattr(ctx.url_row, "canonical", None)
        canonical_in_head = getattr(ctx.url_row, "canonical_in_head", True)

    problems = []
    if raw and not is_absolute(raw):
        problems.append("relative")
    if raw and raw.strip().startswith("//"):
        problems.append("protocol-relative")
    if has_fragment(raw):
        problems.append("contains-fragment")
    if raw and not canonical_in_head:
        problems.append("outside-head")

    if problems:
        return Finding(
            check_id="C09",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"problems": problems, "raw": raw},
            why_it_matters="Fragile, misparsed",
            recommended_fix="Use an absolute canonical inside <head>.",
        )
    return None


@register(
    CheckSpec(
        check_id="C10",
        domain="Canonicalization",
        title="Parameterized URL not canonicalized to clean URL",
        description="Detects: Parameterized URL not canonicalized",
        why_it_matters="Duplicate param variants indexed",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_C10(ctx: CrawlContext) -> Optional[Finding]:
    if ctx.url_row:
        canonical = getattr(ctx.url_row, "canonical", None)
        indexable = getattr(ctx.url_row, "indexable", False)

        pat = r'[?&](utm_|sessionid|sid|replytocom|orderby|filter|fbclid|gclid)'
        _PARAM_JUNK = re.compile(pat, re.I)
        if indexable and _PARAM_JUNK.search(ctx.url):
            if not canonical or _PARAM_JUNK.search(canonical) or canonical == ctx.url:
                return Finding(
                    check_id="C10",
                    severity="Medium",
                    tier="REVIEW",
                    affected_urls=[ctx.url],
                    wp_object_map={},
                    evidence={"url": ctx.url},
                    why_it_matters="Duplicate param variants indexed",
                    recommended_fix="Canonicalize to the clean URL or block it.",
                )
    return None


@register(
    CheckSpec(
        check_id="C11",
        domain="Canonicalization",
        title="Paginated page 2+ canonicalized to page 1 (anti-pattern)",
        description="Detects: Paginated page 2+ canonicalized to page 1 (anti-pattern)",
        why_it_matters="Google drops component pages",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_C11(ctx: CrawlContext) -> Optional[Finding]:
    is_pag = re.search(r'(?:[?&]page=|/page/)(\d+)', ctx.url)
    if is_pag and int(is_pag.group(1)) >= 2:
        t = _canon_target(ctx)
        base = re.sub(r'(?:[?&]page=\d+|/page/\d+/?)', '', ctx.url)
        if t and norm_url(ctx.url, t) == norm_url(ctx.url, base):
            return Finding(
                check_id="C11",
                severity="Medium",
                tier="REVIEW",
                affected_urls=[ctx.url],
                wp_object_map={},
                evidence={"canonical": t},
                why_it_matters="Google drops component pages",
                recommended_fix="Use self-referential canonicals on paginated URLs.",
            )
    return None
