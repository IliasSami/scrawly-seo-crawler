from pathlib import Path

from sentinelseo.checks.domain_v.checks import (
    check_V01,
    check_V02,
    check_V03,
    check_V04,
    check_V05,
    check_V06,
    check_V07,
    check_V08,
    check_V09,
    check_V10,
    check_V11,
    check_V12,
)
from sentinelseo.checks.registry import CrawlContext


def get_fixture(name: str) -> str:
    return Path(f"tests/fixtures/{name}").read_text()


def test_check_V01_positive() -> None:
    ctx = CrawlContext(url="http://localhost/category/uncategorized/")
    assert check_V01(ctx) is not None


def test_check_V01_negative() -> None:
    ctx = CrawlContext(url="http://localhost/category/tech/")
    assert check_V01(ctx) is None


def test_check_V02_positive() -> None:
    ctx = CrawlContext(url="http://localhost/tag/seo/")
    assert check_V02(ctx) is not None


def test_check_V02_negative() -> None:
    ctx = CrawlContext(url="http://localhost/post/")
    assert check_V02(ctx) is None


def test_check_V03_positive() -> None:
    ctx = CrawlContext(url="http://localhost/?attachment_id=123")
    assert check_V03(ctx) is not None


def test_check_V03_negative() -> None:
    ctx = CrawlContext(url="http://localhost/")
    assert check_V03(ctx) is None


def test_check_V04_positive() -> None:
    ctx = CrawlContext(url="http://localhost/comment-page-1/")
    assert check_V04(ctx) is not None


def test_check_V04_negative() -> None:
    ctx = CrawlContext(url="http://localhost/")
    assert check_V04(ctx) is None


def test_check_V05_positive() -> None:
    ctx = CrawlContext(url="http://localhost/?s=query")
    assert check_V05(ctx) is not None


def test_check_V05_negative() -> None:
    ctx = CrawlContext(url="http://localhost/")
    assert check_V05(ctx) is None


def test_check_V06_positive() -> None:
    html = get_fixture("v06_fail.html")
    ctx = CrawlContext(url="http://localhost/", raw_html=html)
    assert check_V06(ctx) is not None


def test_check_V06_negative() -> None:
    html = get_fixture("clean_page.html")
    ctx = CrawlContext(url="http://localhost/", raw_html=html)
    assert check_V06(ctx) is None


def test_check_V07_positive() -> None:
    html = get_fixture("v07_fail.html")
    ctx = CrawlContext(url="http://localhost/", raw_html=html)
    assert check_V07(ctx) is not None


def test_check_V07_negative() -> None:
    html = get_fixture("clean_page.html")
    ctx = CrawlContext(url="http://localhost/", raw_html=html)
    assert check_V07(ctx) is None


def test_check_V08_positive() -> None:
    ctx = CrawlContext(url="http://localhost/")
    assert check_V08(ctx) is None


def test_check_V08_negative() -> None:
    ctx = CrawlContext(url="http://localhost/")
    assert check_V08(ctx) is None


def test_check_V09_positive() -> None:
    ctx = CrawlContext(url="http://localhost/?replytocom=123")
    assert check_V09(ctx) is not None


def test_check_V09_negative() -> None:
    ctx = CrawlContext(url="http://localhost/")
    assert check_V09(ctx) is None


def test_check_V10_positive() -> None:
    html = get_fixture("clean_page.html")
    ctx = CrawlContext(url="http://staging.domain.com/", raw_html=html)
    assert check_V10(ctx) is not None


def test_check_V10_negative() -> None:
    html = get_fixture("clean_page.html")
    ctx = CrawlContext(url="http://www.domain.com/", raw_html=html)
    assert check_V10(ctx) is None


def test_check_V11_positive() -> None:
    html = get_fixture("v11_fail.html")
    ctx = CrawlContext(url="http://localhost/", raw_html=html)
    assert check_V11(ctx) is not None


def test_check_V11_negative() -> None:
    html = get_fixture("clean_page.html")
    ctx = CrawlContext(url="http://localhost/", raw_html=html)
    assert check_V11(ctx) is None


def test_check_V12_positive() -> None:
    ctx = CrawlContext(url="http://localhost/wp-json/wp/v2/users")
    assert check_V12(ctx) is not None


def test_check_V12_negative() -> None:
    ctx = CrawlContext(url="http://localhost/wp-json/wp/v2/posts")
    assert check_V12(ctx) is None
