"""Crawler robustness regressions (all offline: httpx MockTransport, no network).

Each test pins a bug found in the pre-release audit:
- robots.txt was only checked for the start URL (Invariant I7);
- 5xx pages vanished, and a failing robots.txt aborted the whole audit;
- a start address that redirects to another host (apex -> www) or a Unicode
  (IDN) address crawled a single page;
- the worker pool collapsed to one fetch at a time;
- linked files (images) and links redirecting off-site were audited as pages;
- javascript:/sms: links were treated as crawlable URLs.
"""
import asyncio
from typing import Any, Awaitable, Callable, Dict, List, Tuple

import httpx
import pytest
from tenacity import wait_none

from sentinelseo.crawl import fetcher as F
from sentinelseo.crawl.parser import parse_html

Handler = Callable[[httpx.Request], Awaitable[httpx.Response]]


def _page(title: str, links: str = "") -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"},
                          text=f"<html><head><title>{title}</title></head><body>{links}</body></html>")


@pytest.fixture(autouse=True)
def _fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tenacity's retry policy but drop its back-off sleeps."""
    monkeypatch.setattr(F.Crawler, "fetch_raw", F.Crawler.fetch_raw.retry_with(wait=wait_none()))


def _run(handler: Handler, start: str, **kw: Any) -> Tuple[List[Any], F.Crawler]:
    orig = httpx.AsyncClient

    class _Mocked(orig):  # type: ignore[misc, valid-type]
        def __init__(self, *a: Any, **k: Any) -> None:
            k["transport"] = httpx.MockTransport(handler)
            super().__init__(*a, **k)

    F.httpx.AsyncClient = _Mocked  # type: ignore[misc, attr-defined]
    try:
        opts: Dict[str, Any] = {"render": False, "concurrency": 4, "max_depth": 3,
                                "discover_sitemap": False}
        opts.update(kw)
        crawler = F.Crawler(**opts)
        urls, *_ = asyncio.run(crawler.crawl_site(start))
        return urls, crawler
    finally:
        F.httpx.AsyncClient = orig  # type: ignore[misc, attr-defined]


def _addresses(urls: List[Any]) -> Dict[str, int]:
    return {u.address: u.status for u in urls}


def _site(robots: httpx.Response | None = None) -> Handler:
    async def handler(req: httpx.Request) -> httpx.Response:
        p = req.url.path
        if p == "/robots.txt":
            return robots or httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
        if p == "/":
            return _page("Home", '<a href="/private/x">p</a><a href="/err">e</a><a href="/ok">o</a>')
        if p == "/err":
            return httpx.Response(500, headers={"content-type": "text/html"},
                                  text="<html><title>boom</title></html>")
        return _page(p)
    return handler


def test_robots_disallow_applies_to_discovered_links() -> None:
    urls, crawler = _run(_site(), "http://example.test/")
    found = _addresses(urls)
    assert "http://example.test/ok" in found
    assert not any("/private" in a for a in found)
    assert crawler.telemetry.get("robots_blocked", 0) >= 1


def test_robots_can_be_ignored() -> None:
    urls, _ = _run(_site(), "http://example.test/", respect_robots=False)
    assert "http://example.test/private/x" in _addresses(urls)


def test_server_errors_are_recorded_not_dropped() -> None:
    urls, _ = _run(_site(), "http://example.test/")
    assert _addresses(urls).get("http://example.test/err") == 500


def test_failing_robots_txt_does_not_abort_the_audit() -> None:
    urls, _ = _run(_site(robots=httpx.Response(503, text="busy")), "http://example.test/")
    found = _addresses(urls)
    assert found.get("http://example.test/") == 200
    assert "http://example.test/ok" in found


