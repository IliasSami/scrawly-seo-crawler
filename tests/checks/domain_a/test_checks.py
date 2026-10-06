from typing import Any

from sentinelseo.checks.domain_a.checks import (
    check_A01,
    check_A02,
    check_A03,
    check_A04,
    check_A05,
    check_A06,
    check_A07,
    check_A08,
    check_A09,
    check_A10,
    check_A11,
    check_A12,
    check_A13,
    check_A14,
    check_A15,
)
from sentinelseo.checks.registry import CrawlContext
from sentinelseo.crawl.models import UrlRenderDiffRow, URLRow


def _mock_url_row(**kwargs: Any) -> URLRow:
    defaults: dict[str, Any] = {
        "address": "http://localhost/",
        "status": 200,
        "redirect_chain": [],
        "title": None,
        "meta_desc": None,
        "canonical": None,
        "meta_robots": None,
        "x_robots": None,
        "h1": [],
        "h2": [],
        "h3": [],
        "h4": [],
        "h5": [],
        "h6": [],
        "word_count": 0,
        "content_hash": "",
        "near_dup_cluster": "",
        "ttfb": 0.0,
        "size": 0,
        "inlink_count": 10,
        "outlink_count": 0,
        "indexable": True,
        "indexability_reason": None,
        "internal_links": [],
        "external_links": [],
    }
    defaults.update(kwargs)
    return URLRow(**defaults)


# A01, A02, A03, A12, A15 are deferred, they should return None
def test_check_A01() -> None:
    assert check_A01(CrawlContext(url="http://localhost/")) is None


def test_check_A02() -> None:
    assert check_A02(CrawlContext(url="http://localhost/")) is None


def test_check_A03() -> None:
    assert check_A03(CrawlContext(url="http://localhost/")) is None


# A04
def test_check_A04_positive() -> None:
    ctx = CrawlContext(
        url="http://localhost/",
        url_row=_mock_url_row(meta_robots="noindex, follow", status=200),
    )
    assert check_A04(ctx) is not None


def test_check_A04_negative() -> None:
    ctx = CrawlContext(
        url="http://localhost/",
        url_row=_mock_url_row(meta_robots="index, follow", status=200),
    )
    assert check_A04(ctx) is None


def test_check_A04_boundary() -> None:
    ctx = CrawlContext(
        url="http://localhost/",
        url_row=_mock_url_row(meta_robots="noindex", status=404),
    )
    assert check_A04(ctx) is None  # Because status != 200


# A05
def test_check_A05_positive() -> None:
    ctx = CrawlContext(
        url="http://localhost/", url_row=_mock_url_row(x_robots="noindex", status=200)
    )
    assert check_A05(ctx) is not None


def test_check_A05_negative() -> None:
    ctx = CrawlContext(
        url="http://localhost/", url_row=_mock_url_row(x_robots="index", status=200)
    )
    assert check_A05(ctx) is None


def test_check_A05_boundary() -> None:
    ctx = CrawlContext(
        url="http://localhost/", url_row=_mock_url_row(x_robots="noindex", status=404)
    )
    assert check_A05(ctx) is None


# A06
def test_check_A06_positive() -> None:
    ctx = CrawlContext(
        url="http://localhost/", url_row=_mock_url_row(meta_robots="noindex, nofollow")
    )
    assert check_A06(ctx) is not None


def test_check_A06_negative() -> None:
    ctx = CrawlContext(
        url="http://localhost/", url_row=_mock_url_row(meta_robots="noindex, follow")
    )
    assert check_A06(ctx) is None


def test_check_A06_boundary() -> None:
    ctx = CrawlContext(
        url="http://localhost/", url_row=_mock_url_row(meta_robots="index, nofollow")
    )
    assert check_A06(ctx) is None


# A07
def test_check_A07_positive() -> None:
    ctx = CrawlContext(
        url="http://localhost/",
        url_row=_mock_url_row(meta_robots="noindex", x_robots="index"),
    )
    assert check_A07(ctx) is not None


def test_check_A07_negative() -> None:
    ctx = CrawlContext(
        url="http://localhost/",
        url_row=_mock_url_row(meta_robots="noindex", x_robots="noindex"),
    )
    assert check_A07(ctx) is None


def test_check_A07_boundary() -> None:
    row = _mock_url_row(
        meta_robots="noindex", x_robots="noindex", canonical="http://localhost/other"
    )
    row.in_sitemap = True
    ctx = CrawlContext(url="http://localhost/", url_row=row)
    assert check_A07(ctx) is None  # Canon away handles the noindex gracefully


# A08
def test_check_A08_positive() -> None:
    ctx = CrawlContext(
        url="http://localhost/",
        render_diffs=[
            UrlRenderDiffRow(
                url="http://localhost/", element="meta_robots", state="added"
            )
        ],
    )
    assert check_A08(ctx) is not None


