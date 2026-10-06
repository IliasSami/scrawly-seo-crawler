from pathlib import Path

from sentinelseo.checks.domain_k.checks import (
    check_K01,
    check_K02,
    check_K03,
    check_K04,
    check_K05,
    check_K06,
    check_K07,
    check_K08,
    check_K09,
    check_K10,
)
from sentinelseo.checks.registry import CrawlContext


def test_check_K01_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K01(ctx)
    assert result is not None
    assert result.check_id == "K01"


def test_check_K01_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K01(ctx)
    assert result is None


def test_check_K02_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K02(ctx)
    assert result is not None
    assert result.check_id == "K02"


def test_check_K02_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K02(ctx)
    assert result is None


def test_check_K03_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K03(ctx)
    assert result is not None
    assert result.check_id == "K03"


def test_check_K03_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K03(ctx)
    assert result is None


def test_check_K04_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K04(ctx)
    assert result is not None
    assert result.check_id == "K04"


def test_check_K04_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K04(ctx)
    assert result is None


def test_check_K05_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K05(ctx)
    assert result is not None
    assert result.check_id == "K05"


def test_check_K05_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K05(ctx)
    assert result is None


def test_check_K06_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K06(ctx)
    assert result is not None
    assert result.check_id == "K06"


def test_check_K06_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K06(ctx)
    assert result is None


def test_check_K07_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K07(ctx)
    assert result is not None
    assert result.check_id == "K07"


def test_check_K07_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K07(ctx)
    assert result is None


def test_check_K08_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K08(ctx)
    assert result is not None
    assert result.check_id == "K08"


def test_check_K08_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K08(ctx)
    assert result is None


def test_check_K09_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K09(ctx)
    assert result is not None
    assert result.check_id == "K09"


def test_check_K09_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K09(ctx)
    assert result is None


def test_check_K10_positive() -> None:
    html = Path("tests/fixtures/positive_all.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K10(ctx)
    assert result is not None
    assert result.check_id == "K10"


def test_check_K10_negative() -> None:
    html = Path("tests/fixtures/clean_page.html").read_text(encoding="utf-8")
    ctx = CrawlContext(url="http://localhost:8080/page", raw_html=html)
    result = check_K10(ctx)
    assert result is None
