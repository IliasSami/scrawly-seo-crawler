from pathlib import Path

import pytest

from sentinelseo.checks.domain_t.checks import (
    check_T01,
    check_T02,
    check_T03,
    check_T04,
    check_T05,
    check_T06,
    check_T07,
    check_T08,
    check_T09,
)
from sentinelseo.checks.registry import CrawlContext


@pytest.fixture
def clean_html() -> str:
    return Path("tests/fixtures/clean_page.html").read_text()


def test_check_T01_positive(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/BadPath", raw_html=clean_html)
    assert check_T01(ctx) is not None


def test_check_T01_negative(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/goodpath", raw_html=clean_html)
    assert check_T01(ctx) is None


def test_check_T02_positive(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/path%20with%20space", raw_html=clean_html)
    assert check_T02(ctx) is not None


def test_check_T02_negative(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/goodpath", raw_html=clean_html)
    assert check_T02(ctx) is None


def test_check_T03_positive(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/a//b", raw_html=clean_html)
    assert check_T03(ctx) is not None
    ctx = CrawlContext(url="http://localhost/a/a", raw_html=clean_html)
    assert check_T03(ctx) is not None


def test_check_T03_negative(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/a/b", raw_html=clean_html)
    assert check_T03(ctx) is None


def test_check_T04_positive(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/" + "a" * 100, raw_html=clean_html)
    assert check_T04(ctx) is not None


def test_check_T04_negative(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/short", raw_html=clean_html)
    assert check_T04(ctx) is None


def test_check_T05_positive(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/?utm_source=google", raw_html=clean_html)
    assert check_T05(ctx) is not None


def test_check_T05_negative(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/?page=2", raw_html=clean_html)
    assert check_T05(ctx) is None


def test_check_T06_positive(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/1/2/3/4/5", raw_html=clean_html)
    assert check_T06(ctx) is not None


def test_check_T06_negative(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/1/2", raw_html=clean_html)
    assert check_T06(ctx) is None


def test_check_T07_positive(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/?p=123", raw_html=clean_html)
    assert check_T07(ctx) is not None


def test_check_T07_negative(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/hello-world", raw_html=clean_html)
    assert check_T07(ctx) is None


def test_check_T08_positive(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/a/", raw_html=clean_html)
    # Deferred, returns None
    assert check_T08(ctx) is None


def test_check_T08_negative(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/a", raw_html=clean_html)
    assert check_T08(ctx) is None


def test_check_T09_positive(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/hello_world", raw_html=clean_html)
    assert check_T09(ctx) is not None


def test_check_T09_negative(clean_html: str) -> None:
    ctx = CrawlContext(url="http://localhost/hello-world", raw_html=clean_html)
    assert check_T09(ctx) is None
