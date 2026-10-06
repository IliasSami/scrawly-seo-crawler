from sentinelseo.checks.domain_q.checks import (
    check_Q01,
    check_Q02,
    check_Q03,
    check_Q04,
    check_Q05,
    check_Q06,
    check_Q07,
    check_Q08,
    check_Q09,
)
from sentinelseo.checks.registry import CrawlContext


def test_check_Q01_positive() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="<body><button></button></body>")
    finding = check_Q01(ctx)
    assert finding is not None
    assert finding.check_id == "Q01"


def test_check_Q01_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html="<body><button>Click</button></body>"
    )
    assert check_Q01(ctx) is None


def test_check_Q02_positive() -> None:
    ctx = CrawlContext(
        url="http://test.com",
        raw_html='<body><div aria-invalidattr="true"></div></body>',
    )
    finding = check_Q02(ctx)
    assert finding is not None
    assert finding.check_id == "Q02"


def test_check_Q02_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html='<body><div aria-hidden="true"></div></body>'
    )
    assert check_Q02(ctx) is None


def test_check_Q03_positive() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html='<body><input type="text"></body>'
    )
    finding = check_Q03(ctx)
    assert finding is not None
    assert finding.check_id == "Q03"


def test_check_Q03_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com",
        raw_html='<body><label for="a">A</label><input id="a" type="text"></body>',
    )
    assert check_Q03(ctx) is None


def test_check_Q04_positive() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="<body></body>")
    assert check_Q04(ctx) is None


def test_check_Q04_negative() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="<body></body>")
    assert check_Q04(ctx) is None


def test_check_Q05_positive() -> None:
    ctx = CrawlContext(
        url="http://test.com",
        raw_html='<body><div aria-hidden="true"><button>Click</button></div></body>',
    )
    finding = check_Q05(ctx)
    assert finding is not None
    assert finding.check_id == "Q05"


def test_check_Q05_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html="<body><button>Click</button></body>"
    )
    assert check_Q05(ctx) is None


def test_check_Q06_positive() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html='<body><div role="listitem">Item</div></body>'
    )
    finding = check_Q06(ctx)
    assert finding is not None
    assert finding.check_id == "Q06"


def test_check_Q06_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com",
        raw_html='<body><ul role="list"><li role="listitem">Item</li></ul></body>',
    )
    assert check_Q06(ctx) is None


def test_check_Q07_positive() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="<html><body></body></html>")
    finding = check_Q07(ctx)
    assert finding is not None
    assert finding.check_id == "Q07"


def test_check_Q07_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html='<html lang="en"><body></body></html>'
    )
    assert check_Q07(ctx) is None


def test_check_Q08_positive() -> None:
    ctx = CrawlContext(
        url="http://test.com",
        raw_html='<body><div onclick="alert(1)">Click</div></body>',
    )
    finding = check_Q08(ctx)
    assert finding is not None
    assert finding.check_id == "Q08"


def test_check_Q08_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com",
        raw_html='<body><button onclick="alert(1)">Click</button></body>',
    )
    assert check_Q08(ctx) is None


def test_check_Q09_positive() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html="<body><div>Just content</div></body>"
    )
    finding = check_Q09(ctx)
    assert finding is not None
    assert finding.check_id == "Q09"


def test_check_Q09_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com", raw_html="<body><main>Content</main></body>"
    )
    assert check_Q09(ctx) is None
