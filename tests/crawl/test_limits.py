"""Crawl limits + rate cap (M3 slice A)."""
import asyncio
import time

from sentinelseo.crawl.fetcher import Crawler


def test_url_length_limit() -> None:
    c = Crawler(max_url_length=40)
    assert c._url_allowed("https://x.com/short")
    assert not c._url_allowed("https://x.com/" + "a" * 60)


def test_query_param_limit() -> None:
    c = Crawler(max_query_params=2)
    assert c._url_allowed("https://x.com/p?a=1&b=2")
    assert not c._url_allowed("https://x.com/p?a=1&b=2&c=3")


def test_folder_depth_limit() -> None:
    c = Crawler(max_folder_depth=2)
    assert c._url_allowed("https://x.com/a/b")
    assert not c._url_allowed("https://x.com/a/b/c")


def test_unlimited_by_default() -> None:
    c = Crawler()  # all limits 0 = unlimited
    assert c._url_allowed("https://x.com/" + "a" * 5000 + "?x=1&y=2&z=3&w=4")


def test_scope_include_exclude() -> None:
    c = Crawler(include_patterns="/blog/", exclude_patterns="/wp-admin/")
    assert c._in_scope("https://x.com/blog/post")
    assert not c._in_scope("https://x.com/products/1")   # not in include
    assert not c._in_scope("https://x.com/blog/wp-admin/")  # excluded


def test_rate_cap_spaces_requests() -> None:
    # 10 req/s → 3 throttled calls should span ~0.2s (2 intervals).
    c = Crawler(max_requests_per_sec=10)

    async def run() -> float:
        t0 = time.monotonic()
        for _ in range(3):
            await c._throttle()
        return time.monotonic() - t0

    elapsed = asyncio.run(run())
    assert elapsed >= 0.18, f"rate cap not enforced (elapsed={elapsed:.3f}s)"


def test_no_throttle_when_unlimited() -> None:
    c = Crawler(max_requests_per_sec=0)

    async def run() -> float:
        t0 = time.monotonic()
        for _ in range(50):
            await c._throttle()
        return time.monotonic() - t0

    assert asyncio.run(run()) < 0.05  # effectively free
