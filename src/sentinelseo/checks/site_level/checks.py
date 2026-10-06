import array
import re
from typing import Any, Iterable
from urllib.parse import urlparse

from datasketch import MinHash, MinHashLSH  # type: ignore

from sentinelseo.audit.context import SiteContext
from sentinelseo.checks.registry import CheckSpec, Finding
from sentinelseo.checks.site_level.registry import register_site_level

# The parser stores MinHash.hashvalues (datasketch uint32) via .tobytes(); decode
# with the platform typecode whose itemsize is 4 bytes to match that width.
_U32_CODE = "I" if array.array("I").itemsize == 4 else "L"


# Recognizes common pagination URL shapes (?page=2, /page/2/, ?paged=2) in
# addition to explicit rel=prev/next links, so ignore_paginated_dupes can drop
# them from duplicate-content detection (SF "Ignore Paginated URLs for Duplicates").
_PAGINATION_URL = re.compile(r"(?:[?&](?:page|paged|pg)=\d+|/page/\d+/?$)", re.IGNORECASE)


def _is_paginated(url: str, ctx: Any) -> bool:
    row = getattr(ctx, "url_row", None)
    if row is not None and (getattr(row, "prev_url", None) or getattr(row, "next_url", None)):
        return True
    return bool(_PAGINATION_URL.search(url))


def _base_finding(check_id: str, severity: str, tier: str, url: str, evidence: dict[str, Any], why: str = "", fix: str = "") -> Finding:
    return Finding(
        check_id=check_id,
        severity=severity,
        tier=tier,
        affected_urls=[url],
        wp_object_map={},
        evidence=evidence,
        why_it_matters=why,
        recommended_fix=fix,
    )

# D02, D08, D14: Duplicates
@register_site_level(CheckSpec(check_id="D02", domain="On-page", title="Duplicate titles", description="", why_it_matters="", default_severity="High", fix_tier="REVIEW", data_source="crawl"))
def check_D02(site: SiteContext) -> Iterable[Finding]:
    seen: dict[str, list[str]] = {}
    for url, ctx in site.pages.items():
        if ctx.url_row and ctx.url_row.title and ctx.url_row.status == 200 and ctx.url_row.indexable:
            seen.setdefault(ctx.url_row.title.strip().lower(), []).append(url)

    for title, urls in seen.items():
        if len(urls) > 1:
            for u in urls:
                yield _base_finding("D02", "High", "REVIEW", u, {"title": title, "shared_with": [x for x in urls if x != u]})

@register_site_level(CheckSpec(check_id="D08", domain="On-page", title="Duplicate meta descriptions", description="", why_it_matters="", default_severity="Medium", fix_tier="REVIEW", data_source="crawl"))
def check_D08(site: SiteContext) -> Iterable[Finding]:
    seen: dict[str, list[str]] = {}
    for url, ctx in site.pages.items():
        if ctx.url_row and ctx.url_row.meta_desc and ctx.url_row.status == 200 and ctx.url_row.indexable:
            seen.setdefault(ctx.url_row.meta_desc.strip().lower(), []).append(url)

    for desc, urls in seen.items():
        if len(urls) > 1:
            for u in urls:
                yield _base_finding("D08", "Medium", "REVIEW", u, {"meta_desc": desc, "shared_with": [x for x in urls if x != u]})

@register_site_level(CheckSpec(check_id="D14", domain="On-page", title="Duplicate H1", description="", why_it_matters="", default_severity="Low", fix_tier="REVIEW", data_source="crawl"))
def check_D14(site: SiteContext) -> Iterable[Finding]:
    seen: dict[str, list[str]] = {}
    for url, ctx in site.pages.items():
        if ctx.url_row and ctx.url_row.h1 and ctx.url_row.status == 200 and ctx.url_row.indexable:
            seen.setdefault(ctx.url_row.h1[0].strip().lower(), []).append(url)

    for h1, urls in seen.items():
        if len(urls) > 1:
            for u in urls:
                yield _base_finding("D14", "Low", "REVIEW", u, {"h1": h1, "shared_with": [x for x in urls if x != u]})

@register_site_level(CheckSpec(check_id="D06", domain="On-page", title="Title same as H1", description="", why_it_matters="", default_severity="Low", fix_tier="REVIEW", data_source="crawl"))
def check_D06(site: SiteContext) -> Iterable[Finding]:
    count, matches = 0, 0
    for _url, ctx in site.pages.items():
        if ctx.url_row and ctx.url_row.title and ctx.url_row.h1:
            count += 1
            if ctx.url_row.title.strip().lower() == ctx.url_row.h1[0].strip().lower():
                matches += 1
    if count > 0 and matches == count:
        for url in site.pages.keys():
            yield _base_finding("D06", "Low", "REVIEW", url, {"title_matches_h1_sitewide": True})

