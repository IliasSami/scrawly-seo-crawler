from pathlib import Path

from sentinelseo.checks.domain_i.checks import (
    check_I01,
    check_I02,
    check_I03,
    check_I04,
    check_I05,
    check_I06,
    check_I07,
    check_I08,
)
from sentinelseo.checks.registry import CrawlContext


def test_check_I01_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_I01(ctx)
    assert result is not None
    assert result.check_id == "I01"


def test_check_I01_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_I01(ctx)
    assert result is None


def test_check_I02_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_I02(ctx)
    assert result is not None
    assert result.check_id == "I02"


def test_check_I02_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_I02(ctx)
    assert result is None


def test_check_I03_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_I03(ctx)
    assert result is not None
    assert result.check_id == "I03"


def test_check_I03_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_I03(ctx)
    assert result is None


def test_check_I04_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_I04(ctx)
    assert result is not None
    assert result.check_id == "I04"


def test_check_I04_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_I04(ctx)
    assert result is None


def test_check_I05_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_I05(ctx)
    assert result is not None
    assert result.check_id == "I05"


def test_check_I05_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_I05(ctx)
    assert result is None


def test_check_I06_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_I06(ctx)
    assert result is not None
    assert result.check_id == "I06"


def test_check_I06_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_I06(ctx)
    assert result is None


def test_check_I07_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_I07(ctx)
    assert result is not None
    assert result.check_id == "I07"


def test_check_I07_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_I07(ctx)
    assert result is None


def test_check_I08_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_I08(ctx)
    assert result is not None
    assert result.check_id == "I08"


def test_check_I08_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_I08(ctx)
    assert result is None
