"""Offline tests for the origin-level agentic probes.

Everything is served by an httpx.MockTransport, so the suite is deterministic and
makes no network calls — the probes must be provably correct without depending
on some third-party site keeping its well-known paths stable.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict

import httpx

from sentinelseo.agentic import ProbeStatus, run_agentic_audit
from sentinelseo.agentic.engine import _commerce_signals, detect_commerce
from sentinelseo.agentic.models import Category, level_for
from sentinelseo.agentic.probes import (
    ProbeContext,
    probe_ai_bot_rules,
    probe_content_signals,
    probe_link_headers,
    probe_llms_txt,
    probe_markdown,
    probe_mcp_server_card,
    probe_robots_txt,
    probe_sitemap,
)

ROBOTS_GOOD = """User-Agent: *
Allow: /
Disallow: /admin/

User-Agent: GPTBot
Allow: /

User-Agent: PerplexityBot
Allow: /

Sitemap: https://ex.com/sitemap.xml
"""

SITEMAP = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' \
          "<url><loc>https://ex.com/</loc></url></urlset>"


def _transport(routes: Dict[str, Any]) -> httpx.MockTransport:
    """Map path -> (status, body, headers) | callable. Unlisted paths 404."""
    def handler(request: httpx.Request) -> httpx.Response:
        spec = routes.get(request.url.path)
        if spec is None:
            return httpx.Response(404, text="<html>not found</html>",
                                  headers={"content-type": "text/html"})
        if callable(spec):
            return spec(request)
        status, body, headers = spec
        return httpx.Response(status, text=body, headers=headers)
    return httpx.MockTransport(handler)


def _run(probe: Callable[..., Any], routes: Dict[str, Any],
         *args: Any, origin: str = "https://ex.com") -> Any:
    async def go() -> Any:
        async with httpx.AsyncClient(transport=_transport(routes)) as c:
            ctx = ProbeContext(origin, c, timeout=5)
            return await probe(ctx, *args)
    return asyncio.run(go())


TEXT = {"content-type": "text/plain"}
XML = {"content-type": "application/xml"}
JSON_H = {"content-type": "application/json"}
HTML = {"content-type": "text/html"}


class TestRobotsAndSitemap:
    def test_robots_pass(self) -> None:
        r = _run(probe_robots_txt, {"/robots.txt": (200, ROBOTS_GOOD, TEXT)})
        assert r.status is ProbeStatus.PASS
        assert "valid format" in r.conclusion

    def test_robots_missing_fails_with_remediation(self) -> None:
        r = _run(probe_robots_txt, {})
        assert r.status is ProbeStatus.FAIL
        assert r.remediation, "a failure must always tell the user what to do"

    def test_robots_without_user_agent_fails(self) -> None:
        r = _run(probe_robots_txt, {"/robots.txt": (200, "# nothing here", TEXT)})
        assert r.status is ProbeStatus.FAIL

    def test_sitemap_found_via_robots_directive(self) -> None:
        r = _run(probe_sitemap, {"/robots.txt": (200, ROBOTS_GOOD, TEXT),
                                 "/sitemap.xml": (200, SITEMAP, XML)})
        assert r.status is ProbeStatus.PASS
        assert r.evidence["declared_in_robots"] is True
        assert r.evidence["type"] == "urlset"

    def test_sitemap_falls_back_to_conventional_path(self) -> None:
        r = _run(probe_sitemap, {"/robots.txt": (200, "User-Agent: *\n", TEXT),
                                 "/sitemap.xml": (200, SITEMAP, XML)})
        assert r.status is ProbeStatus.PASS
        assert r.evidence["declared_in_robots"] is False

    def test_sitemap_rejects_html_masquerading_as_sitemap(self) -> None:
        r = _run(probe_sitemap, {"/robots.txt": (200, "User-Agent: *\n", TEXT),
                                 "/sitemap.xml": (200, "<html>oops</html>", HTML)})
        assert r.status is ProbeStatus.FAIL

    def test_sitemap_index_is_valid(self) -> None:
        idx = '<?xml version="1.0"?><sitemapindex><sitemap><loc>https://ex.com/s1.xml</loc></sitemap></sitemapindex>'
        r = _run(probe_sitemap, {"/robots.txt": (200, "User-Agent: *\n", TEXT),
                                 "/sitemap.xml": (200, idx, XML)})
        assert r.status is ProbeStatus.PASS
        assert r.evidence["type"] == "index"


class TestAIBotRules:
    def test_detects_named_ai_bots(self) -> None:
        r = _run(probe_ai_bot_rules, {"/robots.txt": (200, ROBOTS_GOOD, TEXT)})
        assert r.status is ProbeStatus.PASS
        assert set(r.evidence["bots"]) == {"gptbot", "perplexitybot"}

    def test_generic_wildcard_only_is_not_enough(self) -> None:
        r = _run(probe_ai_bot_rules,
                 {"/robots.txt": (200, "User-Agent: *\nAllow: /\n", TEXT)})
        assert r.status is ProbeStatus.FAIL

    def test_googlebot_alone_does_not_count_as_an_ai_bot(self) -> None:
        r = _run(probe_ai_bot_rules,
                 {"/robots.txt": (200, "User-Agent: Googlebot\nAllow: /\n", TEXT)})
        assert r.status is ProbeStatus.FAIL


class TestContentSignals:
    def test_parses_signals(self) -> None:
        body = "User-Agent: *\nContent-Signal: search=yes, ai-train=no, ai-input=yes\nAllow: /\n"
        r = _run(probe_content_signals, {"/robots.txt": (200, body, TEXT)})
        assert r.status is ProbeStatus.PASS
        assert r.evidence["signals"] == {
            "search": "yes", "ai-train": "no", "ai-input": "yes"}

    def test_absent_signals_fail(self) -> None:
        r = _run(probe_content_signals, {"/robots.txt": (200, ROBOTS_GOOD, TEXT)})
        assert r.status is ProbeStatus.FAIL

    def test_ignores_unknown_signal_keys(self) -> None:
        body = "Content-Signal: search=yes, bogus=maybe\n"
        r = _run(probe_content_signals, {"/robots.txt": (200, body, TEXT)})
        assert r.evidence["signals"] == {"search": "yes"}


class TestLinkHeaders:
    def test_parses_rel_values(self) -> None:
        hdr = {"content-type": "text/html",
               "link": '</.well-known/api-catalog>; rel="api-catalog", '
                       '</docs>; rel="service-doc"'}
        r = _run(probe_link_headers, {"/": (200, "<html></html>", hdr)})
        assert r.status is ProbeStatus.PASS
        assert r.evidence["rels"] == ["api-catalog", "service-doc"]

    def test_absent_link_header_fails(self) -> None:
        r = _run(probe_link_headers, {"/": (200, "<html></html>", HTML)})
        assert r.status is ProbeStatus.FAIL


class TestMarkdownNegotiation:
    def test_markdown_served_passes(self) -> None:
        def h(req: httpx.Request) -> httpx.Response:
            if req.headers.get("accept") == "text/markdown":
                return httpx.Response(200, text="# Hi",
                                      headers={"content-type": "text/markdown",
                                               "x-markdown-tokens": "42"})
            return httpx.Response(200, text="<html/>", headers=HTML)
        r = _run(probe_markdown, {"/": h})
        assert r.status is ProbeStatus.PASS
        assert r.evidence["tokens"] == "42"

    def test_html_only_fails(self) -> None:
        r = _run(probe_markdown, {"/": (200, "<html/>", HTML)})
        assert r.status is ProbeStatus.FAIL


class TestLlmsTxt:
    def test_structured_llms_txt_passes(self) -> None:
        body = "# Example\n\n> Summary\n\n## Docs\n- [Guide](https://ex.com/g): how to\n"
        r = _run(probe_llms_txt, {"/llms.txt": (200, body, TEXT)})
        assert r.status is ProbeStatus.PASS
        assert r.evidence["links"] == 1

    def test_missing_fails(self) -> None:
        assert _run(probe_llms_txt, {}).status is ProbeStatus.FAIL

    def test_present_but_malformed_fails(self) -> None:
        r = _run(probe_llms_txt, {"/llms.txt": (200, "just some prose", TEXT)})
        assert r.status is ProbeStatus.FAIL


class TestMcpServerCard:
    def test_found_at_primary_path(self) -> None:
        card = json.dumps({"serverInfo": {"name": "x", "version": "1"}})
        r = _run(probe_mcp_server_card,
                 {"/.well-known/mcp/server-card.json": (200, card, JSON_H)})
        assert r.status is ProbeStatus.PASS

    def test_falls_back_to_alternate_path(self) -> None:
        """Emerging specs move their paths; the probe must follow."""
        card = json.dumps({"serverInfo": {"name": "x"}})
        r = _run(probe_mcp_server_card, {"/.well-known/mcp.json": (200, card, JSON_H)})
        assert r.status is ProbeStatus.PASS
        assert r.evidence["path"] == "/.well-known/mcp.json"

    def test_html_404_page_is_not_a_card(self) -> None:
        """A SPA returning 200 HTML for unknown paths must not read as a pass."""
        r = _run(probe_mcp_server_card,
                 {"/.well-known/mcp/server-card.json": (200, "<html>404</html>", HTML)})
        assert r.status is ProbeStatus.FAIL


class TestCommerceDetection:
    def test_service_offer_is_not_commerce(self) -> None:
        """A consultancy pricing a Service must not trip commerce probes."""
        html = ('{"@type":"Offer","itemOffered":{"@type":"Service",'
                '"name":"SEO retainer"},"price":"750"}')
        assert _commerce_signals(html) == []

    def test_platform_names_as_page_copy_are_not_commerce(self) -> None:
        """Listing platforms you work with is not running a store."""
        html = "<span>WordPress</span><span>Shopify</span><span>WooCommerce</span>"
        assert _commerce_signals(html) == []

    def test_platform_runtime_is_commerce(self) -> None:
        assert "ecommerce_platform_runtime" in _commerce_signals(
            '<script src="https://cdn.shopify.com/s/files/1/x.js"></script>')

    def test_woocommerce_plugin_path_is_commerce(self) -> None:
        assert "ecommerce_platform_runtime" in _commerce_signals(
            '<link href="/wp-content/plugins/woocommerce/assets/css/woocommerce.css">')

    def test_cart_route_is_commerce(self) -> None:
        assert "cart_or_checkout_route" in _commerce_signals('<a href="/cart">Cart</a>')

    def test_add_to_cart_control_is_commerce(self) -> None:
        assert "cart_or_checkout_route" in _commerce_signals(
            '<button>Add to Cart</button>')

    def test_product_schema_is_commerce(self) -> None:
        assert "schema_org_product" in _commerce_signals('{"@type":"Product"}')

    def test_detect_commerce_over_http(self) -> None:
        async def go() -> bool:
            routes = {"/": (200, '<a href="/checkout">Buy</a>', HTML)}
            async with httpx.AsyncClient(transport=_transport(routes)) as c:
                return await detect_commerce(ProbeContext("https://ex.com", c))
        assert asyncio.run(go()) is True


class TestScoringAndLevels:
    def test_level_bands_are_monotonic(self) -> None:
        assert level_for(0)[0] == "Level 0"
        assert level_for(25)[0] == "Level 1"
        assert level_for(50)[0] == "Level 2"
        assert level_for(100)[0] == "Level 5"

    def test_info_and_na_never_affect_the_score(self) -> None:
        """A content site must not be marked down for lacking payment rails."""
        async def go() -> Any:
            routes = {"/robots.txt": (200, ROBOTS_GOOD, TEXT),
                      "/sitemap.xml": (200, SITEMAP, XML),
                      "/": (200, "<html>a blog</html>", HTML)}
            async with httpx.AsyncClient(transport=_transport(routes)) as c:
                return await run_agentic_audit("https://ex.com", client=c, browser=None)
        rep = asyncio.run(go())
        assert rep.is_commerce is False
        commerce = [r for r in rep.results if r.category is Category.COMMERCE]
        assert commerce and all(
            r.status is ProbeStatus.NOT_APPLICABLE for r in commerce)
        assert all(not r.status.scores for r in commerce)
        # robots + sitemap + ai-bot-rules pass
        assert rep.score > 0


class TestFullRun:
    def _report(self, routes: Dict[str, Any]) -> Any:
        async def go() -> Any:
            async with httpx.AsyncClient(transport=_transport(routes)) as c:
                return await run_agentic_audit("https://ex.com", client=c, browser=None)
        return asyncio.run(go())

    def test_runs_every_probe_and_records_evidence(self) -> None:
        rep = self._report({"/robots.txt": (200, ROBOTS_GOOD, TEXT),
                            "/sitemap.xml": (200, SITEMAP, XML),
                            "/": (200, "<html/>", HTML)})
        assert len(rep.results) >= 20, "all probes must report, pass or fail"
        assert all(r.steps for r in rep.results), "every probe needs an audit trail"
        assert all(r.probe_id.startswith("AGT.") for r in rep.results)

    def test_every_failure_carries_remediation(self) -> None:
        rep = self._report({"/": (200, "<html/>", HTML)})
        for r in rep.failures:
            assert r.remediation, f"{r.probe_id} fails with no remediation"

    def test_probe_ids_are_unique(self) -> None:
        rep = self._report({"/": (200, "<html/>", HTML)})
        ids = [r.probe_id for r in rep.results]
        assert len(ids) == len(set(ids))

    def test_serialises_to_dict(self) -> None:
        d = self._report({"/": (200, "<html/>", HTML)}).to_dict()
        for key in ("origin", "score", "level", "categories", "results"):
            assert key in d
        assert isinstance(d["score"], int) and 0 <= d["score"] <= 100

    def test_dead_origin_degrades_instead_of_raising(self) -> None:
        """An origin that answers nothing must still produce a usable report."""
        def dead(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("unreachable")

        async def go() -> Any:
            async with httpx.AsyncClient(transport=httpx.MockTransport(dead)) as c:
                return await run_agentic_audit("https://down.example",
                                               client=c, browser=None)
        rep = asyncio.run(go())
        assert rep.results, "must still return probe results"
        assert rep.score == 0

    def test_webmcp_without_browser_is_error_not_crash(self) -> None:
        rep = self._report({"/": (200, "<html/>", HTML)})
        webmcp = [r for r in rep.results if r.probe_id == "AGT.WEBMCP"]
        assert webmcp and webmcp[0].status is ProbeStatus.ERROR
        assert not webmcp[0].status.scores


class TestUnreachableVersusAbsent:
    """"The server said 404" and "we never got a reply" are different findings.

    Reporting an unreachable origin as a confident FAIL would tell users to go
    build something they may already have.
    """

    def _probe(self, handler: Any) -> Any:
        async def go() -> Any:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
                ctx = ProbeContext("https://ex.com", c, timeout=2)
                return await probe_mcp_server_card(ctx)
        return asyncio.run(go())

    def test_real_404_is_a_fail(self) -> None:
        def h(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="nope")
        r = self._probe(h)
        assert r.status is ProbeStatus.FAIL
        assert r.remediation

    def test_unreachable_origin_is_an_error_not_a_fail(self) -> None:
        def h(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("unreachable")
        r = self._probe(h)
        assert r.status is ProbeStatus.ERROR
        assert "reach" in r.conclusion.lower()

    def test_unreachable_does_not_count_against_the_score(self) -> None:
        def h(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("unreachable")
        assert self._probe(h).status.scores is False


class TestHomepageIsFetchedOnce:
    """Several probes reason about `/`; fetching it per probe timed out slow
    origins and turned real results into spurious errors."""

    def test_homepage_is_cached_across_probes(self) -> None:
        calls = {"n": 0}

        def h(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/":
                calls["n"] += 1
            return httpx.Response(200, text="<html/>", headers=HTML)

        async def go() -> None:
            async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
                ctx = ProbeContext("https://ex.com", c, timeout=2)
                await ctx.homepage()
                await ctx.homepage()
                await ctx.homepage()
        asyncio.run(go())
        assert calls["n"] == 1, f"homepage fetched {calls['n']}x, expected 1"

    def test_concurrent_callers_still_fetch_once(self) -> None:
        calls = {"n": 0}

        def h(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/":
                calls["n"] += 1
            return httpx.Response(200, text="<html/>", headers=HTML)

        async def go() -> None:
            async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
                ctx = ProbeContext("https://ex.com", c, timeout=2)
                await asyncio.gather(*[ctx.homepage() for _ in range(6)])
        asyncio.run(go())
        assert calls["n"] == 1


class TestNoSecretLeakage:
    """Invariant I5: probe evidence must never carry credentials."""

    def test_set_cookie_and_auth_headers_are_not_recorded(self) -> None:
        routes = {"/robots.txt": (200, ROBOTS_GOOD,
                                  {"content-type": "text/plain",
                                   "set-cookie": "session=SUPERSECRET; Path=/",
                                   "authorization": "Bearer TOPSECRET"})}
        r = _run(probe_robots_txt, routes)
        blob = json.dumps(r.to_dict())
        assert "SUPERSECRET" not in blob
        assert "TOPSECRET" not in blob
        assert "set-cookie" not in blob.lower()