@register_site_level(CheckSpec(check_id="E01", domain="Content", title="Exact duplicate", description="", why_it_matters="", default_severity="High", fix_tier="REVIEW", data_source="crawl"))
def check_E01(site: SiteContext) -> Iterable[Finding]:
    skip_paginated = bool(site.config.get("ignore_paginated_dupes"))
    seen: dict[str, list[str]] = {}
    for url, ctx in site.pages.items():
        if ctx.url_row and ctx.url_row.content_hash and ctx.url_row.status == 200 and ctx.url_row.indexable:
            if skip_paginated and _is_paginated(url, ctx):
                continue
            seen.setdefault(ctx.url_row.content_hash, []).append(url)
    for hash_val, urls in seen.items():
        if len(urls) > 1:
            for u in urls:
                yield _base_finding("E01", "High", "REVIEW", u, {"hash": hash_val, "exact_dups": [x for x in urls if x != u]})


def _minhash_from_bytes(raw: bytes) -> MinHash:
    """Rebuild a datasketch MinHash from the raw hashvalues bytes the parser
    stores (mh.hashvalues.tobytes()). The parser's get_minhash() uses the
    library defaults for datasketch 2.0 — num_perm=128, seed=1, the affine32
    hashing scheme and uint32 hashvalues — which must be mirrored here so the
    band signatures line up for LSH querying."""
    arr = array.array(_U32_CODE)
    arr.frombytes(raw)
    return MinHash(num_perm=128, hashvalues=arr, scheme="affine32")


@register_site_level(CheckSpec(check_id="E02", domain="Content", title="Near duplicate", description="", why_it_matters="", default_severity="Medium", fix_tier="REVIEW", data_source="crawl"))
def check_E02(site: SiteContext) -> Iterable[Finding]:
    # SF "Near Duplicates" threshold (percentage similarity); default 90%.
    try:
        pct = float(site.config.get("near_dup_threshold", 90))
    except (TypeError, ValueError):
        pct = 90.0
    threshold = min(max(pct / 100.0, 0.05), 1.0)
    skip_paginated = bool(site.config.get("ignore_paginated_dupes"))

    lsh = MinHashLSH(threshold=threshold, num_perm=128)
    hashes = {}
    # pass 1: build
    for url, ctx in site.pages.items():
        if ctx.url_row and ctx.url_row.minhash and ctx.url_row.status == 200 and ctx.url_row.indexable:
            if skip_paginated and _is_paginated(url, ctx):
                continue
            try:
                m = _minhash_from_bytes(ctx.url_row.minhash)
                lsh.insert(url, m)
                hashes[url] = m
            except Exception:
                pass

    # pass 2: query
    for url, m in hashes.items():
        results = lsh.query(m)
        dups = [r for r in results if r != url]
        if dups:
            yield _base_finding("E02", "Medium", "REVIEW", url, {"near_dups": dups, "threshold_pct": round(threshold * 100)})

@register_site_level(CheckSpec(check_id="E03", domain="Content", title="URL pattern duplicate", description="", why_it_matters="", default_severity="Medium", fix_tier="REVIEW", data_source="crawl"))
def check_E03(site: SiteContext) -> Iterable[Finding]:
    # Flag duplicate *access patterns* (index.php paths, WP ugly-permalink query
    # params that duplicate the pretty URL). The old logic fired on every
    # trailing-slash URL — that is normal pretty-permalink structure, not a dupe.
    dupe_param = re.compile(r"(?:^|&)(?:p|page_id|cat|m|author|attachment_id)=")
    for url, _ctx in site.pages.items():
        parsed = urlparse(url)
        if parsed.path.endswith("/index.php") or dupe_param.search(parsed.query):
            yield _base_finding(
                "E03", "Medium", "REVIEW", url,
                {"path": parsed.path, "query": parsed.query},
            )

@register_site_level(CheckSpec(check_id="I01", domain="Internationalization", title="Missing return hreflang", description="", why_it_matters="", default_severity="High", fix_tier="REVIEW", data_source="crawl"))
def check_I01(site: SiteContext) -> Iterable[Finding]:
    links = {}
    for url, ctx in site.pages.items():
        if ctx.url_row and ctx.url_row.hreflang:
            links[url] = {h[1] for h in ctx.url_row.hreflang}

    for url, targets in links.items():
        missing = []
        for target in targets:
            if target in site.pages:
                if url not in links.get(target, set()):
                    missing.append(target)
            else:
                # Target not crawled, assume it might be missing
                pass
        if missing:
            yield _base_finding("I01", "High", "REVIEW", url, {"missing_return_from": missing})

