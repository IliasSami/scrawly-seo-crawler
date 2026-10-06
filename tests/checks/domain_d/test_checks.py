from dataclasses import dataclass
from typing import Optional

from sentinelseo.checks.domain_d.checks import (
    check_D01,
    check_D02,
    check_D03,
    check_D04,
    check_D05,
    check_D06,
    check_D07,
    check_D08,
    check_D09,
    check_D10,
    check_D11,
    check_D12,
    check_D13,
    check_D14,
    check_D15,
    check_D16,
    check_D17,
    check_D18,
    check_D19,
    check_D20,
    check_D21,
)
from sentinelseo.checks.registry import CrawlContext
from sentinelseo.crawl.models import URLRow


@dataclass
class MockRenderDiff:
    element: str
    state: str

def make_url_row(
    h1: Optional[list[str]] = None,
    h2: Optional[list[str]] = None,
    meta_desc: Optional[str] = None,
    status: int = 200,
    indexable: bool = True
) -> URLRow:
    return URLRow(
        address="http://test.com",
        status=status,
        redirect_chain=[],
        title=None,
        meta_desc=meta_desc,
        canonical=None,
        meta_robots=None,
        x_robots=None,
        h1=h1 or [],
        h2=h2 or [],
        h3=[],
        h4=[],
        h5=[],
        h6=[],
        word_count=0,
        content_hash="",
        near_dup_cluster="",
        ttfb=0.0,
        size=0,
        inlink_count=0,
        outlink_count=0,
        indexable=indexable,
        indexability_reason=None,
    )

# D01: Missing page title
def test_check_D01_positive() -> None:
    ctx = CrawlContext(url="http://test.com", title="", url_row=make_url_row())
    finding = check_D01(ctx)
    assert finding is not None
    assert finding.check_id == "D01"

def test_check_D01_negative() -> None:
    ctx = CrawlContext(url="http://test.com", title="Valid title", url_row=make_url_row())
    assert check_D01(ctx) is None

def test_check_D01_boundary() -> None:
    # whitespace title is missing
    ctx = CrawlContext(url="http://test.com", title="   ", url_row=make_url_row())
    assert check_D01(ctx) is not None

# D02 is deferred
def test_check_D02_returns_none() -> None:
    assert check_D02(CrawlContext(url="http://test.com")) is None

# D03: Title too long (>~60 chars / ~575px)
def test_check_D03_positive() -> None:
    ctx = CrawlContext(url="http://test.com", title="W" * 34, url_row=make_url_row()) # 34 * 17 = 578px
    finding = check_D03(ctx)
    assert finding is not None
    assert finding.check_id == "D03"

def test_check_D03_negative() -> None:
    ctx = CrawlContext(url="http://test.com", title="W" * 32, url_row=make_url_row()) # 32 * 17 = 544px
    assert check_D03(ctx) is None

def test_check_D03_boundary() -> None:
    ctx = CrawlContext(url="http://test.com", title="W" * 33, url_row=make_url_row()) # 33 * 17 = 561px exactly
    assert check_D03(ctx) is None

# D04: Title too short (<~30 chars)
def test_check_D04_positive() -> None:
    ctx = CrawlContext(url="http://test.com", title="w" * 15, url_row=make_url_row()) # 15 * 13 = 195px
    assert check_D04(ctx) is not None

def test_check_D04_negative() -> None:
    ctx = CrawlContext(url="http://test.com", title="w" * 16, url_row=make_url_row()) # 16 * 13 = 208px
    assert check_D04(ctx) is None

def test_check_D04_boundary() -> None:
    ctx = CrawlContext(url="http://test.com", title="W" * 11 + "a", url_row=make_url_row()) # 11*17 + 9 = 196
    assert check_D04(ctx) is not None

# D05: Multiple title tags
def test_check_D05_positive() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="<title>T1</title><TITLE>T2</TITLE>")
    assert check_D05(ctx) is not None

def test_check_D05_negative() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="<title>T1</title>")
    assert check_D05(ctx) is None

def test_check_D05_boundary() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="")
    assert check_D05(ctx) is None

# D06: Title same as H1
def test_check_D06_positive() -> None:
    ctx = CrawlContext(url="http://test.com")
    assert check_D06(ctx) is None

def test_check_D06_negative() -> None:
    ctx = CrawlContext(url="http://test.com")
    assert check_D06(ctx) is None

# D07: Missing meta description
def test_check_D07_positive() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(meta_desc=None))
    assert check_D07(ctx) is not None

def test_check_D07_negative() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(meta_desc="Valid desc"))
    assert check_D07(ctx) is None

def test_check_D07_boundary() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(meta_desc="", indexable=False))
    assert check_D07(ctx) is None # Not indexable -> no finding

# D08 is deferred
def test_check_D08_returns_none() -> None:
    assert check_D08(CrawlContext(url="http://test.com")) is None

# D09: Meta description too thin for AI (present but < 120 chars). Length is no
# longer penalised, so a long, detailed description is fine.
def test_check_D09_positive_thin() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(meta_desc="Short summary."))  # 14 chars
    assert check_D09(ctx) is not None

def test_check_D09_negative_detailed() -> None:
    # A long, entity-rich description is good — no finding, no upper limit.
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(meta_desc="W" * 200))
    assert check_D09(ctx) is None

def test_check_D09_boundary_120() -> None:
    assert check_D09(CrawlContext(url="http://t", url_row=make_url_row(meta_desc="W" * 120))) is None
    assert check_D09(CrawlContext(url="http://t", url_row=make_url_row(meta_desc="W" * 119))) is not None

