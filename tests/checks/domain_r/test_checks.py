from sentinelseo.checks.domain_r.checks import (
    check_R01,
    check_R02,
    check_R03,
    check_R04,
    check_R05,
    check_R06,
    check_R07,
    check_R08,
    check_R09,
    check_R10,
    check_R11,
    check_R12,
)
from sentinelseo.checks.registry import CrawlContext


def test_check_R01_positive() -> None:
    html = '<meta name="GPTBot" content="noindex">'
    ctx = CrawlContext(url="http://test.com", raw_html=html)
    finding = check_R01(ctx)
    assert finding is not None
    assert finding.check_id == "R01"


def test_check_R01_negative() -> None:
    html = '<meta name="GPTBot" content="index">'
    ctx = CrawlContext(url="http://test.com", raw_html=html)
    assert check_R01(ctx) is None


def test_check_R02_positive() -> None:
    html = '<meta name="OAI-SearchBot" content="noindex">'
    ctx = CrawlContext(url="http://test.com", raw_html=html)
    finding = check_R02(ctx)
    assert finding is not None
    assert finding.check_id == "R02"


def test_check_R02_negative() -> None:
    html = '<meta name="OAI-SearchBot" content="index">'
    ctx = CrawlContext(url="http://test.com", raw_html=html)
    assert check_R02(ctx) is None


def test_check_R03_positive() -> None:
    html = '<meta name="ChatGPT-User" content="noindex">'
    ctx = CrawlContext(url="http://test.com", raw_html=html)
    finding = check_R03(ctx)
    assert finding is not None
    assert finding.check_id == "R03"


def test_check_R03_negative() -> None:
    html = '<meta name="ChatGPT-User" content="index">'
    ctx = CrawlContext(url="http://test.com", raw_html=html)
    assert check_R03(ctx) is None


def test_check_R04_positive() -> None:
    # Always None
    ctx = CrawlContext(url="http://test.com", raw_html="")
    assert check_R04(ctx) is None


def test_check_R04_negative() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="")
    assert check_R04(ctx) is None


def test_check_R05_positive() -> None:
    # rendered text > 2x raw text and > 100 chars
    raw = "<body><div id='app'></div></body>"
    rendered = "<body><div id='app'>" + "content " * 20 + "</div></body>"
    ctx = CrawlContext(url="http://test.com", raw_html=raw, rendered_html=rendered)
    finding = check_R05(ctx)
    assert finding is not None
    assert finding.check_id == "R05"


def test_check_R05_negative() -> None:
    raw = "<body><div id='app'>" + "content " * 20 + "</div></body>"
    rendered = raw
    ctx = CrawlContext(url="http://test.com", raw_html=raw, rendered_html=rendered)
    assert check_R05(ctx) is None


def test_check_R06_positive() -> None:
    html = '<body><input type="password"></body>'
    ctx = CrawlContext(url="http://test.com", raw_html=html)
    finding = check_R06(ctx)
    assert finding is not None
    assert finding.check_id == "R06"


def test_check_R06_negative() -> None:
    html = '<body><input type="text"></body>'
    ctx = CrawlContext(url="http://test.com", raw_html=html)
    assert check_R06(ctx) is None


def test_check_R07_positive() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="")
    assert check_R07(ctx) is None


def test_check_R07_negative() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="")
    assert check_R07(ctx) is None


def test_check_R08_positive() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="")
    assert check_R08(ctx) is None


def test_check_R08_negative() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="")
    assert check_R08(ctx) is None


def test_check_R09_positive() -> None:
    html = "<body></body>"
    ctx = CrawlContext(url="http://test.com", raw_html=html)
    finding = check_R09(ctx)
    assert finding is not None
    assert finding.check_id == "R09"


def test_check_R09_negative() -> None:
    html = '<head><meta name="author" content="a"><time datetime="2020"></time></head>'
    ctx = CrawlContext(url="http://test.com", raw_html=html)
    assert check_R09(ctx) is None


def test_check_R10_positive() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html="", structured_data=[{"type": "Article"}]
    )
    finding = check_R10(ctx)
    assert finding is not None
    assert finding.check_id == "R10"


def test_check_R10_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html="", structured_data=[{"type": "Organization"}]
    )
    assert check_R10(ctx) is None


def test_check_R11_positive() -> None:
    html = "<head></head>"
    ctx = CrawlContext(url="http://test.com", raw_html=html)
    finding = check_R11(ctx)
    assert finding is not None
    assert finding.check_id == "R11"


def test_check_R11_negative() -> None:
    html = '<head><meta name="Google-Extended" content="noindex"></head>'
    ctx = CrawlContext(url="http://test.com", raw_html=html)
    assert check_R11(ctx) is None


def test_check_R12_positive() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html="", structured_data=[{"type": "Article"}]
    )
    finding = check_R12(ctx)
    assert finding is not None
    assert finding.check_id == "R12"


def test_check_R12_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html="", structured_data=[{"type": "FAQPage"}]
    )
    assert check_R12(ctx) is None
