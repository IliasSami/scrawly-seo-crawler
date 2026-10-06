from sentinelseo.checks.domain_n.checks import (
    check_N01,
    check_N02,
    check_N03,
    check_N04,
    check_N05,
    check_N06,
    check_N07,
    check_N08,
    check_N09,
    check_N10,
    check_N11,
    check_N12,
    check_N13,
    check_N14,
)
from sentinelseo.checks.registry import CrawlContext
from sentinelseo.crawl.models import URLRow


def _make_ctx(html: str = "", ttfb: float = 0, size: int = 0) -> CrawlContext:
    row = URLRow(
        address="https://example.com",
        status=200,
        redirect_chain=[],
        title=None,
        meta_desc=None,
        canonical=None,
        meta_robots=None,
        x_robots=None,
        h1=[],
        h2=[],
        h3=[],
        h4=[],
        h5=[],
        h6=[],
        word_count=0,
        content_hash="",
        near_dup_cluster="",
        ttfb=ttfb,
        size=size,
        inlink_count=0,
        outlink_count=0,
        indexable=True,
        indexability_reason=None,
    )
    return CrawlContext(url="https://example.com", url_row=row, raw_html=html)


def test_check_N01_positive() -> None:
    ctx = _make_ctx()
    ctx.url_row.lcp_s = 5.0  # poor (> 4.0s)
    f = check_N01(ctx)
    assert f is not None and f.check_id == "N01" and f.severity == "High"


def test_check_N01_negative() -> None:
    ctx = _make_ctx()
    ctx.url_row.lcp_s = 1.8  # good
    assert check_N01(ctx) is None
    assert check_N01(_make_ctx()) is None  # no render data


def test_check_N02_positive() -> None:
    assert check_N02(_make_ctx()) is None


def test_check_N02_negative() -> None:
    assert check_N02(_make_ctx()) is None


def test_check_N03_positive() -> None:
    ctx = _make_ctx()
    ctx.url_row.cls = 0.3  # poor (> 0.25)
    f = check_N03(ctx)
    assert f is not None and f.check_id == "N03" and f.severity == "High"


def test_check_N03_negative() -> None:
    ctx = _make_ctx()
    ctx.url_row.cls = 0.05  # good
    assert check_N03(ctx) is None
    assert check_N03(_make_ctx()) is None  # no render data


def test_check_N04_positive() -> None:
    ctx = _make_ctx(ttfb=0.9)
    res = check_N04(ctx)
    assert res is not None
    assert res.check_id == "N04"


def test_check_N04_negative() -> None:
    ctx = _make_ctx(ttfb=0.5)
    res = check_N04(ctx)
    assert res is None


def test_check_N05_positive() -> None:
    html = (
        '<html><head><script src="app.js"></script>'
        '<link rel="stylesheet" href="style.css"></head><body></body></html>'
    )
    ctx = _make_ctx(html=html)
    res = check_N05(ctx)
    assert res is not None
    assert res.check_id == "N05"
    assert "app.js" in res.evidence["blocking_assets"]
    assert "style.css" in res.evidence["blocking_assets"]


def test_check_N05_negative() -> None:
    html = (
        '<html><head><script src="app.js" async></script>'
        '<link rel="stylesheet" href="print.css" media="print"></head>'
        "<body></body></html>"
    )
    ctx = _make_ctx(html=html)
    res = check_N05(ctx)
    assert res is None


def test_check_N06_positive() -> None:
    assert check_N06(_make_ctx()) is None


def test_check_N06_negative() -> None:
    assert check_N06(_make_ctx()) is None


def test_check_N07_positive() -> None:
    assert check_N07(_make_ctx()) is None


def test_check_N07_negative() -> None:
    assert check_N07(_make_ctx()) is None


def test_check_N08_positive() -> None:
    assert check_N08(_make_ctx()) is None


def test_check_N08_negative() -> None:
    assert check_N08(_make_ctx()) is None


def test_check_N09_positive() -> None:
    html = "<html><body>" + "<div></div>" * 1600 + "</body></html>"
    ctx = _make_ctx(html=html)
    res = check_N09(ctx)
    assert res is not None
    assert res.check_id == "N09"


def test_check_N09_negative() -> None:
    html = "<html><body>" + "<div></div>" * 10 + "</body></html>"
    ctx = _make_ctx(html=html)
    res = check_N09(ctx)
    assert res is None


def test_check_N10_positive() -> None:
    ctx = _make_ctx(size=3_000_000)
    res = check_N10(ctx)
    assert res is not None
    assert res.check_id == "N10"


def test_check_N10_negative() -> None:
    ctx = _make_ctx(size=1_000_000)
    res = check_N10(ctx)
    assert res is None


def test_check_N11_positive() -> None:
    html = "<html><body>" + "<img src='a.jpg'>" * 105 + "</body></html>"
    ctx = _make_ctx(html=html)
    res = check_N11(ctx)
    assert res is not None
    assert res.check_id == "N11"


def test_check_N11_negative() -> None:
    html = "<html><body><img src='a.jpg'></body></html>"
    ctx = _make_ctx(html=html)
    res = check_N11(ctx)
    assert res is None


def test_check_N12_positive() -> None:
    assert check_N12(_make_ctx()) is None


def test_check_N12_negative() -> None:
    assert check_N12(_make_ctx()) is None


def test_check_N13_positive() -> None:
    html = (
        "<html><head>"
        '<link href="https://fonts.googleapis.com/css?family=Roboto" rel="stylesheet">'
        "</head><body></body></html>"
    )
    ctx = _make_ctx(html=html)
    res = check_N13(ctx)
    assert res is not None
    assert res.check_id == "N13"


def test_check_N13_negative() -> None:
    html = (
        "<html><head>"
        '<link href="https://fonts.googleapis.com/css?family=Roboto&display=swap" '
        'rel="stylesheet"></head><body></body></html>'
    )
    ctx = _make_ctx(html=html)
    res = check_N13(ctx)
    assert res is None


def test_check_N14_positive() -> None:
    html = (
        "<html><head>"
        '<script src="https://google-analytics.com/analytics.js"></script>'
        '<script src="https://googletagmanager.com/gtm.js"></script>'
        '<script src="https://hotjar.com/hj.js"></script>'
        "</head><body></body></html>"
    )
    ctx = _make_ctx(html=html)
    res = check_N14(ctx)
    assert res is not None
    assert res.check_id == "N14"


def test_check_N14_negative() -> None:
    html = (
        "<html><head>"
        '<script src="https://google-analytics.com/analytics.js"></script>'
        "</head><body></body></html>"
    )
    ctx = _make_ctx(html=html)
    res = check_N14(ctx)
    assert res is None
