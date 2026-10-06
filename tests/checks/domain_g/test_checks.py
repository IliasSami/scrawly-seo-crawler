from pathlib import Path

from sentinelseo.checks.domain_g.checks import (
    check_G01,
    check_G02,
    check_G03,
    check_G04,
    check_G05,
    check_G06,
)
from sentinelseo.checks.registry import CrawlContext


def test_check_G01_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_G01(ctx)
    assert result is not None
    assert result.check_id == "G01"


def test_check_G01_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_G01(ctx)
    assert result is None


def test_check_G02_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_G02(ctx)
    assert result is not None
    assert result.check_id == "G02"


def test_check_G02_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_G02(ctx)
    assert result is None


def test_check_G03_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_G03(ctx)
    assert result is not None
    assert result.check_id == "G03"


def test_check_G03_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_G03(ctx)
    assert result is None


def test_check_G04_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_G04(ctx)
    assert result is not None
    assert result.check_id == "G04"


def test_check_G04_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_G04(ctx)
    assert result is None


def test_check_G05_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_G05(ctx)
    assert result is not None
    assert result.check_id == "G05"


def test_check_G05_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_G05(ctx)
    assert result is None


def test_check_G06_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_G06(ctx)
    assert result is not None
    assert result.check_id == "G06"


def test_check_G06_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_G06(ctx)
    assert result is None
