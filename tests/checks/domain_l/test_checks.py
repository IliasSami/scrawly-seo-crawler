from pathlib import Path

from sentinelseo.checks.domain_l.checks import (
    check_L01,
    check_L02,
    check_L03,
    check_L04,
    check_L05,
    check_L06,
    check_L07,
)
from sentinelseo.checks.registry import CrawlContext


def test_check_L01_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_L01(ctx)
    assert result is not None
    assert result.check_id == "L01"


def test_check_L01_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_L01(ctx)
    assert result is None


def test_check_L02_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_L02(ctx)
    assert result is not None
    assert result.check_id == "L02"


def test_check_L02_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_L02(ctx)
    assert result is None


def test_check_L03_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_L03(ctx)
    assert result is not None
    assert result.check_id == "L03"


def test_check_L03_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_L03(ctx)
    assert result is None


def test_check_L04_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_L04(ctx)
    assert result is not None
    assert result.check_id == "L04"


def test_check_L04_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_L04(ctx)
    assert result is None


def test_check_L05_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_L05(ctx)
    assert result is not None
    assert result.check_id == "L05"


def test_check_L05_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_L05(ctx)
    assert result is None


def test_check_L06_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_L06(ctx)
    assert result is not None
    assert result.check_id == "L06"


def test_check_L06_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_L06(ctx)
    assert result is None


def test_check_L07_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_L07(ctx)
    assert result is not None
    assert result.check_id == "L07"


def test_check_L07_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_L07(ctx)
    assert result is None