def test_check_D09_ignores_missing() -> None:
    # Missing is D07's job, not D09's.
    assert check_D09(CrawlContext(url="http://t", url_row=make_url_row(meta_desc=None))) is None

# D10 is folded into D09 (thin-for-AI), so it no longer emits its own finding.
def test_check_D10_is_folded_into_D09() -> None:
    assert check_D10(CrawlContext(url="http://t", url_row=make_url_row(meta_desc="W" * 29))) is None
    assert check_D10(CrawlContext(url="http://t", url_row=make_url_row(meta_desc="W" * 200))) is None

def test_check_D10_boundary() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(meta_desc=""))
    assert check_D10(ctx) is None

# D11: Multiple meta descriptions
def test_check_D11_positive() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html='<meta name="description" content="1"><meta name="description" content="2">')
    assert check_D11(ctx) is not None

def test_check_D11_negative() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html='<meta name="description" content="1">')
    assert check_D11(ctx) is None

def test_check_D11_boundary() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html='<meta name="Description" content="1">')
    assert check_D11(ctx) is None

# D12: Missing H1
def test_check_D12_positive() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(h1=[]))
    assert check_D12(ctx) is not None

def test_check_D12_negative() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(h1=["Title"]))
    assert check_D12(ctx) is None

def test_check_D12_boundary() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(h1=[], status=404))
    assert check_D12(ctx) is None

# D13: Multiple H1s
def test_check_D13_positive() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(h1=["One", "Two"]))
    assert check_D13(ctx) is not None

def test_check_D13_negative() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(h1=["One"]))
    assert check_D13(ctx) is None

def test_check_D13_boundary() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(h1=[]))
    assert check_D13(ctx) is None

# D14 is deferred
def test_check_D14_returns_none() -> None:
    assert check_D14(CrawlContext(url="http://test.com")) is None

# D15: Broken heading order
def test_check_D15_positive() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="<h2>H2</h2><h4>H4</h4>")
    assert check_D15(ctx) is not None

def test_check_D15_negative() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="<h2>H2</h2><h3>H3</h3>")
    assert check_D15(ctx) is None

def test_check_D15_boundary() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="<h1>H1</h1><h2>H2</h2>")
    assert check_D15(ctx) is None

# D16: Empty heading tags
def test_check_D16_positive() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(h1=[" "], h2=["OK"]))
    assert check_D16(ctx) is not None

def test_check_D16_negative() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(h1=["OK"]))
    assert check_D16(ctx) is None

def test_check_D16_boundary() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(h1=[""], h2=[""]))
    assert check_D16(ctx) is not None

# D17: Title/description modified by JS
def test_check_D17_positive() -> None:
    ctx = CrawlContext(url="http://test.com", render_diffs=[MockRenderDiff("title", "modified")])
    assert check_D17(ctx) is not None

def test_check_D17_negative() -> None:
    ctx = CrawlContext(url="http://test.com", render_diffs=[MockRenderDiff("title", "unchanged")])
    assert check_D17(ctx) is None

def test_check_D17_boundary() -> None:
    ctx = CrawlContext(url="http://test.com", render_diffs=[MockRenderDiff("meta_desc", "created")])
    assert check_D17(ctx) is not None

# D18: Meta keywords tag present
def test_check_D18_positive() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html='<meta name="keywords" content="spam">')
    assert check_D18(ctx) is not None

def test_check_D18_negative() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html='<meta name="description" content="ok">')
    assert check_D18(ctx) is None

def test_check_D18_boundary() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html='<meta name=\'keywords\' content="spam">')
    assert check_D18(ctx) is not None

# D19: Missing OG/Twitter tags
def test_check_D19_positive() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html='<meta property="og:title" content="og">', url_row=make_url_row())
    assert check_D19(ctx) is not None # Missing og:image and og:description

def test_check_D19_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com",
        raw_html='<meta property="og:title" content="og"><meta property="og:image" content="1"><meta property="og:description" content="1">',
        url_row=make_url_row()
    )
    assert check_D19(ctx) is None

def test_check_D19_boundary() -> None:
    # Not indexable -> None
    ctx = CrawlContext(
        url="http://test.com",
        raw_html='<meta property="og:title" content="og">',
        url_row=make_url_row(indexable=False)
    )
    assert check_D19(ctx) is None

# D20: Missing viewport meta
def test_check_D20_positive() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="<title>No viewport</title>", url_row=make_url_row())
    assert check_D20(ctx) is not None

def test_check_D20_negative() -> None:
    ctx = CrawlContext(
        url="http://test.com",
        raw_html='<meta name="viewport" content="width=device-width, initial-scale=1">',
        url_row=make_url_row()
    )
    assert check_D20(ctx) is None

def test_check_D20_boundary() -> None:
    ctx = CrawlContext(url="http://test.com", raw_html="<title>No viewport</title>", url_row=make_url_row(status=404))
    assert check_D20(ctx) is None

# D21: Heading over 70 chars
def test_check_D21_positive() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(h1=["A" * 71]))
    assert check_D21(ctx) is not None

def test_check_D21_negative() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(h1=["A" * 70]))
    assert check_D21(ctx) is None

def test_check_D21_boundary() -> None:
    ctx = CrawlContext(url="http://test.com", url_row=make_url_row(h2=["A" * 71]))
    assert check_D21(ctx) is not None