@register_site_level(CheckSpec(check_id="K01", domain="Sitemap", title="Sitemap missing or not in robots.txt", description="", why_it_matters="", default_severity="Medium", fix_tier="REVIEW", data_source="crawl"))
def check_K01(site: SiteContext) -> Iterable[Finding]:
    if not site.sitemap_files:
        yield _base_finding("K01", "Medium", "REVIEW", site.base_url, {"sitemaps_found": 0})
    else:
        # Check if they are referenced in robots.txt (which we assume is stored in site.robots_txt)
        if "sitemap:" not in site.robots_txt.lower():
            yield _base_finding("K01", "Low", "REVIEW", site.base_url, {"in_robots_txt": False})

@register_site_level(CheckSpec(check_id="K02", domain="Sitemap", title="Sitemap contains non-200 URLs", description="", why_it_matters="", default_severity="Medium", fix_tier="REVIEW", data_source="crawl"))
def check_K02(site: SiteContext) -> Iterable[Finding]:
    for url, ctx in site.pages.items():
        if ctx.url_row and ctx.url_row.in_sitemap and ctx.url_row.status != 200:
            yield _base_finding("K02", "Medium", "REVIEW", url, {"status": ctx.url_row.status})

@register_site_level(CheckSpec(check_id="K03", domain="Sitemap", title="Sitemap contains noindex or canonicalized-away URLs", description="", why_it_matters="", default_severity="Medium", fix_tier="REVIEW", data_source="crawl"))
def check_K03(site: SiteContext) -> Iterable[Finding]:
    for url, ctx in site.pages.items():
        if ctx.url_row and ctx.url_row.in_sitemap:
            if not ctx.url_row.indexable or (ctx.url_row.canonical and ctx.url_row.canonical != url):
                yield _base_finding("K03", "Medium", "REVIEW", url, {"indexable": ctx.url_row.indexable, "canonical": ctx.url_row.canonical})

@register_site_level(CheckSpec(check_id="K04", domain="Sitemap", title="Sitemap contains redirects", description="", why_it_matters="", default_severity="Low", fix_tier="REVIEW", data_source="crawl"))
def check_K04(site: SiteContext) -> Iterable[Finding]:
    for url, ctx in site.pages.items():
        if ctx.url_row and ctx.url_row.in_sitemap and ctx.url_row.status in (301, 302, 307, 308):
            yield _base_finding("K04", "Low", "REVIEW", url, {"status": ctx.url_row.status})

@register_site_level(CheckSpec(check_id="K05", domain="Sitemap", title="Indexable pages missing from sitemap", description="", why_it_matters="", default_severity="Medium", fix_tier="REVIEW", data_source="crawl"))
def check_K05(site: SiteContext) -> Iterable[Finding]:
    # Only meaningful when a sitemap actually exists; otherwise K01 covers the
    # "no sitemap" case and this would flag every indexable page.
    if not site.sitemap_files:
        return
    for url, ctx in site.pages.items():
        if ctx.url_row and ctx.url_row.status == 200 and ctx.url_row.indexable and not ctx.url_row.in_sitemap:
            yield _base_finding("K05", "Medium", "REVIEW", url, {"in_sitemap": False})

@register_site_level(CheckSpec(check_id="K06", domain="Sitemap", title="Sitemap exceeds 50k URLs or 50MB", description="", why_it_matters="", default_severity="Medium", fix_tier="FLAG", data_source="crawl"))
def check_K06(site: SiteContext) -> Iterable[Finding]:
    for sm, (count, size) in site.sitemap_files.items():
        if count > 50000 or size > 50 * 1024 * 1024:
            yield _base_finding("K06", "Medium", "FLAG", sm, {"urls": count, "size_bytes": size})

@register_site_level(CheckSpec(check_id="L01", domain="Robots", title="Disallow: / (whole site blocked)", description="", why_it_matters="", default_severity="Critical", fix_tier="FLAG", data_source="crawl"))
def check_L01(site: SiteContext) -> Iterable[Finding]:
    if site.robots_txt:
        for line in site.robots_txt.splitlines():
            line = line.strip().lower()
            if line.startswith("disallow:") and line.split(":", 1)[1].strip() == "/":
                yield _base_finding("L01", "Critical", "FLAG", site.base_url, {"disallow": "/"})

@register_site_level(CheckSpec(check_id="L05", domain="Robots", title="robots.txt wrong location or content-type", description="", why_it_matters="", default_severity="Medium", fix_tier="FLAG", data_source="crawl"))
def check_L05(site: SiteContext) -> Iterable[Finding]:
    if site.robots_txt_status == 200 and "text/plain" not in site.robots_txt_content_type.lower():
        yield _base_finding("L05", "Medium", "FLAG", site.base_url, {"content_type": site.robots_txt_content_type})

