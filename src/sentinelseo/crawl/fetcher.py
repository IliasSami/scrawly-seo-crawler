import asyncio
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern, Set
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlsplit, urlunsplit

import httpx
from playwright.async_api import BrowserContext, Page, async_playwright
from protego import Protego
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
)

from sentinelseo.crawl.browser import launch_chromium
from sentinelseo.crawl.form_auth import (
    DANGEROUS_PATTERNS,
    cookies_to_header,
    login_and_get_cookies,
    looks_authenticated,
)
from sentinelseo.crawl.form_auth import is_configured as form_auth_configured
from sentinelseo.crawl.pdf import build_pdf_row, is_pdf

from .models import (
    AgenticContext,
    AIAccessMatrix,
    ImageRef,
    MobileContext,
    ResourceRef,
    StructuredDataRow,
    UrlRenderDiffRow,
    URLRow,
)
from .parser import compute_render_diff, parse_html


def is_retryable_status(result: Optional[httpx.Response]) -> bool:
    if result is None:
        return True
    return bool(result.status_code == 429 or result.status_code >= 500)


def _last_result(retry_state: Any) -> Optional[httpx.Response]:
    """After the final retry, hand back the last response (a 5xx/429 page is a
    real finding, not a reason to drop the URL or abort the crawl)."""
    outcome = retry_state.outcome
    if outcome is None or outcome.failed:
        return None
    result: Optional[httpx.Response] = outcome.result()
    return result


# Content types that are pages worth auditing. Anything else a link points at
# (images, archives, media, fonts, binaries) is a file, not a page.
_PAGE_LIKE_PREFIXES = ("text/", "application/xhtml", "application/xml", "application/json",
                       "application/ld+json", "application/rss", "application/atom")


def is_page_like(content_type: Optional[str]) -> bool:
    ct = (content_type or "").split(";")[0].strip().lower()
    return not ct or ct.startswith(_PAGE_LIKE_PREFIXES) or ct.endswith("+xml")


def to_ascii_url(url: str) -> str:
    """IDNA-encode the host (bücher.de -> xn--bcher-kva.de) so a Unicode address
    matches the punycode host the HTTP client actually reports."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    try:
        ascii_host = host.encode("idna").decode("ascii") if host else host
    except UnicodeError:
        return url
    if ascii_host == host:
        return url
    netloc = parts.netloc.replace(host, ascii_host, 1)
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


# Content types that are real, crawlable URLs but are NOT HTML documents.
# They must never go through the browser render pipeline: Chromium shows them in
# a built-in viewer (XML tree / JSON view / plain text) where an injected
# <script> never fires `onload`, so page.add_script_tag() waits forever and the
# crawl worker hangs on that URL for good. Rendering them is also pointless —
# there is no DOM, CWV or accessibility signal to collect.
_HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")

# axe-core is injected into every rendered page to collect a11y violations. It is
# vendored (not pulled from a CDN) so the crawl has no third-party dependency in
# its hot path: no per-page round-trip, no leaking the crawl list to a CDN, and
# it still works fully offline / air-gapped.
AXE_VENDOR_PATH = Path(__file__).parent / "vendor" / "axe.min.js"
_AXE_SOURCE: Optional[str] = None


def _axe_source() -> str:
    """Read the vendored axe-core bundle once and keep it in memory."""
    global _AXE_SOURCE
    if _AXE_SOURCE is None:
        try:
            _AXE_SOURCE = AXE_VENDOR_PATH.read_text(encoding="utf-8")
        except OSError:
            _AXE_SOURCE = ""  # missing bundle → a11y data is skipped, crawl continues
    return _AXE_SOURCE


def is_html_document(content_type: Optional[str], assume_html: bool = True) -> bool:
    """True when a response should go through the render / agentic pipeline.

    A missing Content-Type falls back to the caller's assume-HTML setting (SF
    Advanced "Assume pages are HTML"); anything explicitly declared non-HTML
    (XML sitemaps, RSS, JSON, plain text, images) is parsed but never rendered.
    """
    ct = (content_type or "").split(";")[0].strip().lower()
    if not ct:
        return bool(assume_html)
    return ct in _HTML_CONTENT_TYPES


def _compile_patterns(raw: str) -> List[Pattern[str]]:
    """Split a comma/newline-separated pattern string into compiled regexes."""
    out: List[Pattern[str]] = []
    for part in re.split(r"[,\n]", raw or ""):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(re.compile(part))
        except re.error:
            out.append(re.compile(re.escape(part)))
    return out


def normalize_url(url: str) -> str:
    """Canonicalize a URL for crawl dedup: drop the fragment, strip tracking
    params (utm_*, fbclid, gclid, replytocom, ...), lowercase scheme/host,
    collapse duplicate slashes. This kills the #fragment / tracking-param
    inflation that turned one page into many crawl entries.
    """
    s = urlsplit(url)
    query = ""
    if s.query:
        kept = [
            (k, v)
            for k, v in parse_qsl(s.query, keep_blank_values=True)
            if not _JUNK_PARAM_RE.match(k)
        ]
        query = urlencode(kept)
    path = re.sub(r"/{2,}", "/", s.path) or "/"
    return urlunsplit((s.scheme.lower(), s.netloc.lower(), path, query, ""))


_JUNK_PARAM_RE = re.compile(r"^(utm_|fbclid$|gclid$|replytocom$|sessionid$|sid$|msclkid$)", re.I)


def _srcset_urls(srcset: Optional[str], base_url: str) -> List[str]:
    """Absolute URLs of every candidate in an IMG srcset ("a.png 1x, b.png 2x").
    Bails on data-URI srcsets — commas inside base64 break comma-splitting, and a
    data: image isn't a fetchable resource worth status-checking anyway."""
    if not srcset or "data:" in srcset:
        return []
    out: List[str] = []
    for part in srcset.split(","):
        url = part.strip().split(" ")[0].strip()
        if url:
            out.append(urljoin(base_url, url))
    return out


