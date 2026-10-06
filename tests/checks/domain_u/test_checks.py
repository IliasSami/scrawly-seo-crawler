from pathlib import Path

from sentinelseo.checks.domain_u.checks import (
    check_U01,
    check_U02,
    check_U03,
    check_U04,
    check_U05,
)
from sentinelseo.checks.registry import CrawlContext


def get_fixture(name: str) -> str:
    return Path(f"tests/fixtures/{name}").read_text()


def test_check_U01_positive() -> None:
    html = get_fixture("u01_fail.html")
    ctx = CrawlContext(url="http://localhost/page/2", raw_html=html)
    assert check_U01(ctx) is not None


def test_check_U01_negative() -> None:
    html = get_fixture("clean_page.html")
    ctx = CrawlContext(url="http://localhost/page/2", raw_html=html)
    assert check_U01(ctx) is None


def test_check_U02_positive() -> None:
    html = get_fixture("u02_fail.html")
    ctx = CrawlContext(url="http://localhost/", raw_html=html)
    assert check_U02(ctx) is not None


def test_check_U02_negative() -> None:
    html = get_fixture("clean_page.html")
    ctx = CrawlContext(url="http://localhost/", raw_html=html)
    assert check_U02(ctx) is None


def test_check_U03_positive() -> None:
    html = get_fixture("u03_fail.html")
    ctx = CrawlContext(url="http://localhost/page/2", raw_html=html)
    assert check_U03(ctx) is not None


def test_check_U03_negative() -> None:
    html = get_fixture("u03_pass.html")
    ctx = CrawlContext(url="http://localhost/page/2", raw_html=html)
    assert check_U03(ctx) is None


def test_check_U04_positive() -> None:
    ctx = CrawlContext(url="http://localhost/", raw_html="")
    assert check_U04(ctx) is None


def test_check_U04_negative() -> None:
    ctx = CrawlContext(url="http://localhost/", raw_html="")
    assert check_U04(ctx) is None


def test_check_U05_positive() -> None:
    ctx = CrawlContext(url="http://localhost/", raw_html="")
    assert check_U05(ctx) is None


def test_check_U05_negative() -> None:
    ctx = CrawlContext(url="http://localhost/", raw_html="")
    assert check_U05(ctx) is None
