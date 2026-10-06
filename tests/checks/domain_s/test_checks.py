from sentinelseo.checks.domain_s.checks import (
    check_S01,
    check_S02,
    check_S03,
    check_S04,
    check_S05,
    check_S06,
    check_S07,
    check_S08,
    check_S09,
    check_S10,
    check_S11,
    check_S12,
    check_S13,
)
from sentinelseo.checks.registry import CrawlContext


def test_check_S01_positive() -> None:
    assert check_S01(CrawlContext(url="http://test.com")) is None


def test_check_S01_negative() -> None:
    assert check_S01(CrawlContext(url="http://test.com")) is None


def test_check_S02_positive() -> None:
    html = "<body></body>"
    ctx = CrawlContext(url="http://test.com/llms.txt", raw_html=html)
    finding = check_S02(ctx)
    assert finding is not None
    assert finding.check_id == "S02"


def test_check_S02_negative() -> None:
    html = '<body><h1>LLMs</h1><a href="link">link</a>' + "a" * 50 + "</body>"
    ctx = CrawlContext(url="http://test.com/llms.txt", raw_html=html)
    assert check_S02(ctx) is None


def test_check_S03_positive() -> None:
    html = "<body>" + '<a href="link">link</a>' * 801 + "</body>"
    ctx = CrawlContext(url="http://test.com/llms.txt", raw_html=html)
    finding = check_S03(ctx)
    assert finding is not None
    assert finding.check_id == "S03"


def test_check_S03_negative() -> None:
    html = "<body>" + '<a href="link">link</a>' * 10 + "</body>"
    ctx = CrawlContext(url="http://test.com/llms.txt", raw_html=html)
    assert check_S03(ctx) is None


def test_check_S04_positive() -> None:
    assert check_S04(CrawlContext(url="http://test.com")) is None


def test_check_S04_negative() -> None:
    assert check_S04(CrawlContext(url="http://test.com")) is None


def test_check_S05_positive() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="<body><button></button></body>")
    finding = check_S05(ctx)
    assert finding is not None
    assert finding.check_id == "S05"


def test_check_S05_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html="<body><button>Click</button></body>"
    )
    assert check_S05(ctx) is None


def test_check_S06_positive() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html='<body><div role="listitem">Item</div></body>'
    )
    finding = check_S06(ctx)
    assert finding is not None
    assert finding.check_id == "S06"


def test_check_S06_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com",
        raw_html='<body><ul role="list"><li role="listitem">Item</li></ul></body>',
    )
    assert check_S06(ctx) is None


def test_check_S07_positive() -> None:
    ctx = CrawlContext(
        url="http://test.com",
        raw_html='<body><div aria-hidden="true"><button>Click</button></div></body>',
    )
    finding = check_S07(ctx)
    assert finding is not None
    assert finding.check_id == "S07"


def test_check_S07_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html="<body><button>Click</button></body>"
    )
    assert check_S07(ctx) is None


def test_check_S08_positive() -> None:
    from types import SimpleNamespace
    row = SimpleNamespace(agentic_context=SimpleNamespace(post_load_cls=0.3))
    f = check_S08(CrawlContext(url="http://test.com", url_row=row))
    assert f is not None and f.check_id == "S08"


def test_check_S08_negative() -> None:
    from types import SimpleNamespace
    row = SimpleNamespace(agentic_context=SimpleNamespace(post_load_cls=0.02))
    assert check_S08(CrawlContext(url="http://test.com", url_row=row)) is None
    assert check_S08(CrawlContext(url="http://test.com")) is None


def test_check_S09_positive() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html='<body><form action="/submit"></form></body>'
    )
    finding = check_S09(ctx)
    assert finding is not None
    assert finding.check_id == "S09"


def test_check_S09_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html='<body><form data-mcp="{}"></form></body>'
    )
    assert check_S09(ctx) is None


def test_check_S10_positive() -> None:
    ctx = CrawlContext(
        url="http://test.com",
        raw_html='<body><div data-mcp="invalid json"></div></body>',
    )
    finding = check_S10(ctx)
    assert finding is not None
    assert finding.check_id == "S10"


def test_check_S10_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com",
        raw_html="<body><div data-mcp='{\"valid\": true}'></div></body>",
    )
    assert check_S10(ctx) is None


def test_check_S11_positive() -> None:
    assert check_S11(CrawlContext(url="http://test.com")) is None


def test_check_S11_negative() -> None:
    assert check_S11(CrawlContext(url="http://test.com")) is None


def test_check_S12_positive() -> None:
    assert check_S12(CrawlContext(url="http://test.com")) is None


def test_check_S12_negative() -> None:
    assert check_S12(CrawlContext(url="http://test.com")) is None


def test_check_S13_positive() -> None:
    assert check_S13(CrawlContext(url="http://test.com")) is None


def test_check_S13_negative() -> None:
    assert check_S13(CrawlContext(url="http://test.com")) is None
