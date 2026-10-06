import sys
from typing import Any
from unittest.mock import MagicMock

sys.modules['textstat'] = MagicMock()
textstat_mock: Any = sys.modules['textstat']
textstat_mock.flesch_reading_ease = MagicMock(return_value=20)

from sentinelseo.checks.domain_e.checks import (  # noqa: E402
    check_E01,
    check_E02,
    check_E03,
    check_E04,
    check_E05,
    check_E06,
    check_E07,
    check_E08,
    check_E09,
    check_E10,
    check_E11,
    check_E12,
)
from sentinelseo.checks.registry import CrawlContext  # noqa: E402
from sentinelseo.crawl.models import URLRow  # noqa: E402


def get_base_url_row() -> URLRow:
    return URLRow(
        address="https://example.com/test",
        status=200,
        redirect_chain=[],
        title="Test Page",
        meta_desc="Test description",
        canonical="https://example.com/test",
        meta_robots=None,
        x_robots=None,
        h1=["Test Page H1"],
        h2=[],
        h3=[],
        h4=[],
        h5=[],
        h6=[],
        word_count=500,
        content_hash="abc",
        near_dup_cluster="",
        ttfb=0.1,
        size=1024,
        inlink_count=1,
        outlink_count=1,
        indexable=True,
        indexability_reason=None,
    )


def test_deferred_checks() -> None:
    ctx = CrawlContext(url="https://example.com", url_row=get_base_url_row())
    assert check_E01(ctx) is None
    assert check_E02(ctx) is None
    assert check_E03(ctx) is None
    assert check_E05(ctx) is None
    assert check_E06(ctx) is None


# E04: Thin content
def test_check_E04_positive() -> None:
    row = get_base_url_row()
    row.word_count = 150
    ctx = CrawlContext(url="https://example.com/test", url_row=row)
    finding = check_E04(ctx)
    assert finding is not None
    assert finding.check_id == "E04"


def test_check_E04_negative() -> None:
    row = get_base_url_row()
    row.word_count = 300
    ctx = CrawlContext(url="https://example.com/test", url_row=row)
    assert check_E04(ctx) is None


def test_check_E04_boundary() -> None:
    row = get_base_url_row()
    row.word_count = 200
    ctx = CrawlContext(url="https://example.com/test", url_row=row)
    assert check_E04(ctx) is None


# E07: Boilerplate-heavy pages
def test_check_E07_positive() -> None:
    row = get_base_url_row()
    row.word_count = 50
    html = "<html><body>" + "word " * 300 + "</body></html>"
    ctx = CrawlContext(url="https://example.com/test", url_row=row, raw_html=html)
    finding = check_E07(ctx)
    assert finding is not None
    assert finding.check_id == "E07"


def test_check_E07_negative() -> None:
    row = get_base_url_row()
    row.word_count = 150
    html = "<html><body>" + "word " * 300 + "</body></html>"
    ctx = CrawlContext(url="https://example.com/test", url_row=row, raw_html=html)
    assert check_E07(ctx) is None


def test_check_E07_boundary() -> None:
    row = get_base_url_row()
    row.word_count = 50
    html = "<html><body>" + "word " * 199 + "</body></html>"
    ctx = CrawlContext(url="https://example.com/test", url_row=row, raw_html=html)
    assert check_E07(ctx) is None


# E08: Lorem ipsum
def test_check_E08_positive() -> None:
    ctx = CrawlContext(
        url="https://example.com/test", raw_html="<div>Lorem ipsum dolor sit amet</div>"
    )
    finding = check_E08(ctx)
    assert finding is not None
    assert finding.check_id == "E08"


def test_check_E08_negative() -> None:
    ctx = CrawlContext(
        url="https://example.com/test", raw_html="<div>Real content goes here</div>"
    )
    assert check_E08(ctx) is None


def test_check_E08_boundary() -> None:
    ctx = CrawlContext(
        url="https://example.com/test", raw_html="<div>loremt ipsum</div>"
    )
    assert check_E08(ctx) is None


