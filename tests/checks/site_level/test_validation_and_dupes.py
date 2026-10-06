"""Phase-7 SF-parity: HTML validation (V13-V17), near-duplicate threshold and
paginated-dupe skipping."""
from typing import Any

from datasketch import MinHash  # type: ignore

import sentinelseo.checks.site_level.checks  # noqa: F401
from sentinelseo.audit.context import SiteContext
from sentinelseo.checks.registry import CrawlContext
from sentinelseo.checks.site_level.registry import get_site_level_checks
from sentinelseo.crawl.models import URLRow


def _row(**kw: Any) -> URLRow:
    row = URLRow(
        address="http://t/", status=200, redirect_chain=[], title="", meta_desc="",
        canonical="", meta_robots="", x_robots="", h1=[], h2=[], h3=[], h4=[], h5=[], h6=[],
        word_count=0, content_hash="", near_dup_cluster="", ttfb=0.0, size=0, inlink_count=0,
        outlink_count=0, indexable=True, indexability_reason=None,
    )
    for k, v in kw.items():
        setattr(row, k, v)
    return row


def _page(url: str, html: str = "", **row_kw: Any) -> CrawlContext:
    row = _row(content_type="text/html", **row_kw)
    return CrawlContext(url=url, url_row=row, raw_html=html)


def _run(check_id: str, pages: dict[str, CrawlContext], **config: Any) -> list[Any]:
    fn = get_site_level_checks()[check_id][1]
    site = SiteContext("http://t", pages, config=config)
    return list(fn(site))


# ---------------- HTML validation gate ----------------

GOOD = '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Ok</title></head><body>hi</body></html>'
NO_DOCTYPE = '<html lang="en"><head><meta charset="utf-8"><title>Ok</title></head><body>hi</body></html>'
NO_LANG = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Ok</title></head><body>hi</body></html>'
TWO_TITLES = '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>A</title><title>B</title></head><body>hi</body></html>'
NO_CHARSET = '<!DOCTYPE html><html lang="en"><head><title>Ok</title></head><body>hi</body></html>'
BAD_HEAD = '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Ok</title><div>x</div><img src="y"></head><body>hi</body></html>'


def test_validation_off_by_default() -> None:
    pages = {"http://t/bad": _page("http://t/bad", NO_DOCTYPE, title_count=1)}
    # No config → nothing fires.
    for cid in ("V13", "V14", "V15", "V16", "V17"):
        assert _run(cid, pages) == []


def test_v13_missing_doctype() -> None:
    pages = {
        "http://t/ok": _page("http://t/ok", GOOD, lang="en", title_count=1),
        "http://t/bad": _page("http://t/bad", NO_DOCTYPE, lang="en", title_count=1),
    }
    res = _run("V13", pages, html_validation=True)
    assert [f.affected_urls[0] for f in res] == ["http://t/bad"]


def test_v14_missing_lang() -> None:
    pages = {
        "http://t/ok": _page("http://t/ok", GOOD, lang="en", title_count=1),
        "http://t/bad": _page("http://t/bad", NO_LANG, lang="", title_count=1),
    }
    res = _run("V14", pages, html_validation=True)
    assert [f.affected_urls[0] for f in res] == ["http://t/bad"]


def test_v15_multiple_titles() -> None:
    pages = {
        "http://t/ok": _page("http://t/ok", GOOD, lang="en", title_count=1),
        "http://t/bad": _page("http://t/bad", TWO_TITLES, lang="en", title_count=2),
    }
    res = _run("V15", pages, html_validation=True)
    assert [f.affected_urls[0] for f in res] == ["http://t/bad"]


def test_v16_missing_charset_header_counts() -> None:
    # A page with no meta charset but a charset in the Content-Type header passes.
    ok = _page("http://t/ok", NO_CHARSET, lang="en", title_count=1,
               headers={"Content-Type": "text/html; charset=utf-8"})
    bad = _page("http://t/bad", NO_CHARSET, lang="en", title_count=1,
                headers={"Content-Type": "text/html"})
    res = _run("V16", {"http://t/ok": ok, "http://t/bad": bad}, html_validation=True)
    assert [f.affected_urls[0] for f in res] == ["http://t/bad"]


def test_v17_invalid_head_element_from_raw_source() -> None:
    # The HTML parser relocates div/img out of <head>; detection must use raw source.
    pages = {
        "http://t/ok": _page("http://t/ok", GOOD, lang="en", title_count=1),
        "http://t/bad": _page("http://t/bad", BAD_HEAD, lang="en", title_count=1),
    }
    res = _run("V17", pages, html_validation=True)
    assert len(res) == 1 and res[0].affected_urls[0] == "http://t/bad"
    assert set(res[0].evidence["invalid_head_elements"]) == {"div", "img"}


def test_v17_ignores_flow_tags_inside_head_script() -> None:
    # A <div> string inside an inline <script> in the head is NOT invalid markup.
    html = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Ok</title>'
            '<script>var x = "<div>not real</div>";</script></head><body>hi</body></html>')
    pages = {"http://t/js": _page("http://t/js", html, lang="en", title_count=1)}
    assert _run("V17", pages, html_validation=True) == []


# ---------------- near-duplicate threshold ----------------

def _mh_bytes(text: str) -> bytes:
    m = MinHash(num_perm=128)
    for i in range(len(text.split()) - 4):
        m.update(" ".join(text.split()[i:i + 5]).encode())
    return bytes(m.hashvalues.tobytes())


def test_near_dup_threshold_controls_matching() -> None:
    a = "the quick brown fox jumps over the lazy dog " * 20
    # ~60% similar to a
    b = ("the quick brown fox jumps over the lazy dog " * 12
         + "and now for something completely different indeed today ok " * 8)
    pages = {
        "u1": _page("u1", minhash=_mh_bytes(a)),
        "u2": _page("u2", minhash=_mh_bytes(b)),
    }
    # At 90% they are not near-dups.
    assert _run("E02", pages, near_dup_threshold=90) == []
    # At 40% they are.
    res = _run("E02", pages, near_dup_threshold=40)
    assert len(res) == 2


# ---------------- ignore paginated dupes ----------------

def test_ignore_paginated_dupes_skips_page_urls() -> None:
    same = "x" * 32
    pages = {
        "http://t/list": _page("http://t/list", content_hash=same),
        "http://t/list?page=2": _page("http://t/list?page=2", content_hash=same),
    }
    # Without the flag, both flag as exact dupes.
    assert len(_run("E01", pages)) == 2
    # With the flag, the ?page=2 URL is dropped, leaving no duplicate pair.
    assert _run("E01", pages, ignore_paginated_dupes=True) == []
