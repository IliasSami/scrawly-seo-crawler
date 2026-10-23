"""robots.txt / sitemap / llms.txt probes must not turn a dropped connection into
"file not found".

Origins behind a WAF (Imunify360, ModSecurity) often refuse connections for a
few seconds right after a crawl burst. The probes then got no reply at all and
reported FAIL "No valid sitemap found" for a site whose robots.txt-declared
sitemap was valid — telling the user to build something they already have.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable

import httpx

from sentinelseo.agentic import ProbeStatus
from sentinelseo.agentic.probes import (
    ProbeContext,
    probe_ai_bot_rules,
    probe_content_signals,
    probe_llms_txt,
    probe_robots_txt,
    probe_sitemap,
)

ROBOTS = "User-agent: *\nAllow: /\n\nSitemap: https://ex.com/sitemap_index.xml\n"
INDEX = ('<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/'
         'sitemap/0.9"><sitemap><loc>https://ex.com/page-sitemap.xml</loc></sitemap>'
         "</sitemapindex>")


def _run(probe: Callable[..., Any], handler: Any) -> Any:
    async def go() -> Any:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await probe(ProbeContext("https://ex.com", c, timeout=2))
    return asyncio.run(go())


def _down(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused")


def test_every_file_probe_reports_error_when_origin_is_down() -> None:
    for probe in (probe_robots_txt, probe_sitemap, probe_llms_txt,
                  probe_ai_bot_rules, probe_content_signals):
        r = _run(probe, _down)
        assert r.status is ProbeStatus.ERROR, probe.__name__
        assert r.status.scores is False, probe.__name__


def test_sitemap_declared_in_robots_but_fetch_drops_is_error_not_fail() -> None:
    def h(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        raise httpx.ConnectError("connection refused")
    r = _run(probe_sitemap, h)
    assert r.status is ProbeStatus.ERROR


def test_one_transient_drop_is_retried() -> None:
    calls = {"index": 0}

    def h(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        if request.url.path == "/sitemap_index.xml":
            calls["index"] += 1
            if calls["index"] == 1:
                raise httpx.ConnectError("connection reset")
            return httpx.Response(200, text=INDEX)
        return httpx.Response(404)
    r = _run(probe_sitemap, h)
    assert r.status is ProbeStatus.PASS
    assert calls["index"] == 2


def test_real_404_is_still_a_fail() -> None:
    def h(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="nope")
    assert _run(probe_sitemap, h).status is ProbeStatus.FAIL
    assert _run(probe_llms_txt, h).status is ProbeStatus.FAIL
