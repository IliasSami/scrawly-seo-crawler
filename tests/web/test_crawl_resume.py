"""Durable crawl progress and same-id resume API regression tests.

These tests deliberately use a private SQLite database and a deterministic
``do_audit`` replacement.  They exercise the HTTP/storage contract without
making any network requests.
"""
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import sentinelseo.web.api as api
import sentinelseo.web.crawl_checkpoint as checkpoint_mod
from sentinelseo.db.migrate import run_migrations
from sentinelseo.db.models import URL, Client, Crawl


@pytest.fixture  # type: ignore[untyped-decorator]
def resume_api(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    """Bind every API session in this test to an isolated on-disk database."""
    engine = create_engine(f"sqlite:///{tmp_path / 'resume.db'}")
    run_migrations(engine)
    maker = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(api, "SessionLocal", maker)
    monkeypatch.setattr(checkpoint_mod, "SessionLocal", maker)
    api.active_tasks.clear()
    with TestClient(api.app) as http:
        yield http, maker
    api.active_tasks.clear()
    engine.dispose()


def _interrupted_crawl(maker: sessionmaker[Session]) -> int:
    db = maker()
    client = Client(name="Resume fixture", base_url="https://resume.test/")
    db.add(client)
    db.flush()
    crawl = Crawl(
        client_id=client.id,
        target_url=client.base_url,
        config={"max_pages": 10, "max_depth": 2},
        run_state="running",
        discovered_count=2,
        processed_count=1,
        completed_count=1,
        url_count=1,
    )
    db.add(crawl)
    db.flush()
    db.add(URL(
        crawl_id=crawl.id,
        address="https://resume.test/",
        status=200,
        title="Already saved",
        depth=0,
        indexable=True,
    ))
    db.commit()
    crawl_id = int(crawl.id)
    db.close()
    return crawl_id


def test_interrupted_status_and_partial_urls_survive_process_restart(
    resume_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    http, maker = resume_api
    crawl_id = _interrupted_crawl(maker)

    # ``active_tasks`` is process memory.  Clearing it simulates opening the app
    # after the worker process died; status must be reconstructed from SQLite.
    api.active_tasks.clear()

    status = http.get(f"/api/audit/status/{crawl_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["phase"] == "interrupted"
    assert body["resumable"] is True
    assert body["discovered"] == 2
    assert body["processed"] == 1
    assert body["crawled"] == 1

    rows = http.get(f"/api/urls/{crawl_id}")
    assert rows.status_code == 200
    assert [(row["address"], row["title"]) for row in rows.json()] == [
        ("https://resume.test/", "Already saved")
    ]

    listed = http.get("/api/crawls").json()
    item = next(row for row in listed if row["id"] == crawl_id)
    assert item["phase"] == "interrupted"
    assert item["discovered"] == 2
    assert item["processed"] == 1
    assert item["crawled"] == 1


def test_resume_keeps_partial_rows_completes_same_id_and_cannot_run_twice(
    resume_api: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http, maker = resume_api
    crawl_id = _interrupted_crawl(maker)
    launched: list[int] = []

    async def deterministic_resume(
        resumed_id: int, target: str, config: dict[str, Any], owner: str = ""
    ) -> None:
        launched.append(resumed_id)
        assert resumed_id == crawl_id
        assert target == "https://resume.test/"
        assert config["max_pages"] == 10
        db = maker()
        # This producer represents the one pending page.  The already committed
        # homepage must remain in place rather than being deleted/reinserted.
        db.add(URL(
            crawl_id=resumed_id,
            address="https://resume.test/pending",
            status=200,
            title="Finished after resume",
            depth=1,
            indexable=True,
        ))
        crawl = db.query(Crawl).filter(Crawl.id == resumed_id).one()
        crawl.run_state = "complete"
        crawl.discovered_count = 2
        crawl.processed_count = 2
        crawl.completed_count = 2
        crawl.url_count = 2
        db.commit()
        db.close()
        api.active_tasks[api._task_key(resumed_id)].update(
            status="Complete", phase="complete", progress=100,
            discovered=2, processed=2, crawled=2, resumable=False,
        )

    monkeypatch.setattr(api, "do_audit", deterministic_resume)
    api.active_tasks.clear()

    response = http.post(f"/api/audit/resume/{crawl_id}")
    assert response.status_code == 200
    assert response.json()["crawl_id"] == crawl_id
    assert launched == [crawl_id]

    rows = http.get(f"/api/urls/{crawl_id}").json()
    assert {row["address"]: row["title"] for row in rows} == {
        "https://resume.test/": "Already saved",
        "https://resume.test/pending": "Finished after resume",
    }
    status = http.get(f"/api/audit/status/{crawl_id}").json()
    assert status["phase"] == "complete"
    assert status["resumable"] is False
    assert status["discovered"] == status["processed"] == status["crawled"] == 2

    duplicate = http.post(f"/api/audit/resume/{crawl_id}")
    assert duplicate.status_code == 409
    assert launched == [crawl_id]


def test_resume_rejects_a_crawl_that_is_already_active(
    resume_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    http, maker = resume_api
    crawl_id = _interrupted_crawl(maker)
    api.active_tasks[api._task_key(crawl_id)] = {
        "phase": "crawl", "status": "Crawling"
    }

    response = http.post(f"/api/audit/resume/{crawl_id}")

    assert response.status_code == 409
