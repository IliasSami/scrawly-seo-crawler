from dataclasses import dataclass
from typing import Optional

from sentinelseo.checks.domain_b.checks import (
    check_B01,
    check_B02,
    check_B03,
    check_B04,
    check_B05,
    check_B06,
    check_B07,
    check_B08,
    check_B09,
    check_B10,
    check_B11,
    check_B12,
    check_B13,
    check_B14,
)
from sentinelseo.checks.registry import CrawlContext
from sentinelseo.crawl.models import URLRow


@dataclass
class RenderDiff:
    element: str
    state: str


def make_url_row(
    status: int = 200,
    redirect_chain: Optional[list[str]] = None,
    inlink_count: int = 0,
    canonical: Optional[str] = None,
    indexability_reason: Optional[str] = None,
    word_count: int = 0,
) -> URLRow:
    return URLRow(
        address="http://example.com",
        status=status,
        redirect_chain=redirect_chain or [],
        title=None,
        meta_desc=None,
        canonical=canonical,
        meta_robots=None,
        x_robots=None,
        h1=[],
        h2=[],
        h3=[],
        h4=[],
        h5=[],
        h6=[],
        word_count=word_count,
        content_hash="abc",
        near_dup_cluster="cluster",
        ttfb=0.1,
        size=100,
        inlink_count=inlink_count,
        outlink_count=0,
        indexable=True,
        indexability_reason=indexability_reason,
        internal_links=[],
        external_links=[],
    )


# --- B01 ---
def test_check_B01_positive() -> None:
    ctx = CrawlContext(url="http://example.com", url_row=make_url_row(status=404))
    res = check_B01(ctx)
    assert res is not None
    assert res.check_id == "B01"

def test_check_B01_negative() -> None:
    ctx = CrawlContext(url="http://example.com", url_row=make_url_row(status=200))
    res = check_B01(ctx)
    assert res is None

def test_check_B01_boundary() -> None:
    ctx = CrawlContext(url="http://example.com", url_row=make_url_row(status=400))
    res = check_B01(ctx)
    assert res is not None
    assert res.check_id == "B01"

    ctx = CrawlContext(url="http://example.com", url_row=make_url_row(status=499))
    res = check_B01(ctx)
    assert res is not None


# --- B02 ---
def test_check_B02_positive() -> None:
    ctx = CrawlContext(url="http://example.com", url_row=make_url_row(status=500))
    res = check_B02(ctx)
    assert res is not None
    assert res.check_id == "B02"

def test_check_B02_negative() -> None:
    ctx = CrawlContext(url="http://example.com", url_row=make_url_row(status=200))
    res = check_B02(ctx)
    assert res is None

def test_check_B02_boundary() -> None:
    ctx = CrawlContext(url="http://example.com", url_row=make_url_row(status=599))
    res = check_B02(ctx)
    assert res is not None


# --- B03 ---
def test_check_B03_positive() -> None:
    ctx = CrawlContext(
        url="http://example.com",
        title="Page Not Found",
        url_row=make_url_row(status=200, word_count=50),
    )
    res = check_B03(ctx)
    assert res is not None
    assert res.check_id == "B03"

def test_check_B03_negative() -> None:
    ctx = CrawlContext(
        url="http://example.com",
        title="Welcome",
        url_row=make_url_row(status=200, word_count=500),
    )
    res = check_B03(ctx)
    assert res is None

def test_check_B03_boundary() -> None:
    # Phrase in main text, but word count >= 100
    # and no phrase in title -> Should not fire  # noqa: E501
    ctx = CrawlContext(
        url="http://example.com",
        title="Welcome",
        raw_html="Page not found here though",
        url_row=make_url_row(status=200, word_count=150),
    )
    res = check_B03(ctx)
    assert res is None


# --- B04 ---
def test_check_B04_negative() -> None:
    ctx = CrawlContext(url="http://example.com", url_row=make_url_row(status=200))
    res = check_B04(ctx)
    assert res is None


# --- B05 ---
def test_check_B05_negative() -> None:
    ctx = CrawlContext(url="http://example.com", url_row=make_url_row(status=200))
    res = check_B05(ctx)
    assert res is None


# --- B06 ---
def test_check_B06_positive() -> None:
    ctx = CrawlContext(
        url="http://example.com",
        url_row=make_url_row(status=200, redirect_chain=["a", "b"]),
    )
    res = check_B06(ctx)
    assert res is not None
    assert res.check_id == "B06"

def test_check_B06_negative() -> None:
    ctx = CrawlContext(
        url="http://example.com",
        url_row=make_url_row(status=200, redirect_chain=[]),
    )
    res = check_B06(ctx)
    assert res is None

def test_check_B06_boundary() -> None:
    # 1 hop -> not a chain >= 2
    ctx = CrawlContext(
        url="http://example.com",
        url_row=make_url_row(status=200, redirect_chain=["a"]),
    )
    res = check_B06(ctx)
    assert res is None