@register_site_level(CheckSpec(check_id="L07", domain="Robots", title="High crawl-delay", description="", why_it_matters="", default_severity="Low", fix_tier="FLAG", data_source="crawl"))
def check_L07(site: SiteContext) -> Iterable[Finding]:
    if site.robots_txt:
        for line in site.robots_txt.splitlines():
            line = line.strip().lower()
            if line.startswith("crawl-delay:"):
                try:
                    val = float(line.split(":", 1)[1].strip())
                    if val > 5:
                        yield _base_finding("L07", "Low", "FLAG", site.base_url, {"crawl_delay": val})
                except ValueError:
                    pass

@register_site_level(CheckSpec(check_id="M04", domain="Security", title="Expired or soon-expiring TLS certificate", description="", why_it_matters="", default_severity="Critical", fix_tier="FLAG", data_source="crawl"))
def check_M04(site: SiteContext) -> Iterable[Finding]:
    if site.cert_days_valid is not None:
        if site.cert_days_valid < 0:
            yield _base_finding("M04", "Critical", "FLAG", site.base_url, {"days_valid": site.cert_days_valid})
        elif site.cert_days_valid <= 30:
            yield _base_finding("M04", "High", "FLAG", site.base_url, {"days_valid": site.cert_days_valid})

@register_site_level(CheckSpec(check_id="M10", domain="Security", title="XML-RPC / REST user enumeration open", description="", why_it_matters="", default_severity="Medium", fix_tier="FLAG", data_source="crawl"))
def check_M10(site: SiteContext) -> Iterable[Finding]:
    if site.probe.get("xmlrpc_open"):
        yield _base_finding("M10", "Medium", "FLAG", site.base_url, {"xmlrpc": "open"})
    if site.probe.get("rest_users_open"):
        yield _base_finding("M10", "Medium", "FLAG", site.base_url, {"rest_users": "open"})

@register_site_level(CheckSpec(check_id="R01", domain="Crawlers", title="AI training crawlers blocked", description="", why_it_matters="", default_severity="Info", fix_tier="REVIEW", data_source="crawl"))
def check_R01(site: SiteContext) -> Iterable[Finding]:
    if site.probe.get("ai_training_crawlers_blocked"):
        yield _base_finding("R01", "Info", "REVIEW", site.base_url, {"blocked": True})

@register_site_level(CheckSpec(check_id="R02", domain="Crawlers", title="AI search crawlers blocked", description="", why_it_matters="", default_severity="High", fix_tier="REVIEW", data_source="crawl"))
def check_R02(site: SiteContext) -> Iterable[Finding]:
    if site.probe.get("ai_search_crawlers_blocked"):
        yield _base_finding("R02", "High", "REVIEW", site.base_url, {"blocked": True})

@register_site_level(CheckSpec(check_id="R04", domain="Crawlers", title="CDN/WAF silently blocks AI bots despite robots.txt allow", description="", why_it_matters="", default_severity="High", fix_tier="FLAG", data_source="crawl"))
def check_R04(site: SiteContext) -> Iterable[Finding]:
    if site.probe.get("waf_blocks_ai_silently"):
        yield _base_finding("R04", "High", "FLAG", site.base_url, {"waf_blocks_ai": True})

@register_site_level(CheckSpec(check_id="S01", domain="LLMs", title="Missing llms.txt", description="", why_it_matters="", default_severity="Info", fix_tier="REVIEW", data_source="crawl"))
def check_S01(site: SiteContext) -> Iterable[Finding]:
    if site.llms_txt_status != 200:
        yield _base_finding("S01", "Info", "REVIEW", site.base_url, {"status": site.llms_txt_status})

@register_site_level(CheckSpec(check_id="S02", domain="LLMs", title="llms.txt malformed", description="", why_it_matters="", default_severity="Low", fix_tier="REVIEW", data_source="crawl"))
def check_S02(site: SiteContext) -> Iterable[Finding]:
    if site.llms_txt_status == 200:
        if not site.has_h1_in_llms_txt or len(site.llms_txt_content) < 50 or not site.llms_txt_links:
            yield _base_finding("S02", "Low", "REVIEW", site.base_url, {"has_h1": site.has_h1_in_llms_txt, "len": len(site.llms_txt_content), "links": len(site.llms_txt_links)})

