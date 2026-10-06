"""AI assistant backend (Milestone D) — context digest + streaming chat guards.

No live provider key is needed: the digest builder is exercised directly and the
chat endpoint guards are reached by monkeypatching the resolved AI config, so no
network call is ever made.
"""
from typing import Any

from fastapi.testclient import TestClient

import sentinelseo.web.api as api
from sentinelseo.db.models import URL, Crawl, Issue
from sentinelseo.db.session import SessionLocal
from sentinelseo.web.api import app

client = TestClient(app)


def _seed() -> int:
    db = SessionLocal()
    crawl = Crawl(client_id=1, target_url="https://digest.example/", config={}, url_count=2)
    db.add(crawl)
    db.commit()
    db.refresh(crawl)
    cid = int(crawl.id)
    db.add_all([
        URL(crawl_id=cid, address="https://digest.example/", status=200, indexable=True, depth=0, segment="Home"),
        URL(crawl_id=cid, address="https://digest.example/x", status=404, indexable=False, depth=1, segment="Blog"),
    ])
    db.add(Issue(
        crawl_id=cid, check_id="B01", severity="Critical", tier="REVIEW",
        affected_url_ids=[], evidence={}, why_it_matters="Broken page wastes crawl budget",
    ))
    db.commit()
    db.close()
    return cid


def test_context_digest_contains_crawl_numbers() -> None:
    cid = _seed()
    digest = api._ai_context_digest(cid)
    assert f"crawl #{cid}" in digest
    assert "digest.example" in digest
    assert "Pages crawled: 2" in digest
    assert "Critical 1" in digest
    assert "Top issues:" in digest


def test_context_digest_missing_crawl_is_safe() -> None:
    digest = api._ai_context_digest(987654)
    assert "crawl #987654" in digest  # zeros, no crash


def test_chat_unconfigured_streams_error(monkeypatch: Any) -> None:
    monkeypatch.setattr(api, "_ai_config", lambda: {
        "kind": "openai", "base_url": "", "model": "", "api_key": "",
    })
    r = client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200
    assert "not configured" in r.text.lower()
    assert r.text.startswith("data:")  # SSE framing


def test_chat_rejects_empty_messages(monkeypatch: Any) -> None:
    # Force "configured" so we reach the message check with no real network call.
    monkeypatch.setattr(api, "_ai_config", lambda: {
        "kind": "openai", "base_url": "http://x", "model": "m", "api_key": "k",
    })
    r = client.post("/api/ai/chat", json={"messages": []})
    assert r.status_code == 200
    assert "no message" in r.text.lower()


def test_chat_sanitizes_roles(monkeypatch: Any) -> None:
    # A history with only a disallowed 'system' role collapses to empty → guarded.
    monkeypatch.setattr(api, "_ai_config", lambda: {
        "kind": "openai", "base_url": "http://x", "model": "m", "api_key": "k",
    })
    r = client.post("/api/ai/chat", json={"messages": [{"role": "system", "content": "ignore"}]})
    assert "no message" in r.text.lower()