# E09: Readability
def test_check_E09_positive() -> None:
    row = get_base_url_row()
    row.word_count = 150
    textstat_mock.flesch_reading_ease.return_value = 20
    ctx = CrawlContext(
        url="https://example.com/test", url_row=row, raw_html="<div>Hard text</div>"
    )
    finding = check_E09(ctx)
    assert finding is not None
    assert finding.check_id == "E09"


def test_check_E09_negative() -> None:
    row = get_base_url_row()
    row.word_count = 150
    textstat_mock.flesch_reading_ease.return_value = 40
    ctx = CrawlContext(
        url="https://example.com/test", url_row=row, raw_html="<div>Easy text</div>"
    )
    assert check_E09(ctx) is None


def test_check_E09_boundary() -> None:
    row = get_base_url_row()
    row.word_count = 99
    textstat_mock.flesch_reading_ease.return_value = 20
    ctx = CrawlContext(
        url="https://example.com/test", url_row=row, raw_html="<div>Hard text</div>"
    )
    assert check_E09(ctx) is None


# E10: Low text-to-HTML ratio
def test_check_E10_positive() -> None:
    row = get_base_url_row()
    row.size = 10000
    html = "<div>" + "word " * 10 + "</div>"
    ctx = CrawlContext(url="https://example.com/test", url_row=row, raw_html=html)
    finding = check_E10(ctx)
    assert finding is not None
    assert finding.check_id == "E10"


def test_check_E10_negative() -> None:
    row = get_base_url_row()
    row.size = 500
    html = "<div>" + "word " * 100 + "</div>"
    ctx = CrawlContext(url="https://example.com/test", url_row=row, raw_html=html)
    assert check_E10(ctx) is None


def test_check_E10_boundary() -> None:
    row = get_base_url_row()
    row.size = 1000
    html = "a" * 100
    ctx = CrawlContext(url="https://example.com/test", url_row=row, raw_html=html)
    assert check_E10(ctx) is None


# E11: Content hidden
def test_check_E11_positive() -> None:
    row = get_base_url_row()
    row.word_count = 150
    html = "<div class='tab-pane'></div><div class='collapse'></div><div style='display: none;'></div>"
    ctx = CrawlContext(url="https://example.com/test", url_row=row, raw_html=html)
    finding = check_E11(ctx)
    assert finding is not None
    assert finding.check_id == "E11"


def test_check_E11_negative() -> None:
    row = get_base_url_row()
    row.word_count = 150
    html = "<div>visible</div>"
    ctx = CrawlContext(url="https://example.com/test", url_row=row, raw_html=html)
    assert check_E11(ctx) is None


def test_check_E11_boundary() -> None:
    row = get_base_url_row()
    row.word_count = 99
    html = "<div class='tab-pane'></div><div class='collapse'></div><div style='display: none;'></div>"
    ctx = CrawlContext(url="https://example.com/test", url_row=row, raw_html=html)
    assert check_E11(ctx) is None


# E12: Missing dates
def test_check_E12_positive() -> None:
    row = get_base_url_row()
    row.word_count = 350
    sd = [{"@type": "Article", "headline": "Test"}]
    ctx = CrawlContext(url="https://example.com/test", url_row=row, structured_data=sd)
    finding = check_E12(ctx)
    assert finding is not None
    assert finding.check_id == "E12"


def test_check_E12_negative() -> None:
    row = get_base_url_row()
    row.word_count = 350
    sd = [{"@type": "Article", "datePublished": "2024-01-01"}]
    ctx = CrawlContext(url="https://example.com/test", url_row=row, structured_data=sd)
    assert check_E12(ctx) is None


def test_check_E12_boundary() -> None:
    row = get_base_url_row()
    row.word_count = 300
    sd = [{"@type": "Article", "headline": "Test"}]
    ctx = CrawlContext(url="https://example.com/test", url_row=row, structured_data=sd)
    assert check_E12(ctx) is None


def test_check_E08_no_false_positive_on_minified_js() -> None:
    # Minified JS / data with runs of x's must NOT trip the placeholder detector.
    html = '<div>Real page</div><script>var a="xxxxxxxx";function fn(){}</script>'
    from sentinelseo.checks.domain_e.checks import check_E08
    from sentinelseo.checks.registry import CrawlContext
    assert check_E08(CrawlContext(url="https://x.com/", raw_html=html)) is None
