from __future__ import annotations

from types import SimpleNamespace

from sentinelseo.checks.domain_o.checks import (
    check_O01,
    check_O02,
    check_O03,
    check_O04,
    check_O05,
    check_O06,
    check_O07,
)
from sentinelseo.checks.registry import CrawlContext


def test_check_O01_positive() -> None:
    # Missing viewport
    ctx = CrawlContext(
        url="https://example.com",
        raw_html="<html><head></head><body>hello</body></html>",
    )
    result = check_O01(ctx)
    assert result is not None
    assert result.check_id == "O01"

    # Incorrect viewport
    ctx2 = CrawlContext(
        url="https://example.com",
        raw_html=(
            '<html><head><meta name="viewport" '
            'content="initial-scale=1.5"></head><body>hello</body></html>'
        ),
    )
    result2 = check_O01(ctx2)
    assert result2 is not None
    assert result2.check_id == "O01"


def test_check_O01_negative() -> None:
    ctx = CrawlContext(
        url="https://example.com",
        raw_html=(
            '<html><head><meta name="viewport" '
            'content="width=device-width, initial-scale=1"></head>'
            "<body>hello</body></html>"
        ),
    )
    result = check_O01(ctx)
    assert result is None


def test_check_O02_positive() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_O02(ctx) is None


def test_check_O02_negative() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_O02(ctx) is None


def test_check_O03_positive() -> None:
    row = SimpleNamespace(mobile_context=SimpleNamespace(contentWiderThanViewport=True))
    f = check_O03(CrawlContext(url="https://example.com", url_row=row))
    assert f is not None and f.check_id == "O03"


def test_check_O03_negative() -> None:
    row = SimpleNamespace(mobile_context=SimpleNamespace(contentWiderThanViewport=False))
    assert check_O03(CrawlContext(url="https://example.com", url_row=row)) is None
    assert check_O03(CrawlContext(url="https://example.com")) is None


def test_check_O04_positive() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_O04(ctx) is None


def test_check_O04_negative() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_O04(ctx) is None


def test_check_O05_positive() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_O05(ctx) is None


def test_check_O05_negative() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_O05(ctx) is None


def test_check_O06_positive() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_O06(ctx) is None


def test_check_O06_negative() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_O06(ctx) is None


def test_check_O07_positive() -> None:
    row = SimpleNamespace(mobile_context=SimpleNamespace(blocked_resources={"http://x/a.js"}))
    f = check_O07(CrawlContext(url="https://example.com", url_row=row))
    assert f is not None and f.check_id == "O07"


def test_check_O07_negative() -> None:
    ctx = CrawlContext(url="https://example.com")
    assert check_O07(ctx) is None
