from __future__ import annotations

from dataclasses import dataclass

from sentinelseo.checks.domain_f.checks import (
    check_F01,
    check_F02,
    check_F03,
    check_F04,
    check_F05,
    check_F06,
    check_F07,
    check_F08,
    check_F09,
    check_F10,
    check_F11,
    check_F12,
)
from sentinelseo.checks.registry import CrawlContext
from sentinelseo.crawl.models import URLRow


@dataclass
class RenderDiff:
    element: str
    state: str

def make_url_row(
    address: str = "https://example.com/page",
    status: int = 200,
    redirect_chain: list[str] | None = None,
    title: str = "Title",
    meta_desc: str = "Desc",
    canonical: str = "https://example.com/page",
    meta_robots: str | None = None,
    x_robots: str | None = None,
    h1: list[str] | None = None,
    word_count: int = 500,
    content_hash: str = "hash",
    near_dup_cluster: str = "cluster",
    ttfb: float = 0.1,
    size: int = 1000,
    inlink_count: int = 5,
    outlink_count: int = 10,
    indexable: bool = True,
    indexability_reason: str | None = None,
    depth: int = 1,
) -> URLRow:
    row = URLRow(
        address=address,
        status=status,
        redirect_chain=redirect_chain or [],
        title=title,
        meta_desc=meta_desc,
        canonical=canonical,
        meta_robots=meta_robots,
        x_robots=x_robots,
        h1=h1 or [],
        h2=[],
        h3=[],
        h4=[],
        h5=[],
        h6=[],
        word_count=word_count,
        content_hash=content_hash,
        near_dup_cluster=near_dup_cluster,
        ttfb=ttfb,
        size=size,
        inlink_count=inlink_count,
        outlink_count=outlink_count,
        indexable=indexable,
        indexability_reason=indexability_reason,
    )
    row.depth = depth
    return row

def test_check_F01_positive() -> None:
    ctx = CrawlContext(
        url="https://example.com/page",
        url_row=make_url_row(inlink_count=0, status=200, indexable=True)
    )
    res = check_F01(ctx)
    assert res is not None
    assert res.check_id == "F01"
    assert res.evidence["inlinks"] == 0

def test_check_F01_negative() -> None:
    ctx = CrawlContext(
        url="https://example.com/page",
        url_row=make_url_row(inlink_count=5)
    )
    res = check_F01(ctx)
    assert res is None

def test_check_F02_positive() -> None:
    ctx = CrawlContext(
        url="https://example.com/page",
        url_row=make_url_row(inlink_count=1, indexable=True)
    )
    res = check_F02(ctx)
    assert res is not None
    assert res.check_id == "F02"

def test_check_F02_negative() -> None:
    ctx = CrawlContext(
        url="https://example.com/page",
        url_row=make_url_row(inlink_count=5)
    )
    res = check_F02(ctx)
    assert res is None

def test_check_F03_positive() -> None:
    ctx = CrawlContext(
        url="https://example.com/page",
        url_row=make_url_row(outlink_count=151)
    )
    res = check_F03(ctx)
    assert res is not None
    assert res.check_id == "F03"

def test_check_F03_negative() -> None:
    ctx = CrawlContext(
        url="https://example.com/page",
        url_row=make_url_row(outlink_count=50)
    )
    res = check_F03(ctx)
    assert res is None

def test_check_F04_positive() -> None:
    ctx = CrawlContext(
        url="https://example.com/page",
        url_row=make_url_row(depth=5, indexable=True)
    )
    res = check_F04(ctx)
    assert res is not None
    assert res.check_id == "F04"

def test_check_F04_negative() -> None:
    ctx = CrawlContext(
        url="https://example.com/page",
        url_row=make_url_row(depth=2)
    )
    res = check_F04(ctx)
    assert res is None

def test_check_F05_positive() -> None:
    html = "<html><body><a href='https://example.com/internal'></a></body></html>"
    ctx = CrawlContext(url="https://example.com/page", raw_html=html)
    res = check_F05(ctx)
    assert res is not None
    assert res.check_id == "F05"

def test_check_F05_negative() -> None:
    html = "<html><body><a href='/internal'>Text</a></body></html>"
    ctx = CrawlContext(url="https://example.com/page", raw_html=html)
    res = check_F05(ctx)
    assert res is None

