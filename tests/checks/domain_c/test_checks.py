from typing import Any

from sentinelseo.checks.domain_c.checks import (
    check_C01,
    check_C02,
    check_C03,
    check_C04,
    check_C05,
    check_C06,
    check_C07,
    check_C08,
    check_C09,
    check_C10,
    check_C11,
)
from sentinelseo.checks.registry import CrawlContext
from sentinelseo.crawl.models import UrlRenderDiffRow, URLRow


def get_base_url_row(**kwargs: Any) -> URLRow:
    defaults: dict[str, Any] = {
        "address": "https://example.com/page",
        "status": 200,
        "redirect_chain": [],
        "title": "Test Title",
        "meta_desc": "Desc",
        "canonical": "https://example.com/page",
        "meta_robots": "",
        "x_robots": "",
        "h1": [],
        "h2": [],
        "h3": [],
        "h4": [],
        "h5": [],
        "h6": [],
        "word_count": 500,
        "content_hash": "abc",
        "near_dup_cluster": "",
        "ttfb": 0.1,
        "size": 1024,
        "inlink_count": 1,
        "outlink_count": 1,
        "indexable": True,
        "indexability_reason": None,
        "internal_links": [],
        "external_links": [],
    }
    defaults.update(kwargs)
    return URLRow(**defaults)


# C01
def test_check_C01_positive() -> None:
    row = get_base_url_row(canonical=None, status=200, meta_robots="")
    ctx = CrawlContext(url="https://example.com/page", url_row=row)
    assert check_C01(ctx) is not None

def test_check_C01_negative() -> None:
    row = get_base_url_row(canonical="https://example.com/page", status=200, meta_robots="")  # noqa: E501
    ctx = CrawlContext(url="https://example.com/page", url_row=row)
    assert check_C01(ctx) is None

def test_check_C01_boundary() -> None:
    row = get_base_url_row(canonical=None, status=200, meta_robots="noindex, nofollow")
    ctx = CrawlContext(url="https://example.com/page", url_row=row)
    assert check_C01(ctx) is None


# C02 (Deferred)
def test_check_C02_deferred() -> None:
    ctx = CrawlContext(url="https://example.com/page", url_row=get_base_url_row())
    assert check_C02(ctx) is None

# C03 (Deferred)
def test_check_C03_deferred() -> None:
    ctx = CrawlContext(url="https://example.com/page", url_row=get_base_url_row())
    assert check_C03(ctx) is None


# C04
def test_check_C04_positive() -> None:
    row = get_base_url_row(status=404, canonical="https://example.com/page")
    ctx = CrawlContext(url="https://example.com/page", url_row=row)
    assert check_C04(ctx) is not None

def test_check_C04_negative() -> None:
    row = get_base_url_row(status=200, canonical="https://example.com/page")
    ctx = CrawlContext(url="https://example.com/page", url_row=row)
    assert check_C04(ctx) is None

def test_check_C04_boundary() -> None:
    row = get_base_url_row(status=301, canonical="https://example.com/page")
    ctx = CrawlContext(url="https://example.com/page", url_row=row)
    assert check_C04(ctx) is not None


# C05
def test_check_C05_positive() -> None:
    html = '<link rel="canonical" href="https://example.com/p1"><link rel="canonical" href="https://example.com/p2">'  # noqa: E501
    ctx = CrawlContext(url="https://example.com/page", raw_html=html, url_row=get_base_url_row())  # noqa: E501
    assert check_C05(ctx) is not None

def test_check_C05_negative() -> None:
    html = '<link rel="canonical" href="https://example.com/page">'
    ctx = CrawlContext(url="https://example.com/page", raw_html=html, url_row=get_base_url_row())  # noqa: E501
    assert check_C05(ctx) is None

def test_check_C05_boundary() -> None:
    # Same canonical twice
    html = '<link rel="canonical" href="https://example.com/p1"><link rel="canonical" href="https://example.com/p1">'  # noqa: E501
    ctx = CrawlContext(url="https://example.com/page", raw_html=html, url_row=get_base_url_row())  # noqa: E501
    assert check_C05(ctx) is None


# C06
def test_check_C06_positive() -> None:
    ctx = CrawlContext(url="https://example.com/page", url_row=get_base_url_row(canonical="https://example.com/page2"))  # noqa: E501
    ctx.url_row.headers = {"link": '<https://example.com/page1>; rel="canonical"'}
    assert check_C06(ctx) is not None