def test_check_A08_negative() -> None:
    ctx = CrawlContext(
        url="http://localhost/",
        render_diffs=[
            UrlRenderDiffRow(
                url="http://localhost/", element="meta_robots", state="unchanged"
            )
        ],
    )
    assert check_A08(ctx) is None


def test_check_A08_boundary() -> None:
    ctx = CrawlContext(
        url="http://localhost/",
        render_diffs=[
            UrlRenderDiffRow(url="http://localhost/", element="h1", state="added")
        ],
    )
    assert check_A08(ctx) is None


# A09
def test_check_A09_positive() -> None:
    row = _mock_url_row(inlink_count=0, status=200, indexable=True)
    row.in_sitemap = True
    ctx = CrawlContext(url="http://localhost/", url_row=row)
    assert check_A09(ctx) is not None


def test_check_A09_negative() -> None:
    row = _mock_url_row(inlink_count=5, status=200, indexable=True)
    row.in_sitemap = True
    ctx = CrawlContext(url="http://localhost/", url_row=row)
    assert check_A09(ctx) is None


def test_check_A09_boundary() -> None:
    row = _mock_url_row(inlink_count=0, status=200, indexable=True)
    row.in_sitemap = False
    ctx = CrawlContext(url="http://localhost/", url_row=row)
    assert check_A09(ctx) is None


# A10
def test_check_A10_positive() -> None:
    row = _mock_url_row(indexable=True)
    row.depth = 5
    ctx = CrawlContext(url="http://localhost/", url_row=row)
    assert check_A10(ctx) is not None


def test_check_A10_negative() -> None:
    row = _mock_url_row(indexable=True)
    row.depth = 4
    ctx = CrawlContext(url="http://localhost/", url_row=row)
    assert check_A10(ctx) is None


def test_check_A10_boundary() -> None:
    row = _mock_url_row(indexable=False)
    row.depth = 5
    ctx = CrawlContext(url="http://localhost/", url_row=row)
    assert check_A10(ctx) is None


# A11
def test_check_A11_positive() -> None:
    ctx = CrawlContext(
        url="http://localhost/?sort=price", url_row=_mock_url_row(indexable=True)
    )
    assert check_A11(ctx) is not None


def test_check_A11_negative() -> None:
    ctx = CrawlContext(url="http://localhost/", url_row=_mock_url_row(indexable=True))
    assert check_A11(ctx) is None


def test_check_A11_boundary() -> None:
    ctx = CrawlContext(
        url="http://localhost/?sort=price", url_row=_mock_url_row(indexable=False)
    )
    assert check_A11(ctx) is None


# A12
def test_check_A12() -> None:
    assert check_A12(CrawlContext(url="http://localhost/")) is None


# A13
def test_check_A13_positive() -> None:
    html = '<html><body><a href="/important" rel="nofollow">Link</a></body></html>'
    ctx = CrawlContext(url="http://localhost/", raw_html=html)
    assert check_A13(ctx) is not None


def test_check_A13_negative() -> None:
    html = '<html><body><a href="/important" rel="follow">Link</a></body></html>'
    ctx = CrawlContext(url="http://localhost/", raw_html=html)
    assert check_A13(ctx) is None


def test_check_A13_boundary() -> None:
    html = '<html><body><a rel="nofollow" href="/important">Link</a></body></html>'
    ctx = CrawlContext(url="http://localhost/", raw_html=html)
    assert check_A13(ctx) is not None


# A14
def test_check_A14_positive() -> None:
    ctx = CrawlContext(
        url="http://localhost/",
        url_row=_mock_url_row(meta_robots="nosnippet", indexable=True),
    )
    assert check_A14(ctx) is not None


def test_check_A14_negative() -> None:
    ctx = CrawlContext(
        url="http://localhost/",
        url_row=_mock_url_row(meta_robots="index", indexable=True),
    )
    assert check_A14(ctx) is None


def test_check_A14_boundary() -> None:
    ctx = CrawlContext(
        url="http://localhost/",
        url_row=_mock_url_row(meta_robots="nosnippet", indexable=False),
    )
    assert check_A14(ctx) is None


# A15
def test_check_A15() -> None:
    assert check_A15(CrawlContext(url="http://localhost/")) is None


def test_check_A07_no_fp_when_header_absent() -> None:
    # meta-only robots (no X-Robots-Tag) is not a conflict — was a sitewide FP.
    ctx = CrawlContext(
        url="http://localhost/",
        url_row=_mock_url_row(meta_robots="noindex,nofollow", x_robots=None),
    )
    assert check_A07(ctx) is None