def test_check_F06_positive() -> None:
    html = """<html><body>
    <a href="/1">click here</a>
    <a href="/2">read more</a>
    <a href="/3">learn more</a>
    <a href="/4">here</a>
    <a href="/5">more</a>
    <a href="/6">click here</a>
    </body></html>"""
    ctx = CrawlContext(url="https://example.com/page", raw_html=html)
    res = check_F06(ctx)
    assert res is not None
    assert res.check_id == "F06"

def test_check_F06_negative() -> None:
    html = "<html><body><a href='/1'>good anchor</a></body></html>"
    ctx = CrawlContext(url="https://example.com/page", raw_html=html)
    res = check_F06(ctx)
    assert res is None

def test_check_F07_positive() -> None:
    row = make_url_row(status=301, inlink_count=5)
    ctx = CrawlContext(url="https://example.com/page", url_row=row)
    res = check_F07(ctx)
    assert res is not None
    assert res.check_id == "F07"

def test_check_F07_negative() -> None:
    row = make_url_row(status=200, canonical="https://example.com/page", inlink_count=5)
    ctx = CrawlContext(url="https://example.com/page", url_row=row)
    res = check_F07(ctx)
    assert res is None

def test_check_F08_positive() -> None:
    html = "<html><body><a onclick='x()'>Link</a><a>No href</a><div role='link'></div></body></html>"  # noqa: E501
    ctx = CrawlContext(url="https://example.com/page", raw_html=html)
    res = check_F08(ctx)
    assert res is not None
    assert res.check_id == "F08"

def test_check_F08_negative() -> None:
    html = "<html><body><a href='/good'>Link</a></body></html>"
    ctx = CrawlContext(url="https://example.com/page", raw_html=html)
    res = check_F08(ctx)
    assert res is None

def test_check_F09_positive() -> None:
    html = "<html><body><a href='/internal' rel='nofollow'>Link</a></body></html>"
    ctx = CrawlContext(url="https://example.com/page", raw_html=html)
    res = check_F09(ctx)
    assert res is not None
    assert res.check_id == "F09"

def test_check_F09_negative() -> None:
    html = "<html><body><a href='/internal'>Link</a><a href='https://other.com' rel='nofollow'>Ext</a></body></html>"  # noqa: E501
    ctx = CrawlContext(url="https://example.com/page", raw_html=html)
    res = check_F09(ctx)
    assert res is None

def test_check_F10_positive() -> None:
    ctx = CrawlContext(
        url="https://example.com/page",
        render_diffs=[RenderDiff("internal_links", "created")]
    )
    res = check_F10(ctx)
    assert res is not None
    assert res.check_id == "F10"

def test_check_F10_negative() -> None:
    ctx = CrawlContext(
        url="https://example.com/page",
        render_diffs=[RenderDiff("internal_links", "unchanged")]
    )
    res = check_F10(ctx)
    assert res is None

def test_check_F11_positive() -> None:
    ctx = CrawlContext(
        url="https://example.com/page",
        raw_html="<html><body></body></html>",
        url_row=make_url_row(depth=2)
    )
    res = check_F11(ctx)
    assert res is not None
    assert res.check_id == "F11"

def test_check_F11_negative() -> None:
    html = "<html><body><nav aria-label='breadcrumb'></nav></body></html>"
    ctx = CrawlContext(
        url="https://example.com/page",
        raw_html=html,
        url_row=make_url_row(depth=2)
    )
    res = check_F11(ctx)
    assert res is None

def test_check_F12_positive() -> None:
    html = "<html><body><a href='http://example.com/internal'>Link</a></body></html>"
    ctx = CrawlContext(url="https://example.com/page", raw_html=html)
    res = check_F12(ctx)
    assert res is not None
    assert res.check_id == "F12"

def test_check_F12_negative() -> None:
    html = "<html><body><a href='https://example.com/internal'>Link</a><a href='http://other.com'>Link</a></body></html>"  # noqa: E501
    ctx = CrawlContext(url="https://example.com/page", raw_html=html)
    res = check_F12(ctx)
    assert res is None