@register_site_level(CheckSpec(check_id="S03", domain="LLMs", title="llms.txt is an unsorted link dump", description="", why_it_matters="", default_severity="Low", fix_tier="REVIEW", data_source="crawl"))
def check_S03(site: SiteContext) -> Iterable[Finding]:
    if site.llms_txt_status == 200:
        if site.llms_txt_links and len(site.llms_txt_content) < len(site.llms_txt_links) * 40:
            yield _base_finding("S03", "Low", "REVIEW", site.base_url, {"links": len(site.llms_txt_links), "len": len(site.llms_txt_content)})

@register_site_level(CheckSpec(check_id="T08", domain="URLs", title="Trailing-slash inconsistency", description="", why_it_matters="", default_severity="Medium", fix_tier="REVIEW", data_source="crawl"))
def check_T08(site: SiteContext) -> Iterable[Finding]:
    slash = 0
    no_slash = 0
    for url, ctx in site.pages.items():
        if ctx.url_row and ctx.url_row.status == 200 and ctx.url_row.indexable:
            p = urlparse(url).path
            if p != "/":
                if p.endswith("/"):
                    slash += 1
                else:
                    no_slash += 1
    if slash > 0 and no_slash > 0:
        yield _base_finding("T08", "Medium", "REVIEW", site.base_url, {"slash": slash, "no_slash": no_slash})

@register_site_level(CheckSpec(check_id="V10", domain="Staging", title="Staging/dev site indexable", description="", why_it_matters="", default_severity="Critical", fix_tier="FLAG", data_source="crawl"))
def check_V10(site: SiteContext) -> Iterable[Finding]:
    base = site.base_url.lower()
    if "staging." in base or "dev." in base or "test." in base:
        if site.robots_txt and "disallow: /" not in site.robots_txt.lower():
            yield _base_finding("V10", "Critical", "FLAG", site.base_url, {"is_staging": True, "blocked": False})

@register_site_level(CheckSpec(check_id="W05", domain="WWW", title="Multiple homepage versions resolve 200", description="", why_it_matters="", default_severity="Medium", fix_tier="REVIEW", data_source="crawl"))
def check_W05(site: SiteContext) -> Iterable[Finding]:
    if site.probe.get("homepage_versions_200", 0) > 1:
        yield _base_finding("W05", "Medium", "REVIEW", site.base_url, {"versions": site.probe["homepage_versions_200"]})


@register_site_level(CheckSpec(check_id="B04", domain="Response codes & redirects", title="Broken internal links (→ 4xx/5xx)", description="", why_it_matters="Equity loss + UX; list inlink sources", default_severity="High", fix_tier="REVIEW", data_source="crawl"))
def check_B04(site: SiteContext) -> Iterable[Finding]:
    status_by_addr = {a: (p.url_row.status if p.url_row else 0) for a, p in site.pages.items()}
    for addr, page in site.pages.items():
        if not page.url_row:
            continue
        broken = [
            link for link in (getattr(page.url_row, "internal_links", None) or [])
            if (status_by_addr.get(link) or 0) >= 400
        ]
        if broken:
            yield _base_finding("B04", "High", "REVIEW", addr, {"broken_targets": broken[:10]}, "Equity loss + UX", "Fix or remove internal links pointing to 4xx/5xx pages.")


@register_site_level(CheckSpec(check_id="B05", domain="Response codes & redirects", title="Broken external (outbound) links", description="", why_it_matters="UX + trust signal degradation", default_severity="Medium", fix_tier="REVIEW", data_source="crawl"))
def check_B05(site: SiteContext) -> Iterable[Finding]:
    for addr, page in site.pages.items():
        if not page.url_row:
            continue
        broken = [
            link for link in (getattr(page.url_row, "external_links", None) or [])
            if link in site.external_status and (site.external_status[link] >= 400 or site.external_status[link] == 0)
        ]
        if broken:
            yield _base_finding("B05", "Medium", "REVIEW", addr, {"broken_external": broken[:10]}, "UX + trust", "Fix or remove broken outbound links.")


@register_site_level(CheckSpec(check_id="A03", domain="Crawlability & Indexability", title="Robots.txt missing / returns 5xx", description="", why_it_matters="Crawlers may treat whole site as disallowed on 5xx", default_severity="Critical", fix_tier="FLAG", data_source="Hd"))
def check_A03(site: SiteContext) -> Iterable[Finding]:
    status = site.probe.get("robots_status", 200)
    if status >= 500:
        yield _base_finding("A03", "Critical", "FLAG", site.base_url, {"robots_status": status}, "5xx robots.txt can block the whole site", "Fix the server error serving robots.txt.")


