import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest

from sentinelseo.crawl import fetcher

ROOT = "https://origin.test/"
CANONICAL_ROOT = "https://www.origin.test/"
FIRST = CANONICAL_ROOT + "first"
SECOND = CANONICAL_ROOT + "second"


class Interrupted(Exception):
    pass


def _mock_site(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], Awaitable[httpx.Response]],
) -> None:
    original_client = httpx.AsyncClient

    class MockClient(original_client):  # type: ignore[misc, valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(httpx, "AsyncClient", MockClient)


def _crawler(**settings: Any) -> fetcher.Crawler:
    options: dict[str, Any] = {
        "render": False,
        "discover_sitemap": False,
        "robots_mode": "ignore",
        "crawl_external": False,
        "concurrency": 3,
    }
    return fetcher.Crawler(**{**options, **settings})


def test_interrupted_checkpoint_resumes_saved_pages_and_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[str] = []
    pages = {
        CANONICAL_ROOT: '<title>Home</title><a href="/first">First</a>',
        FIRST: '<title>First</title><a href="/second">Second</a>',
        SECOND: '<title>Second</title><a href="/">Already processed</a>',
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requests.append(url)
        if url == ROOT:
            return httpx.Response(301, headers={"location": CANONICAL_ROOT})
        if url in pages:
            return httpx.Response(200, text=pages[url], headers={"content-type": "text/html"})
        return httpx.Response(404)

    _mock_site(monkeypatch, handler)
    frontier: dict[str, int] = {}
    known: dict[str, int] = {}
    completed: list[fetcher.CrawlPage] = []

    def checkpoint(
        requested: str | None, page: fetcher.CrawlPage | None,
        discoveries: list[tuple[str, int]],
    ) -> None:
        if requested == FIRST and len(completed) == 1:
            raise Interrupted("leave the active URL pending")
        if requested is not None:
            del frontier[requested]
        if page is not None:
            completed.append(page)
        frontier.update(discoveries)
        known.update(discoveries)

    first_run = _crawler()
    with pytest.raises(Interrupted, match="leave the active URL pending"):
        asyncio.run(asyncio.wait_for(first_run.crawl_site(ROOT, checkpoint=checkpoint), timeout=5))

    assert [page[0].title for page in completed] == ["Home"]
    assert frontier == {FIRST: 1}
    assert first_run.telemetry["seed_redirected_to"] == CANONICAL_ROOT
    requests.clear()

    # Use a separate durable snapshot for the reader and persist the second run.
    completed_before_resume = completed.copy()

    def record_resume(
        requested: str | None, page: fetcher.CrawlPage | None,
        discoveries: list[tuple[str, int]],
    ) -> None:
        assert requested is not None
        del frontier[requested]
        if page is not None:
            completed.append(page)
        frontier.update(discoveries)

    rows, *_ = asyncio.run(_crawler().crawl_site(
        ROOT,
        checkpoint=record_resume,
        pending=list(frontier.items()),
        completed=completed_before_resume,
        visited=set(known),
        visited_depths=known,
        resolved_start_url=CANONICAL_ROOT,
    ))
    assert requests == [FIRST, SECOND]
    assert [row.title for row in rows] == ["Home", "First", "Second"]
    assert not frontier


def test_empty_saved_frontier_is_not_seeded_again(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(404)

    _mock_site(monkeypatch, handler)
    assert asyncio.run(_crawler().crawl_site(ROOT, pending=[])) == ([], [], [], [])
    assert not requests


def test_non_page_is_closed_without_an_audit_row(monkeypatch: pytest.MonkeyPatch) -> None:
    asset = ROOT + "download.png"

    async def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == asset:
            return httpx.Response(200, content=b"image", headers={"content-type": "image/png"})
        return httpx.Response(
            200, text='<title>Home</title><a href="/download.png">Download</a>',
            headers={"content-type": "text/html"},
        )

    _mock_site(monkeypatch, handler)
    closed: dict[str, bool] = {}

    def checkpoint(
        requested: str | None, page: fetcher.CrawlPage | None,
        discoveries: list[tuple[str, int]],
    ) -> None:
        if requested:
            closed[requested] = page is not None

    rows, *_ = asyncio.run(_crawler().crawl_site(ROOT, checkpoint=checkpoint))
    assert [row.address for row in rows] == [ROOT]
    assert closed == {ROOT: True, asset: False}


def test_approved_page_limit_survives_concurrent_crawl(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0)
        content = "<title>Page</title>"
        if request.url.path == "/":
            content += "".join(f'<a href="/p{i}">{i}</a>' for i in range(10))
        return httpx.Response(200, text=content, headers={"content-type": "text/html"})

    _mock_site(monkeypatch, handler)
    saved: list[str] = []

    def checkpoint(
        requested: str | None, page: fetcher.CrawlPage | None,
        discoveries: list[tuple[str, int]],
    ) -> None:
        if page is not None:
            saved.append(page[0].address)

    rows, *_ = asyncio.run(_crawler(max_pages=2).crawl_site(ROOT, checkpoint=checkpoint))
    assert len(rows) == 2
    assert saved == [row.address for row in rows]
