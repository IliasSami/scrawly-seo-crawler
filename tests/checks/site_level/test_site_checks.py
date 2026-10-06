from typing import Any

from datasketch import MinHash  # type: ignore

import sentinelseo.checks.site_level.checks  # noqa: F401
from sentinelseo.audit.context import SiteContext
from sentinelseo.checks.registry import CrawlContext
from sentinelseo.checks.site_level.registry import get_site_level_checks
from sentinelseo.crawl.models import URLRow


def _mock_url_row(**kwargs: Any) -> URLRow:
    row = URLRow(
        address="http://test.com", status=200, redirect_chain=[], title="", meta_desc="",
        canonical="", meta_robots="", x_robots="", h1=[], h2=[], h3=[], h4=[], h5=[], h6=[],
        word_count=0, content_hash="", near_dup_cluster="", ttfb=0.0, size=0, inlink_count=0,
        outlink_count=0, indexable=True, indexability_reason=None
    )
    for k, v in kwargs.items():
        setattr(row, k, v)
    return row

def test_D02_duplicate_titles() -> None:
    checks = get_site_level_checks()
    fn = checks["D02"][1]

    # 3 pages: 2 with same title
    ctx = SiteContext("http://test.com", {
        "url1": CrawlContext(url="url1", url_row=_mock_url_row(title="Dup Title")),
        "url2": CrawlContext(url="url2", url_row=_mock_url_row(title="Dup Title")),
        "url3": CrawlContext(url="url3", url_row=_mock_url_row(title="Unique Title")),
    })

    res = list(fn(ctx))
    assert len(res) == 2
    assert "url1" in res[0].affected_urls or "url2" in res[0].affected_urls

def test_D06_title_same_as_h1_sitewide() -> None:
    checks = get_site_level_checks()
    fn = checks["D06"][1]

    ctx = SiteContext("http://test.com", {
        "url1": CrawlContext(url="url1", url_row=_mock_url_row(title="Same", h1=["Same"])),
        "url2": CrawlContext(url="url2", url_row=_mock_url_row(title="Same2", h1=["Same2"])),
    })
    res = list(fn(ctx))
    assert len(res) == 2  # one finding for each URL

    # If one page differs, it doesn't fire
    ctx.pages["url2"] = CrawlContext(url="url2", url_row=_mock_url_row(title="Diff", h1=["H1"]))
    res2 = list(fn(ctx))
    assert len(res2) == 0

def test_E02_near_dups() -> None:
    checks = get_site_level_checks()
    fn = checks["E02"][1]

    m1 = MinHash(num_perm=128)
    m1.update("hello world".encode('utf8'))
    m3 = MinHash(num_perm=128)
    m3.update("completely different text".encode('utf8'))

    # The crawler stores MinHash.hashvalues via .tobytes() (not pickle), so the
    # check must reconstruct from those raw bytes — mirror that here.
    ctx = SiteContext("http://test.com", {
        "url1": CrawlContext(url="url1", url_row=_mock_url_row(minhash=m1.hashvalues.tobytes())),
        "url2": CrawlContext(url="url2", url_row=_mock_url_row(minhash=m1.hashvalues.tobytes())),  # same hash
        "url3": CrawlContext(url="url3", url_row=_mock_url_row(minhash=m3.hashvalues.tobytes())),
    })

    res = list(fn(ctx))
    assert len(res) == 2  # url1 and url2 flag each other

def test_L01_disallow_slash() -> None:
    checks = get_site_level_checks()
    fn = checks["L01"][1]

    ctx = SiteContext("http://test.com", pages={}, robots_txt="User-agent: *\nDisallow: /")
    res = list(fn(ctx))
    assert len(res) == 1

    ctx2 = SiteContext("http://test.com", pages={}, robots_txt="User-agent: *\\nDisallow: /admin")
    assert len(list(fn(ctx2))) == 0

def test_I01_hreflang() -> None:
    checks = get_site_level_checks()
    fn = checks["I01"][1]

    ctx = SiteContext("http://test.com", {
        "url1": CrawlContext(url="url1", url_row=_mock_url_row(hreflang=[("en", "url2")])),
        "url2": CrawlContext(url="url2", url_row=_mock_url_row(hreflang=[])), # Missing return
    })
    res = list(fn(ctx))
    assert len(res) == 1
    assert "url2" in res[0].evidence["missing_return_from"]