@register_site_level(CheckSpec(check_id="W04", domain="WWW", title="Missing / unhelpful 404 template", description="", why_it_matters="A non-404 for missing URLs creates soft-404 duplication", default_severity="Low", fix_tier="REVIEW", data_source="crawl"))
def check_W04(site: SiteContext) -> Iterable[Finding]:
    nf = site.probe.get("notfound_status", 0)
    if nf and nf != 404 and nf < 500:
        yield _base_finding("W04", "Low", "REVIEW", site.base_url, {"missing_url_status": nf}, "Missing URLs should return 404", "Return a proper 404 status for non-existent URLs.")


@register_site_level(CheckSpec(check_id="S04", domain="LLMs", title="Optional llms-full.txt absent", description="", why_it_matters="Full-content AI index missing", default_severity="Info", fix_tier="REVIEW", data_source="crawl"))
def check_S04(site: SiteContext) -> Iterable[Finding]:
    if site.llms_txt_status == 200 and site.probe.get("llms_full_status", 404) != 200:
        yield _base_finding("S04", "Info", "REVIEW", site.base_url, {"llms_full": "absent"}, "Full-content AI index missing", "Consider adding llms-full.txt for large-doc sites.")


@register_site_level(CheckSpec(check_id="B09", domain="Response codes & redirects", title="Internal links pointing to redirects", description="", why_it_matters="Should link the final URL directly", default_severity="Medium", fix_tier="REVIEW", data_source="crawl"))
def check_B09(site: SiteContext) -> Iterable[Finding]:
    status_by_addr = {a: (p.url_row.status if p.url_row else 0) for a, p in site.pages.items()}
    for addr, page in site.pages.items():
        if not page.url_row:
            continue
        redir = [link for link in (getattr(page.url_row, "internal_links", None) or []) if 300 <= (status_by_addr.get(link) or 0) < 400]
        if redir:
            yield _base_finding("B09", "Medium", "REVIEW", addr, {"redirect_targets": redir[:10]}, "Link the final URL directly", "Update internal links to point at the redirect's destination.")


@register_site_level(CheckSpec(check_id="B10", domain="Response codes & redirects", title="Canonical points to a redirected URL", description="", why_it_matters="Canonical target itself redirects", default_severity="High", fix_tier="REVIEW", data_source="crawl"))
def check_B10(site: SiteContext) -> Iterable[Finding]:
    status_by_addr = {a: (p.url_row.status if p.url_row else 0) for a, p in site.pages.items()}
    for addr, page in site.pages.items():
        if page.url_row and page.url_row.canonical:
            st = status_by_addr.get(page.url_row.canonical)
            if st is not None and 300 <= st < 400:
                yield _base_finding("B10", "High", "REVIEW", addr, {"canonical": page.url_row.canonical, "status": st}, "Canonical target redirects", "Point the canonical at the final (non-redirecting) URL.")


@register_site_level(CheckSpec(check_id="C03", domain="Canonicalization", title="Canonical to a non-indexable URL", description="", why_it_matters="Contradictory signals", default_severity="High", fix_tier="REVIEW", data_source="crawl"))
def check_C03(site: SiteContext) -> Iterable[Finding]:
    idx_by_addr = {a: (bool(p.url_row.indexable) if p.url_row else True) for a, p in site.pages.items()}
    for addr, page in site.pages.items():
        if page.url_row and page.url_row.canonical and page.url_row.canonical in idx_by_addr:
            if not idx_by_addr[page.url_row.canonical]:
                yield _base_finding("C03", "High", "REVIEW", addr, {"canonical": page.url_row.canonical}, "Canonical target is noindex", "Point the canonical at an indexable URL.")


@register_site_level(CheckSpec(check_id="E05", domain="Content", title="Duplicate title + meta description pair", description="", why_it_matters="Strong duplication signal", default_severity="Medium", fix_tier="REVIEW", data_source="crawl"))
def check_E05(site: SiteContext) -> Iterable[Finding]:
    seen: dict[tuple[str, str], list[str]] = {}
    for url, ctx in site.pages.items():
        r = ctx.url_row
        if r and r.title and r.meta_desc and r.status == 200 and r.indexable:
            seen.setdefault((r.title.strip().lower(), r.meta_desc.strip().lower()), []).append(url)
    for _pair, urls in seen.items():
        if len(urls) > 1:
            for u in urls:
                yield _base_finding("E05", "Medium", "REVIEW", u, {"shared_with": [x for x in urls if x != u]}, "Same title+description on multiple URLs", "Differentiate title and meta description per page.")


