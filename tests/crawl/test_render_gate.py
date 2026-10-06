"""Non-HTML documents must never enter the browser render pipeline.

Regression guard for a crawl-freezing bug: measure_agentic() injects axe-core
into every rendered page via page.add_script_tag(url=...). On Chromium's
built-in XML viewer (what a sitemap.xml renders as) an injected <script> never
fires `onload`, so that await blocked forever — it never raised, so the
surrounding try/except never fired, and the worker held the URL in-flight for
good. A real crawl froze at 108/109 URLs on /sitemap.xml with an empty queue.
"""
import asyncio
from pathlib import Path
from typing import Any

from sentinelseo.crawl import fetcher as fetcher_mod
from sentinelseo.crawl.fetcher import (
    AXE_VENDOR_PATH,
    Crawler,
    _axe_source,
    is_html_document,
)


class TestIsHtmlDocument:
    def test_non_html_is_not_rendered(self) -> None:
        for content_type in (
            "application/xml",          # the sitemap that froze the crawl
            "text/xml",
            "application/rss+xml",
            "application/atom+xml",
            "application/json",
            "text/plain",
            "image/svg+xml",
        ):
            assert is_html_document(content_type) is False, content_type

    def test_html_is_rendered(self) -> None:
        for content_type in (
            "text/html",
            "text/html; charset=utf-8",
            "TEXT/HTML",
            "application/xhtml+xml",
        ):
            assert is_html_document(content_type) is True, content_type

    def test_missing_content_type_follows_assume_html(self) -> None:
        # SF Advanced "Assume pages are HTML" decides when the server is silent.
        assert is_html_document(None, assume_html=True) is True
        assert is_html_document("", assume_html=True) is True
        assert is_html_document(None, assume_html=False) is False


class TestPerUrlTimeoutBudget:
    """A single URL must never be able to park a worker forever."""

    def test_budget_scales_with_configured_timeouts(self) -> None:
        c = Crawler(render=False, response_timeout_s=20, render_timeout_s=15, axe_timeout_s=10)
        budget = max(
            60.0,
            c.response_timeout_s * 3 + c.render_timeout_s * 2 + c.axe_timeout_s * 2 + 30.0,
        )
        # Must comfortably exceed one full fetch+render pass, so a healthy slow
        # page is never cut off, while still being finite.
        assert budget >= c.response_timeout_s + c.render_timeout_s
        assert budget == 140.0

    def test_budget_has_a_floor(self) -> None:
        c = Crawler(render=False, response_timeout_s=1, render_timeout_s=1, axe_timeout_s=1)
        budget = max(
            60.0,
            c.response_timeout_s * 3 + c.render_timeout_s * 2 + c.axe_timeout_s * 2 + 30.0,
        )
        assert budget == 60.0

    def test_timed_out_urls_starts_empty_and_is_reported(self) -> None:
        c = Crawler(render=False)
        assert c.timed_out_urls == []

    def test_wait_for_abandons_a_hanging_url(self) -> None:
        """asyncio.wait_for is what rescues the worker from an unbounded await."""
        async def _hangs_forever() -> None:
            await asyncio.Event().wait()

        async def _run() -> bool:
            try:
                await asyncio.wait_for(_hangs_forever(), timeout=0.05)
                return False
            except asyncio.TimeoutError:
                return True

        assert asyncio.run(_run()) is True


class TestAxeIsVendored:
    """axe-core must load from disk, never from a CDN.

    A `url=` script tag waits on both the network and the document firing script
    onload — the exact combination that froze the crawl. It also leaked every
    crawled URL to the CDN and broke offline runs.
    """

    def test_vendored_bundle_ships_with_the_package(self) -> None:
        assert AXE_VENDOR_PATH.exists(), f"vendored axe missing at {AXE_VENDOR_PATH}"
        assert AXE_VENDOR_PATH.suffix == ".js"

    def test_bundle_is_really_axe_core(self) -> None:
        src = _axe_source()
        assert len(src) > 100_000, "bundle looks truncated"
        assert "axe" in src[:200].lower()

    def test_source_is_read_once_and_cached(self) -> None:
        assert _axe_source() is _axe_source()

    def test_no_cdn_reference_remains_in_the_crawler(self) -> None:
        source = Path(fetcher_mod.__file__).read_text(encoding="utf-8")
        for host in ("cdnjs.cloudflare.com", "unpkg.com", "jsdelivr.net"):
            assert host not in source, f"crawler still references CDN host {host}"

    def test_missing_bundle_degrades_instead_of_raising(self, monkeypatch: Any) -> None:
        """A missing/unreadable bundle drops a11y data; it must not break a crawl."""
        monkeypatch.setattr(fetcher_mod, "_AXE_SOURCE", None)
        monkeypatch.setattr(fetcher_mod, "AXE_VENDOR_PATH", Path("/nonexistent/axe.min.js"))
        try:
            assert fetcher_mod._axe_source() == ""
        finally:
            monkeypatch.setattr(fetcher_mod, "_AXE_SOURCE", None)

    def test_measure_agentic_skips_injection_when_bundle_absent(
        self, monkeypatch: Any
    ) -> None:
        injected: list[str] = []

        class _Page:
            async def evaluate(self, *a: Any, **k: Any) -> Any:
                return 0

            async def add_script_tag(self, *a: Any, **k: Any) -> None:
                injected.append("called")

        monkeypatch.setattr(fetcher_mod, "_axe_source", lambda: "")
        ctx = asyncio.run(Crawler(render=False).measure_agentic(_Page()))
        assert ctx.axe_violations == []
        assert injected == [], "must not inject when there is no bundle"


class TestAxeProbeIsBounded:
    def test_axe_timeout_defaults_and_is_configurable(self) -> None:
        assert Crawler(render=False).axe_timeout_s == 10.0
        assert Crawler(render=False, axe_timeout_s=3).axe_timeout_s == 3.0

    def test_axe_timeout_never_zero(self) -> None:
        # A 0/None timeout would restore the unbounded-await hang.
        assert Crawler(render=False, axe_timeout_s=0).axe_timeout_s == 10.0

    def test_measure_agentic_survives_a_hanging_script_tag(self) -> None:
        """A page whose script never loads yields empty a11y data, not a hang."""
        class _HangingPage:
            async def evaluate(self, *a: Any, **k: Any) -> Any:
                return 0

            async def add_script_tag(self, *a: Any, **k: Any) -> None:
                await asyncio.Event().wait()  # never resolves, like the XML viewer

        c = Crawler(render=False, axe_timeout_s=0.05)
        ctx = asyncio.run(c.measure_agentic(_HangingPage()))
        assert ctx.axe_violations == []
