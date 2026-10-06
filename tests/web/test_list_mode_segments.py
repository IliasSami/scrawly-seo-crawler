"""List mode (SF §17) + Segments (SF Pattern N)."""
from types import SimpleNamespace
from typing import Any

from sentinelseo.crawl.fetcher import Crawler
from sentinelseo.web.api import _apply_segments, _parse_url_list

# ---- List mode ----


def test_parse_url_list_handles_messy_input() -> None:
    raw = """
    https://ex.com/a
    ex.com/b
    not a url at all
    https://ex.com/a
    , https://ex.com/c
    """
    assert _parse_url_list(raw) == [
        "https://ex.com/a",     # de-duped, order preserved
        "https://ex.com/b",     # scheme added
        "https://ex.com/c",
    ]


def test_parse_url_list_accepts_a_real_list() -> None:
    assert _parse_url_list(["https://x.com/1", " ", "https://x.com/2"]) == [
        "https://x.com/1", "https://x.com/2",
    ]


def test_list_mode_needs_a_list() -> None:
    # Enabling list mode with nothing in the list would crawl zero URLs — fall back.
    assert Crawler(render=False, list_mode=True, list_urls=[]).list_mode is False
    assert Crawler(render=False, list_mode=True, list_urls=["https://x/1"]).list_mode is True


def test_list_mode_stores_urls() -> None:
    c = Crawler(render=False, list_mode=True, list_urls=["https://x/1", "  ", "https://x/2"])
    assert c.list_urls == ["https://x/1", "https://x/2"]


# ---- Segments ----


def _rows(*addrs: str) -> list[Any]:
    return [SimpleNamespace(address=a, segment=None) for a in addrs]


def test_segments_first_match_wins() -> None:
    rows = _rows("https://ex.com/blog/post-1", "https://ex.com/shop/item", "https://ex.com/about")
    cfg = {"segments": [
        {"name": "Blog", "pattern": r"/blog/"},
        {"name": "Shop", "pattern": r"/shop/"},
        {"name": "Everything", "pattern": r".*"},   # catch-all, last
    ]}
    _apply_segments(rows, cfg)
    assert [r.segment for r in rows] == ["Blog", "Shop", "Everything"]


def test_segment_cascade_order_is_priority() -> None:
    rows = _rows("https://ex.com/blog/post-1")
    # Catch-all placed FIRST swallows everything — order defines precedence.
    _apply_segments(rows, {"segments": [
        {"name": "Everything", "pattern": r".*"},
        {"name": "Blog", "pattern": r"/blog/"},
    ]})
    assert rows[0].segment == "Everything"


def test_unmatched_url_has_no_segment() -> None:
    rows = _rows("https://ex.com/about")
    _apply_segments(rows, {"segments": [{"name": "Blog", "pattern": r"/blog/"}]})
    assert rows[0].segment is None


def test_no_rules_is_a_noop() -> None:
    rows = _rows("https://ex.com/x")
    _apply_segments(rows, {})
    assert rows[0].segment is None


def test_invalid_regex_falls_back_to_literal() -> None:
    rows = _rows("https://ex.com/a(b", "https://ex.com/ab")
    _apply_segments(rows, {"segments": [{"name": "Lit", "pattern": "a(b"}]})
    assert rows[0].segment == "Lit"   # matched literally, didn't raise
    assert rows[1].segment is None


def test_incomplete_rules_skipped() -> None:
    rows = _rows("https://ex.com/blog/x")
    _apply_segments(rows, {"segments": [
        {"name": "", "pattern": r"/blog/"},      # no name
        {"name": "NoPattern", "pattern": ""},    # no pattern
        {"name": "Blog", "pattern": r"/blog/"},
    ]})
    assert rows[0].segment == "Blog"