@register_site_level(CheckSpec(check_id="E06", domain="Content", title="Keyword cannibalization (same title + H1)", description="", why_it_matters="Pages compete for the same query", default_severity="Medium", fix_tier="REVIEW", data_source="crawl"))
def check_E06(site: SiteContext) -> Iterable[Finding]:
    seen: dict[str, list[str]] = {}
    for url, ctx in site.pages.items():
        r = ctx.url_row
        if r and r.title and r.h1 and r.status == 200 and r.indexable:
            key = r.title.strip().lower() + "||" + r.h1[0].strip().lower()
            seen.setdefault(key, []).append(url)
    for _key, urls in seen.items():
        if len(urls) > 1:
            for u in urls:
                yield _base_finding("E06", "Medium", "REVIEW", u, {"competing_with": [x for x in urls if x != u]}, "Pages compete for the same query", "Consolidate or differentiate the competing pages.")


@register_site_level(CheckSpec(check_id="A01", domain="Crawlability & Indexability", title="Important URL blocked by robots.txt", description="", why_it_matters="Content never crawled/indexed", default_severity="Critical", fix_tier="REVIEW", data_source="crawl"))
def check_A01(site: SiteContext) -> Iterable[Finding]:
    if not site.robots_txt:
        return
    from protego import Protego
    rp = Protego.parse(site.robots_txt)
    for url, ctx in site.pages.items():
        if ctx.url_row and ctx.url_row.status == 200 and not rp.can_fetch(url, "Googlebot"):
            yield _base_finding("A01", "Critical", "REVIEW", url, {"disallowed_for": "Googlebot"}, "Important URL disallowed in robots.txt", "Remove the Disallow rule for this URL if it should be indexed.")


@register_site_level(CheckSpec(check_id="A02", domain="Crawlability & Indexability", title="Robots.txt disallows CSS/JS", description="", why_it_matters="Blocks rendering resources so Google can't render the page", default_severity="High", fix_tier="REVIEW", data_source="crawl"))
def check_A02(site: SiteContext) -> Iterable[Finding]:
    if not site.robots_txt:
        return
    from protego import Protego
    base = f"{urlparse(site.base_url).scheme}://{urlparse(site.base_url).netloc}"
    rp = Protego.parse(site.robots_txt)
    probes = [
        "/wp-content/themes/a/style.css", "/wp-includes/js/a.js",
        "/assets/app.css", "/assets/app.js",
    ]
    blocked = [p for p in probes if not rp.can_fetch(base + p, "Googlebot")]
    if blocked:
        yield _base_finding("A02", "High", "REVIEW", site.base_url, {"blocked_asset_paths": blocked}, "Rendering resources blocked", "Allow CSS/JS paths in robots.txt so Google can render the page.")


@register_site_level(CheckSpec(check_id="A15", domain="Crawlability & Indexability", title="Disallowed URL still internally linked", description="", why_it_matters="Confusing signals; wasted links", default_severity="Low", fix_tier="REVIEW", data_source="crawl"))
def check_A15(site: SiteContext) -> Iterable[Finding]:
    if not site.robots_txt:
        return
    from protego import Protego
    rp = Protego.parse(site.robots_txt)
    for addr, page in site.pages.items():
        if not page.url_row:
            continue
        disallowed = [
            link for link in (getattr(page.url_row, "internal_links", None) or [])
            if not rp.can_fetch(link, "Googlebot")
        ]
        if disallowed:
            yield _base_finding("A15", "Low", "REVIEW", addr, {"disallowed_links": disallowed[:10]}, "Confusing signals; wasted links", "Remove internal links to robots-disallowed URLs.")


# ---------------------------------------------------------------------------
# HTML validation (SF "Perform HTML validation"). Opt-in via config; each rule
# is its own check so it surfaces as a distinct issue row. These read the raw
# response HTML and already-parsed URLRow fields — no extra DOM parse needed.
# ---------------------------------------------------------------------------