# --- B07 ---
def test_check_B07_positive() -> None:
    ctx = CrawlContext(
        url="http://example.com",
        url_row=make_url_row(status=200, redirect_chain=["a", "b", "a"]),
    )
    res = check_B07(ctx)
    assert res is not None
    assert res.check_id == "B07"

def test_check_B07_negative() -> None:
    ctx = CrawlContext(
        url="http://example.com",
        url_row=make_url_row(status=200, redirect_chain=["a", "b"]),
    )
    res = check_B07(ctx)
    assert res is None

def test_check_B07_boundary() -> None:
    # Repeat in chain, but not at ends
    ctx = CrawlContext(
        url="http://example.com",
        url_row=make_url_row(status=200, redirect_chain=["a", "b", "b", "c"]),
    )
    res = check_B07(ctx)
    assert res is not None


# --- B08 ---
def test_check_B08_positive() -> None:
    ctx = CrawlContext(url="http://example.com", url_row=make_url_row(status=302))
    res = check_B08(ctx)
    assert res is not None
    assert res.check_id == "B08"

def test_check_B08_negative() -> None:
    ctx = CrawlContext(url="http://example.com", url_row=make_url_row(status=301))
    res = check_B08(ctx)
    assert res is None

def test_check_B08_boundary() -> None:
    ctx = CrawlContext(url="http://example.com", url_row=make_url_row(status=307))
    res = check_B08(ctx)
    assert res is not None


# --- B09 ---
def test_check_B09_negative() -> None:
    ctx = CrawlContext(url="http://example.com", url_row=make_url_row(status=200))
    res = check_B09(ctx)
    assert res is None


# --- B10 ---
def test_check_B10_negative() -> None:
    ctx = CrawlContext(url="http://example.com", url_row=make_url_row(status=200))
    res = check_B10(ctx)
    assert res is None


# --- B11 ---
def test_check_B11_positive() -> None:
    ctx = CrawlContext(
        url="http://example.com", url_row=make_url_row(status=404, redirect_chain=["a"])
    )
    res = check_B11(ctx)
    assert res is not None
    assert res.check_id == "B11"

def test_check_B11_negative() -> None:
    # 200 with redirect chain -> not an error
    ctx = CrawlContext(
        url="http://example.com", url_row=make_url_row(status=200, redirect_chain=["a"])
    )
    res = check_B11(ctx)
    assert res is None

def test_check_B11_boundary() -> None:
    # error but no redirect chain -> not B11
    ctx = CrawlContext(
        url="http://example.com", url_row=make_url_row(status=400, redirect_chain=[])
    )
    res = check_B11(ctx)
    assert res is None


# --- B12 ---
def test_check_B12_positive() -> None:
    html = '<html><head><meta http-equiv="refresh" content="0; url=http://example.com/"></head></html>'  # noqa: E501
    ctx = CrawlContext(
        url="http://example.com", raw_html=html, url_row=make_url_row(status=200)
    )
    res = check_B12(ctx)
    assert res is not None
    assert res.check_id == "B12"

def test_check_B12_positive_js() -> None:
    ctx = CrawlContext(
        url="http://example.com",
        raw_html="<html></html>",
        render_diffs=[RenderDiff(element="_js_redirect", state="created")],
        url_row=make_url_row(status=200),
    )
    res = check_B12(ctx)
    assert res is not None
    assert res.check_id == "B12"

def test_check_B12_negative() -> None:
    ctx = CrawlContext(
        url="http://example.com",
        raw_html="<html></html>",
        url_row=make_url_row(status=200),
    )
    res = check_B12(ctx)
    assert res is None


# --- B13 ---
def test_check_B13_positive() -> None:
    ctx = CrawlContext(url="http://example.com", url_row=make_url_row(status=200))
    res = check_B13(ctx)
    assert res is not None
    assert res.check_id == "B13"

def test_check_B13_negative() -> None:
    ctx = CrawlContext(url="https://example.com", url_row=make_url_row(status=200))
    res = check_B13(ctx)
    assert res is None

def test_check_B13_boundary() -> None:
    # http url but status is 301 (has redirect) -> Should not fire
    ctx = CrawlContext(url="http://example.com", url_row=make_url_row(status=301))
    res = check_B13(ctx)
    assert res is None


# --- B14 ---
def test_check_B14_positive() -> None:
    ctx = CrawlContext(
        url="http://example.com",
        url_row=make_url_row(status=301, indexability_reason="mixed_redirect"),
    )
    res = check_B14(ctx)
    assert res is not None
    assert res.check_id == "B14"

def test_check_B14_negative() -> None:
    ctx = CrawlContext(
        url="http://example.com",
        url_row=make_url_row(status=301, indexability_reason="none"),
    )
    res = check_B14(ctx)
    assert res is None

def test_check_B14_boundary() -> None:
    # Missing indexability reason entirely
    ctx = CrawlContext(
        url="http://example.com",
        url_row=make_url_row(status=301),
    )
    res = check_B14(ctx)
    assert res is None
