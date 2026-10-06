"""R13 — hard-to-read (low readability) content check."""
from types import SimpleNamespace

from sentinelseo.checks.domain_r.checks import check_R13
from sentinelseo.checks.registry import CrawlContext


def _ctx(words: int, score: float) -> CrawlContext:
    return CrawlContext(
        url="http://t.com",
        raw_html="",
        url_row=SimpleNamespace(word_count=words, readability=score),
    )


def test_R13_positive() -> None:
    f = check_R13(_ctx(500, 12.0))  # substantial + very hard to read
    assert f is not None and f.check_id == "R13"


def test_R13_negative_readable() -> None:
    assert check_R13(_ctx(500, 70.0)) is None  # plain English


def test_R13_boundary_too_short() -> None:
    assert check_R13(_ctx(120, 5.0)) is None  # too little prose to judge


def test_R13_no_url_row() -> None:
    assert check_R13(CrawlContext(url="http://t.com", raw_html="")) is None
