from pathlib import Path

from sentinelseo.checks.domain_j.checks import (
    check_J01,
    check_J02,
    check_J03,
    check_J04,
    check_J05,
    check_J06,
    check_J07,
    check_J08,
    check_J09,
    check_J10,
    check_J11,
    check_J12,
    check_J13,
)
from sentinelseo.checks.registry import CrawlContext


def test_check_J01_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J01(ctx)
    assert result is not None
    assert result.check_id == "J01"


def test_check_J01_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J01(ctx)
    assert result is None


def test_check_J02_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J02(ctx)
    assert result is not None
    assert result.check_id == "J02"


def test_check_J02_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J02(ctx)
    assert result is None


def test_check_J03_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J03(ctx)
    assert result is not None
    assert result.check_id == "J03"


def test_check_J03_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J03(ctx)
    assert result is None


def test_check_J04_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J04(ctx)
    assert result is not None
    assert result.check_id == "J04"


def test_check_J04_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J04(ctx)
    assert result is None


def test_check_J05_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J05(ctx)
    assert result is not None
    assert result.check_id == "J05"


def test_check_J05_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J05(ctx)
    assert result is None


def test_check_J06_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J06(ctx)
    assert result is not None
    assert result.check_id == "J06"


def test_check_J06_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J06(ctx)
    assert result is None


def test_check_J07_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J07(ctx)
    assert result is not None
    assert result.check_id == "J07"


def test_check_J07_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J07(ctx)
    assert result is None


def test_check_J08_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J08(ctx)
    assert result is not None
    assert result.check_id == "J08"


def test_check_J08_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J08(ctx)
    assert result is None


def test_check_J09_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J09(ctx)
    assert result is not None
    assert result.check_id == "J09"


def test_check_J09_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J09(ctx)
    assert result is None


def test_check_J10_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J10(ctx)
    assert result is not None
    assert result.check_id == "J10"


def test_check_J10_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J10(ctx)
    assert result is None


def test_check_J11_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J11(ctx)
    assert result is not None
    assert result.check_id == "J11"


def test_check_J11_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J11(ctx)
    assert result is None


def test_check_J12_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J12(ctx)
    assert result is not None
    assert result.check_id == "J12"


def test_check_J12_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J12(ctx)
    assert result is None


def test_check_J13_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J13(ctx)
    assert result is not None
    assert result.check_id == "J13"


def test_check_J13_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_J13(ctx)
    assert result is None
