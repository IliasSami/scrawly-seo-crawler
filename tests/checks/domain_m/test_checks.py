from sentinelseo.checks.domain_m.checks import (
    check_M01,
    check_M02,
    check_M03,
    check_M04,
    check_M05,
    check_M06,
    check_M07,
    check_M08,
    check_M09,
    check_M10,
)
from sentinelseo.checks.registry import CrawlContext


def test_check_M01_positive() -> None:
    ctx = CrawlContext(url="http://example.com")
    finding = check_M01(ctx)
    assert finding is not None
    assert finding.check_id == "M01"
    assert finding.affected_urls == ["http://example.com"]


def test_check_M01_negative() -> None:
    ctx = CrawlContext(url="https://example.com")
    finding = check_M01(ctx)
    assert finding is None


def test_check_M02_positive() -> None:
    html = '<html><body><img src="http://example.com/img.jpg"></body></html>'
    ctx = CrawlContext(url="https://example.com", raw_html=html)
    finding = check_M02(ctx)
    assert finding is not None
    assert finding.check_id == "M02"


def test_check_M02_negative() -> None:
    html = '<html><body><img src="https://example.com/img.jpg"></body></html>'
    ctx = CrawlContext(url="https://example.com", raw_html=html)
    finding = check_M02(ctx)
    assert finding is None


def test_check_M03_positive() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_M03(ctx) is None


def test_check_M03_negative() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_M03(ctx) is None


def test_check_M04_positive() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_M04(ctx) is None


def test_check_M04_negative() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_M04(ctx) is None


def test_check_M05_positive() -> None:
    html = '<html><body><script src="//example.com/script.js"></script></body></html>'
    ctx = CrawlContext(url="https://example.com", raw_html=html)
    finding = check_M05(ctx)
    assert finding is not None
    assert finding.check_id == "M05"


def test_check_M05_negative() -> None:
    html = '<html><body><script src="https://example.com/a.js"></script></body></html>'
    ctx = CrawlContext(url="https://example.com", raw_html=html)
    finding = check_M05(ctx)
    assert finding is None


def test_check_M06_positive() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_M06(ctx) is None


def test_check_M06_negative() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_M06(ctx) is None


def test_check_M07_positive() -> None:
    html = (
        '<html><body><a href="https://other.com" target="_blank">Link</a></body></html>'
    )
    ctx = CrawlContext(url="https://example.com", raw_html=html)
    finding = check_M07(ctx)
    assert finding is not None
    assert finding.check_id == "M07"


def test_check_M07_negative() -> None:
    html = (
        '<html><body><a href="https://other.com" '
        'target="_blank" rel="noopener">Link</a></body></html>'
    )
    ctx = CrawlContext(url="https://example.com", raw_html=html)
    finding = check_M07(ctx)
    assert finding is None

    html2 = '<html><body><a href="https://other.com">Link</a></body></html>'
    ctx2 = CrawlContext(url="https://example.com", raw_html=html2)
    assert check_M07(ctx2) is None


def test_check_M08_positive() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_M08(ctx) is None


def test_check_M08_negative() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_M08(ctx) is None


def test_check_M09_positive() -> None:
    html = '<html><head><meta name="generator" content="WordPress 6.2"></head></html>'
    ctx = CrawlContext(url="https://example.com", raw_html=html)
    finding = check_M09(ctx)
    assert finding is not None
    assert finding.check_id == "M09"

    html2 = "WordPress is installed here"
    ctx2 = CrawlContext(url="https://example.com/readme.html", raw_html=html2)
    finding2 = check_M09(ctx2)
    assert finding2 is not None


def test_check_M09_negative() -> None:
    html = '<html><head><meta name="generator" content="Hugo 1.0"></head></html>'
    ctx = CrawlContext(url="https://example.com", raw_html=html)
    finding = check_M09(ctx)
    assert finding is None

    html2 = "Welcome to our site"
    ctx2 = CrawlContext(url="https://example.com/readme.html", raw_html=html2)
    assert check_M09(ctx2) is None


def test_check_M10_positive() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_M10(ctx) is None


def test_check_M10_negative() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_M10(ctx) is None