def test_start_address_redirecting_to_www_crawls_the_site() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "example.test":
            return httpx.Response(301, headers={"location": f"http://www.example.test{req.url.path}"})
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.path == "/":
            return _page("Home", '<a href="/a">a</a><a href="/b">b</a>')
        return _page(req.url.path)

    urls, crawler = _run(handler, "http://example.test/")
    found = _addresses(urls)
    assert {"http://www.example.test/a", "http://www.example.test/b"} <= set(found)
    assert crawler.telemetry.get("seed_redirected_to") == "http://www.example.test/"


def test_unicode_domain_is_crawled() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.path == "/":
            return _page("Start", '<a href="/seite">s</a>')
        return _page(req.url.path)

    urls, _ = _run(handler, "http://bücher.test/")
    assert "http://xn--bcher-kva.test/seite" in _addresses(urls)


def test_linked_files_and_offsite_redirects_are_not_pages() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "other.test":
            return _page("Elsewhere")
        p = req.url.path
        if p == "/robots.txt":
            return httpx.Response(404)
        if p == "/":
            return _page("Home", '<a href="/photo.png">img</a><a href="/go">go</a><a href="/ok">ok</a>')
        if p == "/photo.png":
            return httpx.Response(200, headers={"content-type": "image/png"}, content=b"\x89PNG....")
        if p == "/go":
            return httpx.Response(302, headers={"location": "http://other.test/landing"})
        return _page(p)

    urls, crawler = _run(handler, "http://example.test/")
    found = _addresses(urls)
    assert "http://example.test/ok" in found
    assert "http://example.test/photo.png" not in found
    assert not any("other.test" in a for a in found)
    assert crawler.telemetry.get("redirected_offsite") == 1


def test_redirect_to_known_page_is_not_duplicated() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        p = req.url.path
        if p == "/robots.txt":
            return httpx.Response(404)
        if p == "/":
            return _page("Home", '<a href="/old">old</a><a href="/new">new</a>')
        if p == "/old":
            return httpx.Response(301, headers={"location": "http://example.test/new"})
        return _page(p)

    urls, _ = _run(handler, "http://example.test/")
    assert [u.address for u in urls].count("http://example.test/new") == 1


def test_workers_fetch_in_parallel() -> None:
    # Distinct pages in flight (one page may issue several requests itself).
    active: Dict[str, int] = {}
    state = {"peak": 0}

    async def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.path == "/":
            await asyncio.sleep(0.02)   # a real fetch yields: idle workers look meanwhile
            return _page("Home", "".join(f'<a href="/p{i}">p</a>' for i in range(12)))
        # Count only the crawl's own page fetches (not robots / AI-access probes).
        path = req.url.path
        active[path] = active.get(path, 0) + 1
        state["peak"] = max(state["peak"], len(active))
        await asyncio.sleep(0.02)
        active[path] -= 1
        if not active[path]:
            del active[path]
        return _page(path)

    urls, _ = _run(handler, "http://example.test/", concurrency=6)
    assert len(urls) == 13
    assert state["peak"] > 1


def test_crawl_respects_page_budget() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return _page(req.url.path, "".join(f'<a href="/p{i}">p</a>' for i in range(30)))

    urls, _ = _run(handler, "http://example.test/", max_pages=5)
    assert len(urls) <= 5 + 4   # in-flight pages may finish after the cap is hit


@pytest.mark.parametrize("href", ["JavaScript:void(0)", " mailto:a@b.co", "sms:+100", "whatsapp://send",
                                  "tel:123", "data:text/plain,hi"])
def test_non_web_links_are_not_crawlable(href: str) -> None:
    row, _, _ = parse_html("https://example.test/", f'<html><body><a href="{href}">x</a></body></html>',
                           status=200, headers={})
    assert not row.internal_links
    assert not row.external_links


def test_page_like_content_types() -> None:
    assert F.is_page_like("text/html; charset=utf-8")
    assert F.is_page_like("application/xhtml+xml")
    assert F.is_page_like("application/rss+xml")
    assert F.is_page_like(None)
    assert not F.is_page_like("image/png")
    assert not F.is_page_like("application/zip")
    assert not F.is_page_like("video/mp4")
