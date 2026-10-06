"""Config-profile endpoints: preset seeding + CRUD + default switching."""
from fastapi.testclient import TestClient

from sentinelseo.web.api import app

client = TestClient(app)


def test_presets_seeded() -> None:
    r = client.get("/api/profiles")
    assert r.status_code == 200
    profiles = r.json()
    names = {p["name"] for p in profiles}
    assert {"Quick Check", "Full Technical", "Content Audit", "JS Mobile"} <= names
    # Exactly one default at all times.
    assert sum(1 for p in profiles if p["is_default"]) == 1
    # Presets carry a full, merged config.
    full = next(p for p in profiles if p["name"] == "Full Technical")
    assert full["data"]["js_render"] is True
    assert "concurrency" in full["data"] and "max_pages" in full["data"]


def test_profile_crud_and_default() -> None:
    r = client.post(
        "/api/profiles",
        json={"name": "My Audit", "data": {"max_pages": 42, "js_render": False}},
    )
    assert r.status_code == 200
    pid = r.json()["id"]
    assert r.json()["data"]["max_pages"] == 42
    assert r.json()["data"]["js_render"] is False
    assert "concurrency" in r.json()["data"]  # defaults merged in

    r = client.put(f"/api/profiles/{pid}", json={"data": {"max_pages": 7}})
    assert r.json()["data"]["max_pages"] == 7

    r = client.post(f"/api/profiles/{pid}/default")
    assert r.status_code == 200
    defaults = [p for p in client.get("/api/profiles").json() if p["is_default"]]
    assert len(defaults) == 1 and defaults[0]["id"] == pid

    assert client.delete(f"/api/profiles/{pid}").status_code == 200


def test_preset_delete_blocked() -> None:
    presets = [p for p in client.get("/api/profiles").json() if p["is_preset"]]
    r = client.delete(f"/api/profiles/{presets[0]['id']}")
    assert r.status_code == 400