class Crawler:
    def __init__(
        self,
        concurrency: int = 10,
        max_depth: int = 3,
        user_agent: str = "ScrawlyBot/1.0",
        render: bool = True,
        respect_robots: bool = True,
        render_sample: int = 0,
        include_patterns: str = "",
        exclude_patterns: str = "",
        max_pages: int = 500,
        max_requests_per_sec: float = 0.0,
        max_url_length: int = 0,
        max_query_params: int = 0,
        max_links_per_page: int = 0,
        max_folder_depth: int = 0,
        max_redirects: int = 5,
        discover_sitemap: bool = True,
        sitemap_only: bool = False,
        # --- SF-parity config (Phase 1) ---
        robots_mode: str = "respect",          # respect | ignore | ignore_but_report
        robots_user_agent: str = "",           # UA matched against robots groups
        remove_parameters: str = "",           # comma-separated query keys to strip
        regex_replace: Optional[List[Dict[str, str]]] = None,  # ordered [{pattern,replacement}]
        lowercase_urls: bool = False,
        crawl_fragment_identifiers: bool = False,
        max_urls_per_depth: int = 0,
        max_per_subdomain: int = 0,
        max_page_size_kb: int = 0,
        response_timeout_s: float = 20.0,
        custom_headers: Optional[Dict[str, str]] = None,
        # Resource crawl/store gates (SF Pattern A) — expensive work skipped when off.
        crawl_images: bool = True,
        crawl_external: bool = True,
        crawl_css: bool = True,
        crawl_js: bool = True,
        crawl_media: bool = True,
        # Link-target gates (Pattern A): follow these <link rel> targets as pages.
        # SF defaults all three OFF — the reference is recorded, not followed.
        crawl_hreflang: bool = False,
        crawl_amp: bool = False,
        crawl_pagination: bool = False,
        extract_pdf: bool = True,
        # List mode (SF §17): check exactly these URLs, no link discovery.
        list_mode: bool = False,
        list_urls: Optional[List[str]] = None,
        # Web-form auth (SF §12): credentials come from the environment only.
        form_auth: bool = False,
        render_timeout_s: float = 15.0,   # JS render / AJAX wait (SF Rendering tab)
        axe_timeout_s: float = 10.0,      # per-page cap on the axe-core a11y probe
        # Scope + rendering + extraction options (SF Spider/Rendering/Advanced).
        crawl_subdomains: bool = False,
        crawl_outside_start_folder: bool = False,
        follow_nofollow: bool = False,
        cdns: str = "",
        assume_html: bool = True,
        window_width: int = 1024,
        window_height: int = 768,
        js_error_reporting: bool = False,
        extract_srcset: bool = True,
        content_include: str = "",
        content_exclude: str = "",
        flatten_shadow_dom: bool = False,
        flatten_iframes: bool = False,
    ):
        self.concurrency = concurrency
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.user_agent = user_agent
        self.render = render
        # robots_mode is the SF-style tri-state; respect_robots kept for back-compat.
        self.robots_mode = (robots_mode or "respect").lower()
        self.respect_robots = respect_robots and self.robots_mode != "ignore"
        self.robots_user_agent = robots_user_agent or user_agent
        # Parsed robots.txt per origin ("https://example.com"), fetched once each.
        self._robots: Dict[str, Protego] = {}
        self.render_sample = render_sample
        self._rendered_count = 0
        self.include_res = _compile_patterns(include_patterns)
        self.exclude_res = _compile_patterns(exclude_patterns)
        self.semaphore = asyncio.Semaphore(concurrency)
        self.visited: Set[str] = set()

        # Crawl limits (0 = unlimited). Guard run-away crawls on large sites.
        self.max_requests_per_sec = max_requests_per_sec
        self.max_url_length = max_url_length
        self.max_query_params = max_query_params
        self.max_links_per_page = max_links_per_page
        self.max_folder_depth = max_folder_depth
        self.max_redirects = max_redirects
        self.discover_sitemap = discover_sitemap
        self.sitemap_only = sitemap_only
        # SF-parity URL handling + limits.
        self.remove_parameters = [
            p.strip().lower() for p in (remove_parameters or "").split(",") if p.strip()
        ]
        self.regex_replace = [
            (re.compile(r["pattern"]), r.get("replacement", ""))
            for r in (regex_replace or []) if r.get("pattern")
        ]
        self.lowercase_urls = lowercase_urls
        self.crawl_fragment_identifiers = crawl_fragment_identifiers
        self.max_urls_per_depth = max_urls_per_depth
        self.max_per_subdomain = max_per_subdomain
        self.max_page_size_kb = max_page_size_kb
        self.response_timeout_s = response_timeout_s or 20.0
        self.custom_headers = custom_headers or {}
        self.crawl_images = crawl_images
        self.crawl_external = crawl_external
        self.crawl_resource_types = {
            t for t, on in (("css", crawl_css), ("js", crawl_js), ("media", crawl_media)) if on
        }
        self.crawl_hreflang = crawl_hreflang
        self.crawl_amp = crawl_amp
        self.crawl_pagination = crawl_pagination
        self.extract_pdf = extract_pdf
        self.form_auth = form_auth
        self.render_timeout_s = render_timeout_s or 15.0
        self.axe_timeout_s = axe_timeout_s or 10.0
        self.crawl_subdomains = crawl_subdomains
        self.crawl_outside_start_folder = crawl_outside_start_folder
        self.follow_nofollow = follow_nofollow
        self.cdns = [c.strip().lower() for c in (cdns or "").replace("\n", ",").split(",") if c.strip()]
        self.assume_html = assume_html
        self.window_width = window_width or 1024
        self.window_height = window_height or 768
        self.js_error_reporting = js_error_reporting
        self.content_include = content_include or ""
        self.content_exclude = content_exclude or ""
        self.flatten_shadow_dom = flatten_shadow_dom
        self.flatten_iframes = flatten_iframes
        self.extract_srcset = extract_srcset
        self._seed_registrable = ""     # set in crawl_site
        self._seed_folder = ""          # start-folder path prefix
        self.list_mode = list_mode
        self.list_urls = [u for u in (list_urls or []) if u.strip()]
        # List mode only makes sense with a list; an empty one would crawl nothing.
        if self.list_mode and not self.list_urls:
            self.list_mode = False
        # Host of the seed URL — link-target gates stay on-site (an hreflang
        # alternate on another domain must not silently widen the crawl).
        self._seed_netloc = ""
        # Populated by the post-crawl resource sweep; read by do_audit.
        self.resources: List[ResourceRef] = []
        self._depth_counts: Dict[int, int] = {}
        self._subdomain_counts: Dict[str, int] = {}
        # Global token-bucket rate limiter state (shared across workers).
        self._rate_lock = asyncio.Lock()
        self._next_slot = 0.0

        # New globals for site aggregation
        self.external_cache: Dict[str, int] = {}
        self.ai_access: Optional[AIAccessMatrix] = None

        # Live crawl telemetry sink. do_audit points this at active_tasks[crawl_id]
        # so the worker's per-URL progress streams to the /audit/status endpoint.
        self.telemetry: Dict[str, Any] = {}
        # URLs abandoned for blowing the per-URL time budget (reported, not hidden).
        self.timed_out_urls: List[str] = []

        self.mobile_ua = "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/W.X.Y.Z Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"  # noqa: E501
        self.mobile_viewport = {"width": 412, "height": 915}

    # Two-part public suffixes so a subdomain crawl of example.co.uk doesn't
    # widen to the whole .co.uk. Not exhaustive — covers the common cases.
    _MULTI_TLD = frozenset({
        "co.uk", "org.uk", "gov.uk", "ac.uk", "co.jp", "com.au", "net.au",
        "org.au", "co.nz", "co.za", "com.br", "com.mx", "co.in", "com.sg",
    })

    def _registrable(self, host: str) -> str:
        """Best-effort registrable domain (example.com / example.co.uk)."""
        labels = (host or "").lower().split(".")
        if len(labels) <= 2:
            return host.lower()
        if ".".join(labels[-2:]) in self._MULTI_TLD and len(labels) >= 3:
            return ".".join(labels[-3:])
        return ".".join(labels[-2:])

    def _in_site_scope(self, url: str) -> bool:
        """Host/folder scope for FOLLOWING a link (SF Spider scope booleans).
        `_in_scope` (include/exclude) is applied separately."""
        parts = urlsplit(url)
        host = parts.netloc.lower()
        if host == self._seed_netloc:
            ok_host = True
        elif self.crawl_subdomains and self._seed_registrable and (
            host == self._seed_registrable or host.endswith("." + self._seed_registrable)
        ):
            ok_host = True                       # a subdomain of the seed
        elif any(host == c or host.endswith("." + c) for c in self.cdns):
            ok_host = True                       # first-party CDN treated as internal
        else:
            ok_host = False
        if not ok_host:
            return False
        # Start-folder scope: stay within the seed's folder unless told to roam.
        if self._seed_folder and not self.crawl_outside_start_folder:
            if not (parts.path or "/").startswith(self._seed_folder):
                return False
        return True

    def _in_scope(self, url: str) -> bool:
        if self.exclude_res and any(r.search(url) for r in self.exclude_res):
            return False
        if self.include_res and not any(r.search(url) for r in self.include_res):
            return False
        return True

    def _url_allowed(self, url: str, depth: int = 0) -> bool:
        """Enforce the numeric crawl limits at enqueue time (0 = unlimited)."""
        if self.max_url_length and len(url) > self.max_url_length:
            return False
        parts = urlsplit(url)
        if self.max_query_params:
            n = len([p for p in parts.query.split("&") if p])
            if n > self.max_query_params:
                return False
        if self.max_folder_depth:
            segs = [s for s in parts.path.split("/") if s]
            if len(segs) > self.max_folder_depth:
                return False
        if self.max_urls_per_depth and self._depth_counts.get(depth, 0) >= self.max_urls_per_depth:
            return False
        if self.max_per_subdomain and self._subdomain_counts.get(parts.netloc, 0) >= self.max_per_subdomain:
            return False
        return True

    def _set_seed_scope(self, url: str) -> None:
        seed = urlsplit(url)
        self._seed_netloc = seed.netloc.lower()
        self._seed_registrable = self._registrable(seed.hostname or seed.netloc)
        path = seed.path or "/"
        self._seed_folder = path if path.endswith("/") else path.rsplit("/", 1)[0] + "/"

    async def _resolve_seed(self, client: httpx.AsyncClient, start_url: str) -> str:
        """Follow the start address to where the site actually lives. When it
        redirects to another host (apex -> www, a new domain), crawl scope moves
        with it; otherwise the crawl would treat every page as external and stop
        after one. Returns the URL robots/sitemaps should be read from."""
        try:
            resp = await self.fetch_raw(client, start_url)
        except Exception:  # noqa: BLE001 (unreachable: let the normal crawl report it)
            return start_url
        if resp is None:
            return start_url
        final = normalize_url(str(resp.url))
        if urlsplit(final).netloc.lower() == urlsplit(start_url).netloc.lower():
            return start_url
        self._set_seed_scope(final)
        self.visited.add(final)
        self.telemetry["seed_redirected_to"] = final
        return final

    @property
    def _enforce_robots(self) -> bool:
        return self.respect_robots and self.robots_mode == "respect"

    async def _robots_for(self, client: httpx.AsyncClient, url: str) -> Protego:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        rp = self._robots.get(origin)
        if rp is None:
            try:
                resp = await self.fetch_raw(client, f"{origin}/robots.txt")
            except Exception:  # noqa: BLE001 (an unreachable robots.txt = no rules)
                resp = None
            rp = Protego.parse(resp.text if resp is not None and resp.status_code == 200 else "")
            self._robots[origin] = rp
        return rp

    async def _robots_allows(self, client: httpx.AsyncClient, url: str) -> bool:
        """False when robots.txt disallows `url` and robots are being respected.
        Blocked URLs are counted (and reported), not crawled."""
        if not self._enforce_robots:
            return True
        rp = await self._robots_for(client, url)
        if rp.can_fetch(url, self.robots_user_agent):
            return True
        self.telemetry["robots_blocked"] = int(self.telemetry.get("robots_blocked", 0)) + 1
        return False

    def _count_enqueue(self, url: str, depth: int) -> None:
        """Bump the per-depth / per-subdomain counters after an enqueue."""
        self._depth_counts[depth] = self._depth_counts.get(depth, 0) + 1
        netloc = urlsplit(url).netloc
        self._subdomain_counts[netloc] = self._subdomain_counts.get(netloc, 0) + 1

    def _gated_link_targets(self, row: Any) -> List[str]:
        """<link rel> targets to follow as pages, per the Pattern A gates.
        Off (SF default) = the reference is still recorded on the row, just not
        queued. Restricted to the seed host so a cross-domain hreflang alternate
        can't silently widen the crawl."""
        out: List[str] = []
        if self.crawl_hreflang:
            # hreflang hrefs are stored raw by the parser — resolve against the page.
            out += [urljoin(row.address, h) for _lang, h in (row.hreflang or []) if h]
        if self.crawl_amp and getattr(row, "amp_url", None):
            out.append(row.amp_url)
        if self.crawl_pagination:
            out += [u for u in (getattr(row, "prev_url", None), getattr(row, "next_url", None)) if u]
        if not self._seed_netloc:
            return out
        return [u for u in out if urlsplit(u).netloc == self._seed_netloc]

    def _rewrite_url(self, url: str) -> str:
        """URL Rewriting pipeline (SF Pattern F) applied to discovered URLs:
        strip Remove-Parameters keys → ordered regex replaces → lowercase.
        Fragments are already dropped by normalize_url unless the fragment-ID
        crawl option keeps them upstream."""
        if self.remove_parameters:
            s = urlsplit(url)
            if s.query:
                kept = [
                    (k, v) for k, v in parse_qsl(s.query, keep_blank_values=True)
                    if k.lower() not in self.remove_parameters
                ]
                url = urlunsplit((s.scheme, s.netloc, s.path, urlencode(kept), s.fragment))
        for pattern, replacement in self.regex_replace:
            url = pattern.sub(replacement, url)
        if self.lowercase_urls:
            url = url.lower()
        return url

    async def _discover_sitemap_urls(
        self, client: httpx.AsyncClient, start_url: str
    ) -> List[str]:
        """Collect page URLs from the site's sitemap(s) (robots.txt + common paths)."""
        base = urlparse(start_url)
        origin = f"{base.scheme}://{base.netloc}"
        candidates: List[str] = []
        resp = await self.fetch_raw(client, f"{origin}/robots.txt")
        if resp and resp.status_code == 200:
            for line in resp.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    candidates.append(line.split(":", 1)[1].strip())
        candidates += [
            origin + p for p in
            ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml", "/sitemap-index.xml")
        ]
        urls: Set[str] = set()
        seen: Set[str] = set()

        async def load(sm_url: str, depth: int = 0) -> None:
            if sm_url in seen or depth > 2 or len(urls) >= self.max_pages * 3:
                return
            seen.add(sm_url)
            r = await self.fetch_raw(client, sm_url)
            if not r or r.status_code != 200:
                return
            locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text, re.I)
            if "<sitemapindex" in r.text.lower():
                for child in locs[:50]:
                    await load(child.strip(), depth + 1)
            else:
                for u in locs:
                    urls.add(normalize_url(u.strip()))

        for c in dict.fromkeys(candidates):
            await load(c)
            if len(urls) >= self.max_pages * 3:
                break
        return list(urls)

    async def _throttle(self) -> None:
        """Global token-bucket: cap fetches at max_requests_per_sec across workers."""
        if not self.max_requests_per_sec:
            return
        interval = 1.0 / self.max_requests_per_sec
        async with self._rate_lock:
            now = time.monotonic()
            wait = self._next_slot - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._next_slot = max(now, self._next_slot) + interval

    def _record_progress(
        self, url: str, depth: int, row: Any, queue_size: int, crawled: int
    ) -> None:
        """Stream one page's result into the live telemetry sink."""
        tel = self.telemetry
        tel["crawled"] = crawled
        tel["discovered"] = len(self.visited)
        tel["queue"] = queue_size
        sc = getattr(row, "status", 0) or 0
        band = "err" if sc == 0 else f"{sc // 100}xx"
        tally = dict(tel.get("status_tally") or {})
        tally[band] = tally.get(band, 0) + 1
        tel["status_tally"] = tally
        entry = {
            "url": url,
            "status": sc,
            "depth": depth,
            "title": (getattr(row, "title", "") or "")[:80],
        }
        # Reassign (atomic dict-set) rather than mutate in place, so the status
        # endpoint reading this dict from another thread never sees a torn list.
        tel["recent"] = [entry] + (tel.get("recent") or [])[:39]
        denom = crawled + queue_size
        tel["progress"] = 10 + int(50 * crawled / denom) if denom else 30

    @retry(  # type: ignore[misc, untyped-decorator]
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=(
            retry_if_exception_type((httpx.RequestError, httpx.TimeoutException))
            | retry_if_result(is_retryable_status)
        ),
        retry_error_callback=_last_result,
    )
    async def fetch_raw(
        self, client: httpx.AsyncClient, url: str, ua: Optional[str] = None
    ) -> Optional[httpx.Response]:
        try:
            h = dict(self.custom_headers)  # SF Config > HTTP Header (Accept-Language, etc.)
            if ua:
                h["User-Agent"] = ua
            response = await client.get(
                url, timeout=self.response_timeout_s, follow_redirects=True, headers=h
            )
            return response
        except httpx.RequestError:
            return None

    async def fetch_head(
        self, client: httpx.AsyncClient, url: str
    ) -> int:
        # No retry, short timeout — outbound-link checks are best-effort and must
        # never stall the crawl on slow/dead external hosts.
        try:
            response = await client.head(url, timeout=4.0, follow_redirects=True)
            return int(response.status_code)
        except Exception:
            return 0

    async def fetch_resource_head(
        self, client: httpx.AsyncClient, url: str
    ) -> tuple[int, str, Optional[int]]:
        """HEAD a sub-resource for status + content-type + size. Falls back to a
        ranged GET when the origin rejects HEAD (405/501). Best-effort, bounded."""
        try:
            r = await client.head(url, timeout=6.0, follow_redirects=True)
            if r.status_code in (405, 501):
                r = await client.get(
                    url, timeout=6.0, follow_redirects=True, headers={"Range": "bytes=0-0"}
                )
            ct = str(r.headers.get("content-type", "")).split(";")[0].strip()
            cl = r.headers.get("content-range") or r.headers.get("content-length")
            size: Optional[int] = None
            if cl:
                try:
                    size = int(str(cl).split("/")[-1]) if "/" in str(cl) else int(cl)
                except ValueError:
                    size = None
            return int(r.status_code), ct, size
        except Exception:
            return 0, "", None

    async def _sweep_resources(
        self, client: httpx.AsyncClient, all_urls: List[Any]
    ) -> None:
        """Collect CSS/JS/media refs across all pages, drop disabled types, then
        HEAD each unique URL for status/type/size. Result → self.resources
        (one ResourceRef per unique URL, with ref_count pages referencing it)."""
        by_url: Dict[str, ResourceRef] = {}
        ref_pages: Dict[str, Set[str]] = {}
        for row in all_urls:
            kept = []
            for r in getattr(row, "resources", []) or []:
                if r.type not in self.crawl_resource_types:
                    continue
                kept.append(r)
                by_url.setdefault(r.url, r)
                ref_pages.setdefault(r.url, set()).add(row.address)
            row.resources = kept  # persisted per-page view honors the gate too

        unique = list(by_url.values())[:1500]  # bound the sweep
        if not unique:
            self.resources = []
            return
        sem = asyncio.Semaphore(20)

        async def _one(ref: Any) -> None:
            async with sem:
                ref.status, ref.content_type, ref.size = await self.fetch_resource_head(
                    client, ref.url
                )

        try:
            await asyncio.wait_for(
                asyncio.gather(*[_one(r) for r in unique], return_exceptions=True),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            pass

        # Propagate resolved status back onto every per-page ref + attach ref_count.
        for row in all_urls:
            for r in row.resources:
                src = by_url.get(r.url)
                if src is not None:
                    r.status, r.content_type, r.size = src.status, src.content_type, src.size
        for r in unique:
            r.ref_count = len(ref_pages.get(r.url, set()))
        self.resources = unique

    async def fetch_rendered(self, page: Page, url: str) -> Optional[str]:
        try:
            # Honor the profile's Render/AJAX timeout (seconds → ms).
            timeout_ms = int(max(1.0, self.render_timeout_s) * 1000)
            await page.goto(url, timeout=timeout_ms, wait_until="networkidle")
            if self.flatten_shadow_dom or self.flatten_iframes:
                await self._flatten_dom(page)
            content = await page.content()
            return str(content) if content else None
        except Exception:
            return None

    async def _flatten_dom(self, page: Page) -> None:
        """Inline shadow-root and same-origin iframe content into the light DOM
        so page.content() captures it (SF "Flatten Shadow DOM" / "Flatten
        iframes"). Cross-origin iframes are inaccessible and left as-is. Best
        effort — never allowed to fail the render."""
        try:
            await page.evaluate(
                """({ shadow, iframes }) => {
                    if (shadow) {
                        document.querySelectorAll('*').forEach((el) => {
                            if (el.shadowRoot) {
                                try {
                                    const h = document.createElement('div');
                                    h.setAttribute('data-flattened-shadow', '');
                                    h.innerHTML = el.shadowRoot.innerHTML;
                                    el.appendChild(h);
                                } catch (e) { /* closed/detached */ }
                            }
                        });
                    }
                    if (iframes) {
                        document.querySelectorAll('iframe').forEach((f) => {
                            try {
                                const doc = f.contentDocument;
                                if (doc && doc.body && f.parentNode) {
                                    const h = document.createElement('div');
                                    h.setAttribute('data-flattened-iframe', '');
                                    h.innerHTML = doc.body.innerHTML;
                                    f.parentNode.insertBefore(h, f.nextSibling);
                                }
                            } catch (e) { /* cross-origin */ }
                        });
                    }
                }""",
                {"shadow": self.flatten_shadow_dom, "iframes": self.flatten_iframes},
            )
        except Exception:
            pass

    async def probe_ai_access(self, client: httpx.AsyncClient, start_url: str) -> None:
        # 1. Parse robots.txt via Protego (direct fetch, no retry).
        base = urlparse(start_url)
        robots_url = f"{base.scheme}://{base.netloc}/robots.txt"
        robots_txt = ""
        try:
            resp = await client.get(robots_url, timeout=6.0, follow_redirects=True)
            robots_txt = resp.text if resp.status_code == 200 else ""
        except Exception:
            pass
        rp = Protego.parse(robots_txt)

        # 2. Live fetch — the 2026 AI-crawler UA matrix (PRD Appendix A).
        uas = {
            "Googlebot": "Googlebot/2.1 (+http://www.google.com/bot.html)",
            "GPTBot": "Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)",
            "OAI-SearchBot": "Mozilla/5.0 (compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot)",  # noqa: E501
            "ChatGPT-User": "Mozilla/5.0 (compatible; ChatGPT-User/1.0; +https://openai.com/bot)",  # noqa: E501
            "ClaudeBot": "Mozilla/5.0 (compatible; ClaudeBot/1.0; +https://anthropic.com/bot)",  # noqa: E501
            "Claude-SearchBot": "Mozilla/5.0 (compatible; Claude-SearchBot/1.0; +https://anthropic.com/bot)",  # noqa: E501
            "PerplexityBot": "Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/bot)",  # noqa: E501
            "CCBot": "CCBot/2.0 (https://commoncrawl.org/faq/)",
            "Google-Extended": "Mozilla/5.0 (compatible; Google-Extended/1.0)",
            "bingbot": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",  # noqa: E501
        }

        # Probe all UAs concurrently with a short timeout and NO retry — this is a
        # best-effort probe, not a critical fetch, so it must never stall the crawl.
        async def _probe_one(bot_name: str, ua: str) -> tuple[str, dict[str, Any]]:
            allowed = rp.can_fetch(start_url, bot_name)
            status = 0
            try:
                r = await client.get(
                    start_url, headers={"User-Agent": ua},
                    timeout=6.0, follow_redirects=True,
                )
                status = r.status_code
            except Exception:
                status = 0
            return bot_name, {
                "robots_allowed": allowed, "live_ok": status == 200, "status": status,
            }

        results = await asyncio.gather(
            *[_probe_one(b, u) for b, u in uas.items()], return_exceptions=False
        )
        self.ai_access = AIAccessMatrix(matrix=dict(results))

    async def measure_agentic(self, page: Page) -> AgenticContext:
        cls_val = 0.0
        try:
            cls_val = await page.evaluate("window._cls || 0")
        except Exception:
            pass

        webmcp_script = """
        () => {
            let links = Array.from(document.querySelectorAll('link[rel="mcp"]'));
            if (links.length > 0) return { "found": true, "href": links[0].href };
            return { "found": false };
        }
        """
        webmcp_result = {"found": False}
        try:
            webmcp_result = await page.evaluate(webmcp_script)
        except Exception:
            pass

        axe_script = """
        async () => {
            if (!window.axe) return [];
            try {
                const results = await window.axe.run();
                return results.violations.map(v => v.id);
            } catch(e) {
                return [];
            }
        }
        """
        axe_violations = []
        # Inject the vendored bundle by CONTENT, never by url=. A url= script tag
        # waits on the network AND on the document firing script onload — which is
        # precisely what hung the crawl on non-HTML documents. Still time-bounded,
        # because axe.run() itself can be slow on a very large DOM.
        axe_src = _axe_source()
        if axe_src:
            try:
                await asyncio.wait_for(
                    page.add_script_tag(content=axe_src), timeout=self.axe_timeout_s
                )
                axe_violations = await asyncio.wait_for(
                    page.evaluate(axe_script), timeout=self.axe_timeout_s
                )
            except Exception:
                pass

        return AgenticContext(
            post_load_cls=float(cls_val),
            webmcp_probe_result=webmcp_result,
            axe_violations=axe_violations
        )

    async def crawl_url(
        self,
        url: str,
        depth: int,
        http_client: httpx.AsyncClient,
        browser: Optional[BrowserContext], # note: this is the playwright browser instance now to create new contexts  # noqa: E501
    ) -> tuple[
        Optional[URLRow],
        List[UrlRenderDiffRow],
        List[ImageRef],
        List[StructuredDataRow],
        str,
        Optional[str],
        Optional[MobileContext],
        Optional[AgenticContext],
    ]:
        if depth > self.max_depth:
            return None, [], [], [], "", None, None, None

        async with self.semaphore:
            await self._throttle()
            start_t = time.time()
            try:
                response = await self.fetch_raw(http_client, url)
            except Exception:
                return None, [], [], [], "", None, None, None

            if response is None:
                return None, [], [], [], "", None, None, None

            ttfb_ms = (time.time() - start_t) * 1000.0

            raw_html = response.text
            status_code = response.status_code
            headers = dict(response.headers)
            content_type = headers.get("content-type")
            fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            requested_url = url
            final_url = str(response.url)

            # Max page size (SF Limits): don't parse a body over the cap.
            if self.max_page_size_kb and len(response.content) > self.max_page_size_kb * 1024:
                return None, [], [], [], "", None, None, None
            # Assume-HTML (SF Advanced): a URL with no Content-Type is treated as
            # HTML and crawled; with the option off we skip parsing such responses.
            if not content_type and not self.assume_html:
                return None, [], [], [], "", None, None, None
            # A link to an image, archive, video or other file is not a page;
            # auditing it as one would flag a "missing title", headings, etc.
            if not is_pdf(content_type, final_url) and not is_page_like(content_type):
                return None, [], [], [], "", None, None, None
            # An internal link that redirects to another site isn't this site's
            # page; don't audit the other site as if it were.
            if (response.history and not self.list_mode
                    and not self._in_site_scope(normalize_url(final_url))):
                self.telemetry["redirected_offsite"] = (
                    int(self.telemetry.get("redirected_offsite", 0)) + 1)
                return None, [], [], [], "", None, None, None

            # PDFs are real indexable documents but the HTML parser would only
            # produce garbage from their bytes — give them their own row builder
            # and skip parsing/rendering entirely.
            if is_pdf(content_type, final_url):
                pdf_row = build_pdf_row(
                    final_url, status_code, headers, response.content,
                    extract_properties=self.extract_pdf,
                )
                pdf_row.requested_url = requested_url
                pdf_row.fetched_at = fetched_at
                pdf_row.ttfb = ttfb_ms
                pdf_row.depth = depth
                if response.history:
                    pdf_row.redirect_chain = [str(r.url) for r in response.history]
                return pdf_row, [], [], [], "", None, None, None

            raw_row, images, sds = parse_html(
                final_url, raw_html, status=status_code, headers=headers,
                content_include=self.content_include,
                content_exclude=self.content_exclude,
            )
            # Resource store gate (Pattern A): drop image refs when images off.
            if not self.crawl_images:
                images = []
                raw_row.images = []
            # Extract images from IMG srcset (SF Advanced): add each responsive
            # candidate as its own image ref so broken/oversized ones are caught.
            elif self.extract_srcset:
                extra: List[ImageRef] = []
                seen_src = {i.src for i in images}
                for img in images:
                    for cand in _srcset_urls(img.srcset, final_url):
                        if cand not in seen_src:
                            seen_src.add(cand)
                            extra.append(ImageRef(
                                src=cand, alt=img.alt, bytes=None, natural_w=None,
                                natural_h=None, rendered_w=None, rendered_h=None,
                                loading=img.loading, is_background=False, srcset=None,
                            ))
                images += extra
                raw_row.images = images

            raw_row.requested_url = requested_url
            raw_row.fetched_at = fetched_at
            raw_row.ttfb = ttfb_ms
            raw_row.content_type = content_type
            raw_row.depth = depth

            if response.history:
                raw_row.redirect_chain = [str(r.url) for r in response.history]

            diffs = []
            rendered_html = None
            mobile_context = None
            agentic_context = None

            # Render sampling: when render_sample > 0, only render the first N pages.
            # Non-HTML documents (XML sitemaps, RSS, JSON, plain text) are recorded
            # with their status/headers but never rendered — Chromium's built-in
            # viewers never fire script onload, which would hang the worker.
            do_render = bool(
                self.render and browser and is_html_document(content_type, self.assume_html)
            )
            if do_render and self.render_sample > 0:
                if self._rendered_count >= self.render_sample:
                    do_render = False
                else:
                    self._rendered_count += 1

            if do_render and browser:
                # 1. Desktop pass (viewport = SF Rendering Window Size).
                desk_ctx = await browser.new_context(
                    user_agent=self.user_agent,
                    viewport={"width": self.window_width, "height": self.window_height},
                )
                try:
                    await desk_ctx.add_init_script("""
                        window._cls = 0;
                        new PerformanceObserver((list) => {
                            for (const entry of list.getEntries()) {
                                if (!entry.hadRecentInput) window._cls += entry.value;
                            }
                        }).observe({type: 'layout-shift', buffered: true});
                        window._lcp = 0;
                        new PerformanceObserver((list) => {
                            const es = list.getEntries();
                            if (es.length) window._lcp = es[es.length - 1].startTime;
                        }).observe({type: 'largest-contentful-paint', buffered: true});
                    """)
                    page = await desk_ctx.new_page()
                    js_errors: List[str] = []
                    page.on("pageerror", lambda e: js_errors.append(str(e)))
                    # JS error reporting (SF): also capture console error/warning lines.
                    if self.js_error_reporting:
                        page.on("console", lambda m: js_errors.append(f"[{m.type}] {m.text}")
                                if m.type in ("error", "warning") else None)
                    ren_start_t = time.time()
                    rendered_html = await self.fetch_rendered(page, final_url)

                    if rendered_html:
                        raw_row.render_ms = (time.time() - ren_start_t) * 1000.0
                        ren_row, _, _ = parse_html(
                            final_url, rendered_html, status=status_code, headers=headers,
                            content_include=self.content_include,
                            content_exclude=self.content_exclude,
                        )
                        diffs = compute_render_diff(final_url, raw_row, ren_row)

                        # Lab Core Web Vitals (LCP in seconds, CLS score).
                        try:
                            raw_row.lcp_s = float(await page.evaluate("(window._lcp || 0) / 1000")) or None
                            raw_row.cls = float(await page.evaluate("window._cls || 0"))
                        except Exception:
                            pass

                        # Agentic (attach any JS errors seen during render for P04).
                        agentic_context = await self.measure_agentic(page)
                        agentic_context.js_errors = js_errors[:10]
                        raw_row.js_errors = js_errors[:20]   # surfaced when reporting is on
                finally:
                    # Always tear the context down. Anything raising between
                    # new_context() and close() would otherwise leak a live browser
                    # context for the rest of the crawl. Closing the context closes
                    # its pages too.
                    try:
                        await desk_ctx.close()
                    except Exception:
                        pass

                # 2. Mobile pass
                mob_ctx = await browser.new_context(
                    user_agent=self.mobile_ua,
                    viewport=self.mobile_viewport,
                    is_mobile=True,
                    has_touch=True
                )
                try:
                    mob_page = await mob_ctx.new_page()
                    blocked_res = set()

                    def on_request_failed(request: Any) -> None:
                        blocked_res.add(request.url)

                    mob_page.on("requestfailed", on_request_failed)

                    mob_html = await self.fetch_rendered(mob_page, final_url)

                    if mob_html:
                        # evaluate mobile JS: tap targets, font sizes, interstitials
                        measure_js = """
                        () => {
                            const vw = window.innerWidth, vh = window.innerHeight;
                            const clickables = Array.from(document.querySelectorAll(
                                'a,button,input,select,textarea,[role=button],[onclick]'));
                            let smallTap = 0;
                            for (const el of clickables) {
                                const r = el.getBoundingClientRect();
                                if (r.width === 0 || r.height === 0) continue;
                                if (r.width < 44 || r.height < 44) smallTap++;
                            }
                            let smallFonts = 0;
                            const textEls = Array.from(document.querySelectorAll(
                                'p,span,li,a,td,div')).slice(0, 800);
                            for (const el of textEls) {
                                if (!el.textContent || !el.textContent.trim()) continue;
                                const fs = parseFloat(getComputedStyle(el).fontSize) || 16;
                                if (fs < 12) smallFonts++;
                            }
                            let interstitial = false;
                            for (const el of Array.from(document.querySelectorAll('*')).slice(0, 1500)) {
                                const cs = getComputedStyle(el);
                                if ((cs.position === 'fixed' || cs.position === 'sticky') &&
                                    cs.display !== 'none' && cs.visibility !== 'hidden') {
                                    const r = el.getBoundingClientRect();
                                    if (r.width >= vw * 0.6 && r.height >= vh * 0.5) { interstitial = true; break; }
                                }
                            }
                            return {
                                smallTapTargets: smallTap,
                                smallFonts: smallFonts,
                                hasInterstitial: interstitial,
                                contentWiderThanViewport: document.documentElement.scrollWidth > vw
                            };
                        }
                        """  # noqa: E501
                        mob_metrics = {"smallTapTargets": 0, "smallFonts": 0, "hasInterstitial": False, "contentWiderThanViewport": False}  # noqa: E501
                        try:
                            mob_metrics = await mob_page.evaluate(measure_js)
                        except Exception:
                            pass

                        # parse mobile html for word count comparison
                        from .parser import parse_html as parse_h
                        mob_row, _, _ = parse_h(final_url, mob_html)

                        mobile_context = MobileContext(
                            mobile_text=mob_row.main_text,
                            mobile_html=mob_html,
                            smallTapTargets=mob_metrics.get("smallTapTargets", 0),
                            contentWiderThanViewport=bool(mob_metrics.get("contentWiderThanViewport", False)),  # noqa: E501
                            blocked_resources=blocked_res,
                            smallFonts=mob_metrics.get("smallFonts", 0),
                            hasInterstitial=bool(mob_metrics.get("hasInterstitial", False)),
                        )
                finally:
                    try:
                        await mob_ctx.close()
                    except Exception:
                        pass

            return raw_row, diffs, images, sds, raw_html, rendered_html, mobile_context, agentic_context  # noqa: E501

    async def crawl_site(  # noqa: C901
        self, start_url: str
    ) -> tuple[
        List[URLRow], List[UrlRenderDiffRow], List[ImageRef], List[StructuredDataRow]
    ]:
        all_urls: List[URLRow] = []
        all_diffs: List[UrlRenderDiffRow] = []
        all_images: List[ImageRef] = []
        all_sds: List[StructuredDataRow] = []
        headers = {"User-Agent": self.user_agent, **self.custom_headers}

        playwright = None
        browser = None

        start_url = normalize_url(to_ascii_url(start_url))
        # Host scope + start folder (e.g. /blog/ for /blog/index.html).
        self._set_seed_scope(start_url)
        queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
        if self.list_mode:
            # The list IS the crawl: seed every supplied URL at depth 0. Include/
            # exclude never applies to list input (SF) — an uploaded URL is
            # deliberate — but the numeric limits still guard the run.
            for lu in self.list_urls[: self.max_pages]:
                nu = normalize_url(lu)
                if nu not in self.visited and self._url_allowed(nu):
                    self.visited.add(nu)
                    queue.put_nowait((nu, 0))
        else:
            queue.put_nowait((start_url, 0))
            self.visited.add(start_url)

        try:
            if self.render:
                playwright = await async_playwright().start()
                browser = await launch_chromium(playwright, headless=True)

            # Web-form auth (SF §12): log in once in a real browser, then crawl
            # with the session cookies. Needs a browser even when JS rendering is
            # off, so launch one just for the login if necessary.
            if self.form_auth and form_auth_configured():
                if not browser:
                    playwright = await async_playwright().start()
                    browser = await launch_chromium(playwright, headless=True)
                cookies = await login_and_get_cookies(browser)
                if cookies:
                    headers["Cookie"] = cookies_to_header(cookies)
                    self.telemetry["authenticated"] = looks_authenticated(cookies)
                    # An authenticated crawler clicks everything — keep it away
                    # from logout/delete/admin so it can't end its own session.
                    # Case-insensitive: ?Action=Logout must be caught too.
                    self.exclude_res += [re.compile(p, re.I) for p in DANGEROUS_PATTERNS]
                else:
                    self.telemetry["authenticated"] = False

            async with httpx.AsyncClient(
                headers=headers, verify=False, max_redirects=self.max_redirects
            ) as client:
                # Probe AI access matrix
                await self.probe_ai_access(client, start_url)

                # The address people type often redirects to another host
                # (example.com -> www.example.com, http -> https). Scope the crawl
                # to where the site actually lives, or it would stop at one page.
                if not self.list_mode:
                    start_url = await self._resolve_seed(client, start_url)

                # Robots.txt (SF Pattern G): respect = enforce; ignore = don't even
                # fetch; ignore_but_report = fetch + record but don't enforce.
                if self.robots_mode != "ignore":
                    rp = await self._robots_for(client, start_url)
                    seed_blocked = not rp.can_fetch(start_url, self.robots_user_agent)
                    self.telemetry["robots_seed_blocked"] = seed_blocked
                    if self._enforce_robots and seed_blocked:
                        return [], [], [], []  # Disallowed by robots.txt

                # Seed the queue from the sitemap when requested (or required for
                # sitemap-only crawls).
                if (self.discover_sitemap or self.sitemap_only) and not self.list_mode:
                    for su in (await self._discover_sitemap_urls(client, start_url))[: self.max_pages]:
                        if (su not in self.visited and self._in_scope(su)
                                and self._url_allowed(su)
                                and await self._robots_allows(client, su)):
                            self.visited.add(su)
                            queue.put_nowait((su, 1))

                # Hard per-URL budget. Every individual await inside crawl_url is
                # meant to be bounded, but a single unbounded one (a browser call
                # with no implicit timeout, a third-party script that never loads)
                # would otherwise park a worker forever and freeze the whole crawl
                # with an empty queue. This is the backstop: a URL that blows its
                # budget is abandoned and the crawl moves on.
                url_budget_s = max(
                    60.0,
                    self.response_timeout_s * 3 + self.render_timeout_s * 2
                    + self.axe_timeout_s * 2 + 30.0,
                )

                stored: Set[str] = set()   # final addresses already recorded

                async def worker() -> None:
                    # Workers wait for work instead of exiting when the queue is
                    # momentarily empty: pages still being fetched by other
                    # workers will add more links. The crawl ends when every
                    # queued URL is done (queue.join below).
                    while True:
                        url, depth = await queue.get()
                        if len(all_urls) >= self.max_pages:  # crawl-budget cap: drain
                            queue.task_done()
                            continue

                        # Show this URL as in-flight for the live "now crawling" view.
                        in_flight = self.telemetry.setdefault("active", [])
                        in_flight.append(url)
                        try:
                            row, diffs, imgs, sds, raw, ren, mob_ctx, ag_ctx = await asyncio.wait_for(
                                self.crawl_url(url, depth, client, browser),
                                timeout=url_budget_s,
                            )
                            final_addr = normalize_url(row.address) if row else ""
                            if row and final_addr in stored:
                                row = None   # a redirect landed on a page we already have
                            if row:
                                stored.add(final_addr)
                                self.visited.add(final_addr)
                                row.mobile_context = mob_ctx
                                row.agentic_context = ag_ctx
                                row.html_render = ren
                                all_urls.append(row)
                                all_diffs.extend(diffs)
                                all_images.extend(imgs)
                                all_sds.extend(sds)

                                # sitemap-only and list mode both check a fixed set of
                                # URLs — neither discovers new ones from the page.
                                _no_discovery = self.sitemap_only or self.list_mode
                                links = [] if _no_discovery else list(row.internal_links)
                                if not _no_discovery:
                                    # Subdomains / first-party CDNs are "external" to
                                    # the parser (different netloc) — pull the ones
                                    # in-scope back in when those options are on.
                                    if self.crawl_subdomains or self.cdns:
                                        links += [e for e in (row.external_links or [])
                                                  if self._in_site_scope(e)]
                                    # SF default skips rel=nofollow links; follow only
                                    # when forced. Build the nofollow set from the row.
                                    if not self.follow_nofollow:
                                        nofollow = {
                                            lr.href for lr in (getattr(row, "links", []) or [])
                                            if any(t in ("nofollow", "sponsored", "ugc") for t in (lr.rel or ()))
                                        }
                                        if nofollow:
                                            links = [ln for ln in links if ln not in nofollow]
                                if self.max_links_per_page:
                                    links = links[: self.max_links_per_page]
                                # hreflang / AMP / pagination targets follow the same
                                # enqueue pipeline, but only when their gate is on.
                                if not _no_discovery:
                                    links = links + self._gated_link_targets(row)
                                for link in links:
                                    # normalize → SF URL-rewriting pipeline (remove
                                    # params / regex replace / lowercase). Fragment
                                    # kept only if the fragment-ID crawl option is on.
                                    base = link if self.crawl_fragment_identifiers else normalize_url(link)
                                    nlink = self._rewrite_url(base)
                                    nd = depth + 1
                                    if (nlink not in self.visited
                                            and nd <= self.max_depth
                                            and self._in_site_scope(nlink)
                                            and self._in_scope(nlink)
                                            and self._url_allowed(nlink, nd)
                                            and await self._robots_allows(client, nlink)):
                                        self.visited.add(nlink)
                                        self._count_enqueue(nlink, nd)
                                        queue.put_nowait((nlink, nd))
                                self._record_progress(
                                    url, depth, row, queue.qsize(), len(all_urls)
                                )
                        except asyncio.TimeoutError:
                            # Surface stalls instead of swallowing them: a silently
                            # dropped URL is indistinguishable from a crawled one,
                            # which is what makes this class of bug hard to spot.
                            self.timed_out_urls.append(url)
                            self.telemetry["timed_out"] = len(self.timed_out_urls)
                        except Exception:
                            pass
                        finally:
                            if url in in_flight:
                                in_flight.remove(url)
                            queue.task_done()

                workers = [asyncio.create_task(worker()) for _ in range(max(1, self.concurrency))]
                await queue.join()
                for w in workers:
                    w.cancel()
                await asyncio.gather(*workers, return_exceptions=True)

                # Final step: resolve external statuses — bounded, high-concurrency,
                # hard-timeout so a site with many slow external hosts can't stall.
                # External links gate (Pattern A): skip the whole HEAD sweep when off.
                ext_urls = (
                    list({link for r in all_urls for link in r.external_links})[:200]
                    if self.crawl_external else []
                )
                sem = asyncio.Semaphore(20)

                async def _head(ex: str) -> tuple[str, int]:
                    async with sem:
                        return ex, await self.fetch_head(client, ex)

                try:
                    results = await asyncio.wait_for(
                        asyncio.gather(*[_head(e) for e in ext_urls], return_exceptions=True),
                        timeout=45.0,
                    )
                    for res in results:
                        if not isinstance(res, BaseException):
                            self.external_cache[res[0]] = res[1]
                except asyncio.TimeoutError:
                    pass

                # Resource sweep (SF Pattern A): HEAD every unique CSS/JS/media a
                # page pulls in, for status/type/size. Gated by crawl_css/js/media.
                await self._sweep_resources(client, all_urls)

        finally:
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()

        return all_urls, all_diffs, all_images, all_sds
