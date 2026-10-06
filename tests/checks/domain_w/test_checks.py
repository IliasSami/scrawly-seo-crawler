from pathlib import Path

from sentinelseo.checks.domain_w.checks import (
    check_W01,
    check_W02,
    check_W03,
    check_W04,
    check_W05,
)
from sentinelseo.checks.registry import CrawlContext


def get_fixture(name: str) -> str:
    return Path(f"tests/fixtures/{name}").read_text()


def test_check_W01_positive() -> None:
    html = get_fixture("w01_fail_missing.html")
    ctx = CrawlContext(url="http://localhost/", raw_html=html)
    assert check_W01(ctx) is not None
    html2 = get_fixture("w01_fail_dup.html")
    ctx2 = CrawlContext(url="http://localhost/", raw_html=html2)
    assert check_W01(ctx2) is not None


def test_check_W01_negative() -> None:
    html = '<html><head><script src="https://googletagmanager.com/gtm.js"></script></head><body></body></html>'  # noqa: E501
    ctx = CrawlContext(url="http://localhost/", raw_html=html)
    assert check_W01(ctx) is None


def test_check_W02_positive() -> None:
    ctx = CrawlContext(url="http://localhost/")
    assert check_W02(ctx) is None


def test_check_W02_negative() -> None:
    ctx = CrawlContext(url="http://localhost/")
    assert check_W02(ctx) is None


def test_check_W03_positive() -> None:
    html = get_fixture("w03_fail.html")
    ctx = CrawlContext(url="http://localhost/", raw_html=html)
    assert check_W03(ctx) is not None


def test_check_W03_negative() -> None:
    html = get_fixture("w03_pass.html")
    ctx = CrawlContext(url="http://localhost/", raw_html=html)
    assert check_W03(ctx) is None


def test_check_W04_positive() -> None:
    ctx = CrawlContext(url="http://localhost/")
    assert check_W04(ctx) is None


def test_check_W04_negative() -> None:
    ctx = CrawlContext(url="http://localhost/")
    assert check_W04(ctx) is None


def test_check_W05_positive() -> None:
    ctx = CrawlContext(url="http://localhost/")
    assert check_W05(ctx) is None


def test_check_W05_negative() -> None:
    ctx = CrawlContext(url="http://localhost/")
    assert check_W05(ctx) is None
