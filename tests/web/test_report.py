"""Audit report: friendly page for a missing crawl, and the PDF export endpoint.

The PDF is rendered with Playwright's Chromium in production; here we stub that
async chain so the test stays fast and offline while still exercising the endpoint
(content type, attachment header, crawl-existence guard)."""
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sentinelseo.db.models import URL, Client, Crawl
from sentinelseo.db.session import SessionLocal
from sentinelseo.web.api import app

client = TestClient(app)


def _seed_crawl() -> int:
    db = SessionLocal()
    c = Client(name="Test Co", base_url="https://ex.com/")
    db.add(c)
    db.commit()
    db.refresh(c)
    cr = Crawl(client_id=c.id, target_url="https://ex.com/", config={}, url_count=1)
    db.add(cr)
    db.commit()
    db.refresh(cr)
    db.add(URL(crawl_id=cr.id, address="https://ex.com/", status=200, indexable=True, depth=0))
    db.commit()
    cid = int(cr.id)
    db.close()
    return cid


def test_report_missing_crawl_is_a_friendly_page() -> None:
    r = client.get("/api/report/999999")
    assert r.status_code == 404
    assert "text/html" in r.headers["content-type"]
    assert "no longer available" in r.text  # not a raw JSON error


def test_report_pdf_missing_crawl_404() -> None:
    r = client.get("/api/report/999999/pdf")
    assert r.status_code == 404


def test_report_pdf_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    cid = _seed_crawl()

    class _Page:
        async def set_content(self, *a: Any, **k: Any) -> None: ...
        async def pdf(self, *a: Any, **k: Any) -> bytes: return b"%PDF-1.4 stub"

    class _Browser:
        async def new_page(self) -> _Page: return _Page()
        async def close(self) -> None: ...

    class _Chromium:
        async def launch(self, *a: Any, **k: Any) -> _Browser: return _Browser()

    class _PW:
        def __init__(self) -> None: self.chromium = _Chromium()
        async def __aenter__(self) -> "_PW": return self
        async def __aexit__(self, *a: Any) -> bool: return False

    import playwright.async_api as pa
    monkeypatch.setattr(pa, "async_playwright", lambda: _PW())

    r = client.get(f"/api/report/{cid}/pdf")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert "ex.com" in r.headers["content-disposition"]  # filename derives from host
    assert r.content.startswith(b"%PDF")
