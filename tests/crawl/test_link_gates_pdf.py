"""Link-target gates (hreflang / AMP / pagination) + PDF extraction."""
from types import SimpleNamespace
from typing import Any

from sentinelseo.crawl.fetcher import Crawler
from sentinelseo.crawl.pdf import build_pdf_row, extract_pdf_properties, is_pdf


def _row() -> SimpleNamespace:
    return SimpleNamespace(
        address="https://ex.com/page",
        hreflang=[("en", "/en/page"), ("de", "https://ex.com/de/page"),
                  ("fr", "https://other.com/fr/page")],
        amp_url="https://ex.com/page/amp",
        prev_url="https://ex.com/page?p=1",
        next_url="https://ex.com/page?p=3",
    )


def _crawler(**kw: Any) -> Crawler:
    c = Crawler(render=False, **kw)
    c._seed_netloc = "ex.com"
    return c


def test_gates_off_by_default_follow_nothing() -> None:
    assert _crawler()._gated_link_targets(_row()) == []


def test_hreflang_gate_resolves_relative_and_stays_on_host() -> None:
    got = _crawler(crawl_hreflang=True)._gated_link_targets(_row())
    assert "https://ex.com/en/page" in got      # relative href resolved
    assert "https://ex.com/de/page" in got
    assert all("other.com" not in u for u in got)  # cross-domain alternate not followed


def test_amp_gate() -> None:
    assert _crawler(crawl_amp=True)._gated_link_targets(_row()) == ["https://ex.com/page/amp"]


def test_pagination_gate_follows_prev_and_next() -> None:
    got = _crawler(crawl_pagination=True)._gated_link_targets(_row())
    assert set(got) == {"https://ex.com/page?p=1", "https://ex.com/page?p=3"}


def test_gates_combine() -> None:
    got = _crawler(crawl_amp=True, crawl_pagination=True)._gated_link_targets(_row())
    assert len(got) == 3 and "https://ex.com/page/amp" in got


# ---- PDF ----

def test_is_pdf_by_content_type_and_extension() -> None:
    assert is_pdf("application/pdf; charset=binary")
    assert is_pdf("application/octet-stream", "https://x/doc.pdf")   # vague server + .pdf
    assert not is_pdf("text/html", "https://x/doc.pdf")             # explicit non-PDF wins
    assert not is_pdf("text/html", "https://x/page")


def _minimal_pdf() -> bytes:
    """A tiny valid one-page PDF with a Title, built by pypdf itself."""
    import io

    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    w.add_metadata({"/Title": "Quarterly Report", "/Author": "Ilias"})
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_extract_pdf_properties() -> None:
    props = extract_pdf_properties(_minimal_pdf())
    assert props["page_count"] == 1
    assert props["title"] == "Quarterly Report"
    assert props["author"] == "Ilias"


def test_build_pdf_row_uses_pdf_title_and_size() -> None:
    content = _minimal_pdf()
    row = build_pdf_row("https://ex.com/report.pdf", 200, {}, content)
    assert row.title == "Quarterly Report"
    assert row.content_type == "application/pdf"
    assert row.size == len(content)
    assert row.indexable is True
    assert row.pdf_properties["page_count"] == 1


def test_build_pdf_row_respects_x_robots_noindex() -> None:
    row = build_pdf_row(
        "https://ex.com/r.pdf", 200, {"x-robots-tag": "noindex"}, _minimal_pdf()
    )
    assert row.indexable is False and "noindex" in (row.indexability_reason or "")


def test_build_pdf_row_extraction_gate_off() -> None:
    row = build_pdf_row("https://ex.com/r.pdf", 200, {}, _minimal_pdf(), extract_properties=False)
    assert row.pdf_properties == {}     # still crawled + status-checked, no props
    assert row.status == 200 and row.size > 0


def test_unreadable_pdf_does_not_raise() -> None:
    props = extract_pdf_properties(b"not really a pdf")
    assert props.get("error") == "unreadable"


# ---- integration: the gates in the real enqueue path ----

def test_rel_targets_only_crawled_when_gated_on(tmp_path: Any) -> None:
    """page2/de/amp are reachable ONLY via <link rel>, never via <a href> — so
    they appear in the crawl if and only if their gate is on. Guards the wiring
    between _gated_link_targets and the worker's enqueue loop."""
    import asyncio
    import functools
    import http.server
    import os
    import socket
    import threading

    (tmp_path / "index.html").write_text(
        '<html><head><link rel="next" href="/page2.html">'
        '<link rel="alternate" hreflang="de" href="/de.html">'
        '<link rel="amphtml" href="/amp.html"></head>'
        '<body><a href="/plain.html">plain</a></body></html>'
    )
    for n in ("page2", "de", "amp", "plain"):
        (tmp_path / f"{n}.html").write_text(f"<html><head><title>{n}</title></head><body>{n}</body></html>")

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:  # keep the test output clean
            pass

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    handler = functools.partial(QuietHandler, directory=str(tmp_path))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}/index.html"

    async def crawl(**gates: Any) -> set[str]:
        c = Crawler(render=False, respect_robots=False, robots_mode="ignore",
                    discover_sitemap=False, max_pages=20, concurrency=4, **gates)
        urls, *_ = await c.crawl_site(base)
        return {os.path.basename(u.address) for u in urls}

    try:
        off = asyncio.run(crawl())
        on = asyncio.run(crawl(crawl_pagination=True, crawl_hreflang=True, crawl_amp=True))
    finally:
        srv.shutdown()

    rel_targets = {"page2.html", "de.html", "amp.html"}
    assert rel_targets.isdisjoint(off)      # gates off -> references recorded, not followed
    assert rel_targets.issubset(on)         # gates on  -> followed as pages
    assert "plain.html" in off and "plain.html" in on   # <a href> unaffected either way
