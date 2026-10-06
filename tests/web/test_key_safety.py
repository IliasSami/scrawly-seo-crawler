"""Stored secrets are only ever sent to the service they were saved for."""
from typing import Any

import pytest
from fastapi.testclient import TestClient

import sentinelseo.web.api as api
from sentinelseo.db.models import AppSettings, Client
from sentinelseo.db.session import SessionLocal
from sentinelseo.web.api import app

client = TestClient(app)


def _settings() -> dict[str, Any]:
    db = SessionLocal()
    row = db.query(AppSettings).filter(AppSettings.id == 1).first()
    data = dict(row.data) if row and row.data else {}
    db.close()
    return data


@pytest.fixture()
def ai_key_saved() -> None:
    client.put("/api/settings", json={"ai_base_url": "https://api.provider-a.test/v1",
                                      "ai_api_key": "key-for-provider-a"})
    assert _settings().get("ai_api_key") == "key-for-provider-a"


def test_ai_key_kept_when_saving_same_provider(ai_key_saved: None) -> None:
    client.put("/api/settings", json={"ai_base_url": "https://api.provider-a.test/v2",
                                      "ai_api_key": ""})
    assert _settings().get("ai_api_key") == "key-for-provider-a"


def test_ai_key_dropped_when_provider_host_changes(ai_key_saved: None) -> None:
    client.put("/api/settings", json={"ai_base_url": "https://elsewhere.test/v1", "ai_api_key": ""})
    assert not _settings().get("ai_api_key")


def test_new_key_with_new_provider_is_saved(ai_key_saved: None) -> None:
    client.put("/api/settings", json={"ai_base_url": "https://api.provider-b.test",
                                      "ai_api_key": "key-for-provider-b"})
    assert _settings().get("ai_api_key") == "key-for-provider-b"


def test_wp_test_never_sends_stored_key_to_another_site(monkeypatch: pytest.MonkeyPatch) -> None:
    db = SessionLocal()
    c = Client(name="Shop", base_url="https://shop.test/", wp_connection_key="stored-key")
    db.add(c)
    db.commit()
    cid = c.id
    db.close()
    sent: list[tuple[str, str]] = []

    class _Conn:
        def __init__(self, url: str, key: str) -> None:
            sent.append((url, key))

        def status(self) -> dict[str, Any]:
            return {"wp_version": "6.8"}

        def close(self) -> None:
            pass

    import sentinelseo.wp.connector as connector
    monkeypatch.setattr(connector, "ScrawlyConnectorClient", _Conn)

    other = client.post(f"/api/clients/{cid}/wp-test", json={"wp_url": "https://attacker.test"}).json()
    assert other["connected"] is False and not sent

    same = client.post(f"/api/clients/{cid}/wp-test", json={"wp_url": "https://www.shop.test/"}).json()
    assert same["connected"] is True
    assert sent == [("https://www.shop.test/", "stored-key")]


def test_same_host_helper() -> None:
    assert api._same_host("https://www.example.com/a", "example.com")
    assert not api._same_host("https://example.com", "https://example.org")
    assert api._same_host("", "")
