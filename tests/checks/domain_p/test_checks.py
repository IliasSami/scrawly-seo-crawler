from sentinelseo.checks.domain_p.checks import (
    check_P01,
    check_P02,
    check_P03,
    check_P04,
    check_P05,
    check_P06,
)
from sentinelseo.checks.registry import CrawlContext


def test_check_P01_positive() -> None:
    raw_html = "<html><body>" + ("a" * 100) + "</body></html>"
    rendered_html = "<html><body>" + ("a" * 600) + "</body></html>"
    ctx = CrawlContext(
        url="http://example.com", raw_html=raw_html, rendered_html=rendered_html
    )
    finding = check_P01(ctx)
    assert finding is not None
    assert finding.check_id == "P01"
    assert "raw_body_length" in finding.evidence


def test_check_P01_negative() -> None:
    raw_html = "<html><body>" + ("a" * 300) + "</body></html>"
    rendered_html = "<html><body>" + ("a" * 300) + "</body></html>"
    ctx = CrawlContext(
        url="http://example.com", raw_html=raw_html, rendered_html=rendered_html
    )
    finding = check_P01(ctx)
    assert finding is None


def test_check_P02_positive() -> None:
    raw_html = "<html><body><a href='http://external.com'>Ext</a></body></html>"
    rendered_html = "<html><body><a href='http://external.com'>Ext</a><a href='/internal'>Int</a></body></html>"  # noqa: E501
    ctx = CrawlContext(
        url="http://example.com", raw_html=raw_html, rendered_html=rendered_html
    )
    finding = check_P02(ctx)
    assert finding is not None
    assert finding.check_id == "P02"
    assert "/internal" in finding.evidence["injected_internal_links"]


def test_check_P02_negative() -> None:
    raw_html = "<html><body><a href='/internal'>Int</a></body></html>"
    rendered_html = "<html><body><a href='/internal'>Int</a></body></html>"
    ctx = CrawlContext(
        url="http://example.com", raw_html=raw_html, rendered_html=rendered_html
    )
    finding = check_P02(ctx)
    assert finding is None


def test_check_P03_positive() -> None:
    raw_html = "<html><head><title>Old</title></head><body></body></html>"
    rendered_html = "<html><head><title>New</title></head><body></body></html>"
    ctx = CrawlContext(
        url="http://example.com", raw_html=raw_html, rendered_html=rendered_html
    )
    finding = check_P03(ctx)
    assert finding is not None
    assert finding.check_id == "P03"
    assert "title" in finding.evidence["diffs"]


def test_check_P03_negative() -> None:
    raw_html = "<html><head><title>Same</title></head><body></body></html>"
    rendered_html = "<html><head><title>Same</title></head><body></body></html>"
    ctx = CrawlContext(
        url="http://example.com", raw_html=raw_html, rendered_html=rendered_html
    )
    finding = check_P03(ctx)
    assert finding is None


def test_check_P04_positive() -> None:
    ctx = CrawlContext(url="http://example.com")
    finding = check_P04(ctx)
    assert finding is None


def test_check_P04_negative() -> None:
    ctx = CrawlContext(url="http://example.com")
    finding = check_P04(ctx)
    assert finding is None


def test_check_P05_positive() -> None:
    ctx = CrawlContext(url="http://example.com")
    finding = check_P05(ctx)
    assert finding is None


def test_check_P05_negative() -> None:
    ctx = CrawlContext(url="http://example.com")
    finding = check_P05(ctx)
    assert finding is None


def test_check_P06_positive() -> None:
    ctx = CrawlContext(url="http://example.com")
    finding = check_P06(ctx)
    assert finding is None


def test_check_P06_negative() -> None:
    ctx = CrawlContext(url="http://example.com")
    finding = check_P06(ctx)
    assert finding is None