_DOCTYPE_RE = re.compile(r"^\s*<!doctype\s+html", re.IGNORECASE)
_CHARSET_RE = re.compile(r"charset", re.IGNORECASE)
_HEAD_RE = re.compile(r"<head\b[^>]*>(.*?)</head>", re.IGNORECASE | re.DOTALL)
_HEAD_STRIP_RE = re.compile(r"<(script|style|template)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_HEAD_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# Flow content that belongs in <body>; its presence in raw <head> markup closes
# the head early (browsers relocate it), so the source is what we must inspect —
# a parsed DOM has already had these moved out and would show a clean head.
_FLOW_IN_HEAD_RE = re.compile(
    r"<(img|div|p|span|a|h[1-6]|ul|ol|li|table|section|article|header|footer|nav|form|button|iframe|main|aside|picture|figure)\b",  # noqa: E501
    re.IGNORECASE,
)


def _html_pages(site: SiteContext) -> Iterable[tuple[str, Any, str]]:
    """Yield (url, ctx, raw_html) for HTML 200 pages when html_validation is on.
    PDFs and other non-HTML rows carry no meaningful markup, so they are skipped."""
    if not site.config.get("html_validation"):
        return
    for url, ctx in site.pages.items():
        row = getattr(ctx, "url_row", None)
        if not row or row.status != 200:
            continue
        ctype = (getattr(row, "content_type", None) or "").lower()
        if ctype and "html" not in ctype:
            continue
        raw = getattr(ctx, "raw_html", "") or getattr(row, "html_response", "") or ""
        if raw.strip():
            yield url, ctx, raw


@register_site_level(CheckSpec(check_id="V13", domain="Validation", title="Missing or misplaced DOCTYPE", description="", why_it_matters="Without a leading <!DOCTYPE html>, browsers fall back to quirks mode, which changes box-model and layout behavior.", default_severity="Low", fix_tier="REVIEW", data_source="crawl"))
def check_V13(site: SiteContext) -> Iterable[Finding]:
    for url, _ctx, raw in _html_pages(site):
        if not _DOCTYPE_RE.match(raw):
            yield _base_finding(
                "V13", "Low", "REVIEW", url, {"first_chars": raw.lstrip()[:60]},
                "Missing/misplaced DOCTYPE triggers quirks mode.",
                "Ensure the document begins with <!DOCTYPE html>.",
            )


@register_site_level(CheckSpec(check_id="V14", domain="Validation", title="Missing <html lang> attribute", description="", why_it_matters="Screen readers and search engines use the lang attribute to determine page language.", default_severity="Low", fix_tier="REVIEW", data_source="crawl"))
def check_V14(site: SiteContext) -> Iterable[Finding]:
    for url, ctx, _raw in _html_pages(site):
        lang = (getattr(ctx.url_row, "lang", None) or "").strip()
        if not lang:
            yield _base_finding(
                "V14", "Low", "REVIEW", url, {"lang": lang or None},
                "No language declared for the document.",
                "Add a lang attribute to the <html> element, e.g. <html lang=\"en\">.",
            )


@register_site_level(CheckSpec(check_id="V15", domain="Validation", title="Multiple <title> elements", description="", why_it_matters="More than one <title> is invalid; engines pick one unpredictably.", default_severity="Low", fix_tier="REVIEW", data_source="crawl"))
def check_V15(site: SiteContext) -> Iterable[Finding]:
    for url, ctx, _raw in _html_pages(site):
        n = int(getattr(ctx.url_row, "title_count", 0) or 0)
        if n > 1:
            yield _base_finding(
                "V15", "Low", "REVIEW", url, {"title_count": n},
                "Multiple <title> elements are invalid HTML.",
                "Keep exactly one <title> element in the document <head>.",
            )


@register_site_level(CheckSpec(check_id="V16", domain="Validation", title="Missing character-encoding declaration", description="", why_it_matters="Without a declared charset the browser guesses encoding, which can mojibake text.", default_severity="Low", fix_tier="REVIEW", data_source="crawl"))
def check_V16(site: SiteContext) -> Iterable[Finding]:
    for url, ctx, raw in _html_pages(site):
        head = raw[:1024]
        header_ct = ""
        hdrs = getattr(ctx.url_row, "headers", None) or {}
        for k, v in hdrs.items():
            if k.lower() == "content-type":
                header_ct = str(v).lower()
                break
        if not _CHARSET_RE.search(head) and "charset" not in header_ct:
            yield _base_finding(
                "V16", "Low", "REVIEW", url, {"checked_bytes": len(head)},
                "No character-encoding declaration in the first 1024 bytes or Content-Type.",
                "Add <meta charset=\"utf-8\"> as the first element in <head>.",
            )


@register_site_level(CheckSpec(check_id="V17", domain="Validation", title="Invalid element in <head>", description="", why_it_matters="Flow content (img, div, p, ...) inside <head> prematurely closes it, dropping later metadata.", default_severity="Low", fix_tier="REVIEW", data_source="crawl"))
def check_V17(site: SiteContext) -> Iterable[Finding]:
    for url, _ctx, raw in _html_pages(site):
        m = _HEAD_RE.search(raw)
        if not m:
            continue
        # Work from the raw source: an HTML parser silently relocates flow content
        # out of <head>, so a parsed tree would look clean. Strip script/style/
        # template bodies and comments first so their contents don't false-positive.
        head = _HEAD_COMMENT_RE.sub("", _HEAD_STRIP_RE.sub("", m.group(1)))
        bad = list(dict.fromkeys(t.lower() for t in _FLOW_IN_HEAD_RE.findall(head)))
        if bad:
            yield _base_finding(
                "V17", "Low", "REVIEW", url, {"invalid_head_elements": bad[:10]},
                "Invalid elements inside <head> close it early and drop metadata.",
                "Move flow content out of <head>; keep only metadata elements there.",
            )
