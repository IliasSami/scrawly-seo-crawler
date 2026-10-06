"""Compare mode (URL diff) + SERP mode (pixel measurement)."""
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

from sentinelseo.web.api import _serp_row, _url_diff, app

client = TestClient(app)


def _u(address: str, **kw: Any) -> Any:
    base: dict[str, Any] = {
        "status": 200, "title": "T", "meta_desc": "D", "canonical": None,
        "indexable": True, "word_count": 100, "segment": None,
    }
    base.update(kw)
    return SimpleNamespace(address=address, **base)


# ---- Compare: URL diff ----

def test_new_and_missing_urls() -> None:
    prev = [_u("https://x/a"), _u("https://x/gone")]
    latest = [_u("https://x/a"), _u("https://x/fresh")]
    d = _url_diff(prev, latest)
    assert [r["address"] for r in d["new"]] == ["https://x/fresh"]
    assert [r["address"] for r in d["missing"]] == ["https://x/gone"]
    assert d["summary"]["new"] == 1 and d["summary"]["missing"] == 1


def test_changed_fields_report_before_and_after() -> None:
    prev = [_u("https://x/a", status=200, title="Old title", indexable=True)]
    latest = [_u("https://x/a", status=404, title="New title", indexable=False)]
    d = _url_diff(prev, latest)
    assert d["summary"]["changed"] == 1
    changes = {c["field"]: (c["before"], c["after"]) for c in d["changed"][0]["changes"]}
    assert changes["status"] == (200, 404)
    assert changes["title"] == ("Old title", "New title")
    assert changes["indexable"] == (True, False)


def test_identical_crawls_have_no_diff() -> None:
    rows = [_u("https://x/a"), _u("https://x/b")]
    d = _url_diff(rows, [_u("https://x/a"), _u("https://x/b")])
    assert d["summary"]["new"] == d["summary"]["missing"] == d["summary"]["changed"] == 0


def test_segment_change_is_diffed() -> None:
    d = _url_diff([_u("https://x/a", segment="Blog")], [_u("https://x/a", segment="Shop")])
    assert d["changed"][0]["changes"][0]["field"] == "segment"


def test_compare_endpoint_shape() -> None:
    body = client.get("/api/compare", params={"crawl1": 999998, "crawl2": 999997}).json()
    # Empty crawls: still returns both the issue diff and the URL diff.
    for key in ("resolved", "new", "regressions", "urls", "summary"):
        assert key in body
    for key in ("new", "missing", "changed", "summary"):
        assert key in body["urls"]


# ---- SERP mode ----

def test_serp_measures_pixels_and_truncation() -> None:
    short = _serp_row("https://x/", "Short title", "Short description")
    assert short["title_px"] > 0 and short["title_chars"] == len("Short title")
    assert short["title_truncated"] is False and short["desc_truncated"] is False

    long_title = _serp_row("https://x/", "W" * 60, "")
    assert long_title["title_truncated"] is True   # way past the ~580px render limit


def test_serp_long_description_truncates() -> None:
    row = _serp_row("https://x/", "t", "word " * 60)
    assert row["desc_truncated"] is True


def test_serp_endpoint_with_rows() -> None:
    body = client.post("/api/serp/preview", json={"rows": [
        {"url": "https://x/1", "title": "Fine", "description": "Fine too"},
        {"url": "https://x/2", "title": "M" * 80, "description": "d"},
    ]}).json()
    assert body["summary"]["total"] == 2
    assert body["summary"]["title_truncated"] == 1
    assert body["rows"][1]["title_truncated"] is True


def test_serp_endpoint_empty_is_safe() -> None:
    body = client.post("/api/serp/preview", json={}).json()
    assert body["summary"]["total"] == 0 and body["rows"] == []


# ---- AI context signal + "Write with AI" ----

def test_serp_flags_thin_descriptions_for_ai() -> None:
    thin = _serp_row("https://x/", "Title", "Too short")
    assert thin["desc_ai_thin"] is True
    detailed = _serp_row("https://x/", "Title", "A" * 200)
    assert detailed["desc_ai_thin"] is False


def test_serp_preview_summarizes_thin_for_ai() -> None:
    body = client.post("/api/serp/preview", json={"rows": [
        {"url": "https://x/1", "title": "t", "description": "x"},
        {"url": "https://x/2", "title": "t", "description": "y" * 200},
    ]}).json()
    assert body["summary"]["desc_ai_thin"] == 1


def test_extract_page_text_pulls_title_meta_and_body() -> None:
    from sentinelseo.web.api import _extract_page_text
    html = (
        "<html><head><title>Acme Widgets</title>"
        "<meta name='description' content='Old meta'></head>"
        "<body><h1>Best Widgets</h1><script>ignore()</script>"
        "<p>We sell durable widgets for makers.</p></body></html>"
    )
    page = _extract_page_text(html)
    assert page["title"] == "Acme Widgets"
    assert page["meta"] == "Old meta"
    assert page["h1"] == "Best Widgets"
    assert "durable widgets" in page["text"]
    assert "ignore()" not in page["text"]   # scripts stripped


def test_parse_serp_json_tolerates_fences_and_prose() -> None:
    from sentinelseo.web.api import _parse_serp_json
    out = _parse_serp_json('```json\n{"title": "T", "description": "D"}\n```')
    assert out == {"title": "T", "description": "D"}
    out2 = _parse_serp_json('Sure! {"title":"A","description":"B"} hope that helps')
    assert out2 == {"title": "A", "description": "B"}
    assert _parse_serp_json("not json") == {"title": "", "description": ""}


def test_serp_generate_requires_ai_configured(monkeypatch: Any) -> None:
    import sentinelseo.web.api as api
    monkeypatch.setattr(api, "_ai_config",
                        lambda: {"kind": "openai", "base_url": "", "model": "", "api_key": ""})
    r = client.post("/api/serp/generate", json={"url": "example.com"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "ai_unconfigured"


def test_serp_generate_full_flow(monkeypatch: Any) -> None:
    import httpx

    import sentinelseo.web.api as api
    monkeypatch.setattr(api, "_ai_config", lambda: {
        "kind": "openai", "base_url": "https://ai.test/v1",
        "model": "m", "api_key": "k"})
    monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(
        text="<html><head><title>Old</title></head><body><h1>Acme</h1>"
             "<p>Acme makes durable widgets for makers.</p></body></html>"))
    # ai_complete + is_configured are imported inside the endpoint from the
    # provider module, so patch them there.
    import sentinelseo.ai.provider as prov
    monkeypatch.setattr(prov, "ai_complete", lambda *a, **k: (
        '{"title": "Acme Widgets for Makers", "description": "Acme makes durable, '
        'maker-grade widgets, plus guides and support to help you pick the right one '
        'for any build project at home."}'))
    monkeypatch.setattr(prov, "is_configured", lambda cfg: True)

    r = client.post("/api/serp/generate", json={"url": "acme.test"})
    assert r.status_code == 200, r.text
    row = r.json()
    assert row["title"] == "Acme Widgets for Makers"
    assert "widgets" in row["description"].lower()
    assert row["ai_generated"] is True
    assert row["desc_ai_thin"] is False   # the generated description is detailed
    assert row["title_px"] > 0            # measured
