"""Resource extraction (CSS/JS/media) — SF Pattern A parser side."""
from sentinelseo.crawl.parser import parse_html

_HTML = """
<html><head>
  <link rel="stylesheet" href="/style.css">
  <link rel="preload" as="style" href="/preload.css">
  <link rel="icon" href="/favicon.ico">
  <script src="/app.js"></script>
  <script src="https://cdn.example.com/lib.js"></script>
  <script>console.log('inline, not a resource')</script>
</head><body>
  <video src="/clip.mp4"></video>
  <audio><source src="/track.mp3"></audio>
  <img src="/pic.png">
</body></html>
"""


def test_extracts_css_js_media() -> None:
    row, _imgs, _sd = parse_html("https://ex.com/page", _HTML)
    by_type: dict[str, list[str]] = {}
    for r in row.resources:
        by_type.setdefault(r.type, []).append(r.url)
    assert "https://ex.com/style.css" in by_type["css"]
    assert "https://ex.com/preload.css" in by_type["css"]     # preload-as-style counts
    assert "https://ex.com/app.js" in by_type["js"]
    assert "https://cdn.example.com/lib.js" in by_type["js"]  # cross-origin script too
    assert "https://ex.com/clip.mp4" in by_type["media"]
    assert "https://ex.com/track.mp3" in by_type["media"]


def test_ignores_inline_and_favicon() -> None:
    row, _i, _s = parse_html("https://ex.com/page", _HTML)
    urls = {r.url for r in row.resources}
    assert not any(u.endswith("favicon.ico") for u in urls)   # icon isn't css/js/media
    assert all(r.type in ("css", "js", "media") for r in row.resources)
    assert all(r.from_page == "https://ex.com/page" for r in row.resources)


def test_data_uris_skipped() -> None:
    html = '<script src="data:text/javascript,void0"></script><link rel="stylesheet" href="data:text/css,x">'
    row, _i, _s = parse_html("https://ex.com/", html)
    assert row.resources == []


def test_crawler_resource_type_gate() -> None:
    from sentinelseo.crawl.fetcher import Crawler
    assert Crawler(render=False).crawl_resource_types == {"css", "js", "media"}
    c = Crawler(render=False, crawl_css=False, crawl_media=False)
    assert c.crawl_resource_types == {"js"}


def test_resources_endpoint_summarises_and_flags_broken() -> None:
    from fastapi.testclient import TestClient

    from sentinelseo.db.models import Resource
    from sentinelseo.db.session import SessionLocal
    from sentinelseo.web.api import app

    db = SessionLocal()
    cid = 999999  # synthetic crawl id, no FK enforcement needed for the read path
    db.query(Resource).filter(Resource.crawl_id == cid).delete(synchronize_session=False)
    db.add(Resource(crawl_id=cid, url="https://x/a.css", type="css", status=200, size=10, ref_count=3))
    db.add(Resource(crawl_id=cid, url="https://x/b.js", type="js", status=404, size=None, ref_count=1))
    db.add(Resource(crawl_id=cid, url="https://x/c.js", type="js", status=0, ref_count=1))
    db.commit()
    db.close()

    body = TestClient(app).get(f"/api/resources/{cid}").json()
    assert body["summary"]["total"] == 3
    assert body["summary"]["broken"] == 2          # 404 + no-response(0)
    assert body["summary"]["css"]["count"] == 1 and body["summary"]["css"]["broken"] == 0
    assert body["summary"]["js"]["broken"] == 2
    assert {r["url"] for r in body["resources"] if r["broken"]} == {"https://x/b.js", "https://x/c.js"}

    db = SessionLocal()
    db.query(Resource).filter(Resource.crawl_id == cid).delete(synchronize_session=False)
    db.commit()
    db.close()