def test_check_C06_negative() -> None:
    ctx = CrawlContext(url="https://example.com/page", url_row=get_base_url_row(canonical="https://example.com/page1"))  # noqa: E501
    ctx.url_row.headers = {"link": '<https://example.com/page1>; rel="canonical"'}
    assert check_C06(ctx) is None

def test_check_C06_boundary() -> None:
    ctx = CrawlContext(url="https://example.com/page", url_row=get_base_url_row(canonical="https://example.com/page"))  # noqa: E501
    ctx.url_row.headers = {}
    assert check_C06(ctx) is None


# C07
def test_check_C07_positive() -> None:
    diff = UrlRenderDiffRow(url="https://example.com/page", element="canonical", state="modified")  # noqa: E501
    ctx = CrawlContext(url="https://example.com/page", render_diffs=[diff], url_row=get_base_url_row())  # noqa: E501
    assert check_C07(ctx) is not None

def test_check_C07_negative() -> None:
    diff = UrlRenderDiffRow(url="https://example.com/page", element="canonical", state="unchanged")  # noqa: E501
    ctx = CrawlContext(url="https://example.com/page", render_diffs=[diff], url_row=get_base_url_row())  # noqa: E501
    assert check_C07(ctx) is None

def test_check_C07_boundary() -> None:
    diff = UrlRenderDiffRow(url="https://example.com/page", element="link", state="deleted")  # noqa: E501
    ctx = CrawlContext(url="https://example.com/page", render_diffs=[diff], url_row=get_base_url_row())  # noqa: E501
    assert check_C07(ctx) is not None


# C08
def test_check_C08_positive() -> None:
    row = get_base_url_row(canonical="https://other.com/page")
    ctx = CrawlContext(url="https://example.com/page", url_row=row)
    assert check_C08(ctx) is not None

def test_check_C08_negative() -> None:
    row = get_base_url_row(canonical="https://example.com/page")
    ctx = CrawlContext(url="https://example.com/page", url_row=row)
    assert check_C08(ctx) is None

def test_check_C08_boundary() -> None:
    # Subdomain is same registrable domain
    row = get_base_url_row(canonical="https://sub.example.com/page")
    ctx = CrawlContext(url="https://example.com/page", url_row=row)
    assert check_C08(ctx) is None


# C09
def test_check_C09_positive() -> None:
    row = get_base_url_row(canonical="/page")
    row.canonical_in_head = True
    ctx = CrawlContext(url="https://example.com/page", url_row=row)
    assert check_C09(ctx) is not None

def test_check_C09_negative() -> None:
    row = get_base_url_row(canonical="https://example.com/page")
    row.canonical_in_head = True
    ctx = CrawlContext(url="https://example.com/page", url_row=row)
    assert check_C09(ctx) is None

def test_check_C09_boundary() -> None:
    # Absolute URL but with fragment
    row = get_base_url_row(canonical="https://example.com/page#frag")
    row.canonical_in_head = True
    ctx = CrawlContext(url="https://example.com/page", url_row=row)
    assert check_C09(ctx) is not None


# C10
def test_check_C10_positive() -> None:
    row = get_base_url_row(indexable=True, canonical="https://example.com/page?utm_source=test")  # noqa: E501
    ctx = CrawlContext(url="https://example.com/page?utm_source=test", url_row=row)
    assert check_C10(ctx) is not None

def test_check_C10_negative() -> None:
    row = get_base_url_row(indexable=True, canonical="https://example.com/page")
    ctx = CrawlContext(url="https://example.com/page?utm_source=test", url_row=row)
    assert check_C10(ctx) is None

def test_check_C10_boundary() -> None:
    row = get_base_url_row(indexable=False, canonical="https://example.com/page?utm_source=test")  # noqa: E501
    ctx = CrawlContext(url="https://example.com/page?utm_source=test", url_row=row)
    assert check_C10(ctx) is None


# C11
def test_check_C11_positive() -> None:
    row = get_base_url_row(canonical="https://example.com/blog/")
    ctx = CrawlContext(url="https://example.com/blog/?page=2", url_row=row)
    assert check_C11(ctx) is not None

def test_check_C11_negative() -> None:
    row = get_base_url_row(canonical="https://example.com/blog/?page=2")
    ctx = CrawlContext(url="https://example.com/blog/?page=2", url_row=row)
    assert check_C11(ctx) is None

def test_check_C11_boundary() -> None:
    row = get_base_url_row(canonical="https://example.com/blog/?page=1")
    ctx = CrawlContext(url="https://example.com/blog/?page=2", url_row=row)
    assert check_C11(ctx) is None
