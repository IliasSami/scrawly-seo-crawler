"""Universal connection framework: methods, auto-detect, relaxed audit gate."""
from typing import Any

import pytest
from fastapi.testclient import TestClient

import sentinelseo.detect as detect_mod
import sentinelseo.web.api as api
from sentinelseo.detect.fingerprint import DetectionResult
from sentinelseo.web.api import app

client = TestClient(app)


def _new_client(**over: Any) -> dict[str, Any]:
    body = {"name": "Conn Test", "base_url": "https://example.com", **over}
    r = client.post("/api/clients", json=body)
    assert r.status_code == 200
    out: dict[str, Any] = r.json()
    return out


def test_new_client_defaults_to_url_only() -> None:
    c = _new_client()
    assert c["connection_method"] == "url_only"


def test_update_persists_method_and_detected_stack() -> None:
    c = _new_client()
    r = client.put(
        f"/api/clients/{c['id']}",
        json={"connection_method": "ssh", "detected_stack": {"stack": "laravel"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["connection_method"] == "ssh"
    assert body["detected_stack"]["stack"] == "laravel"


def test_audit_gate_allows_url_only_client(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_audit(*a: Any, **k: Any) -> None:
        return None

    monkeypatch.setattr(api, "do_audit", fake_audit)
    c = _new_client()  # url_only, no WordPress connection
    r = client.post("/api/audit/start", json={"client_id": c["id"], "max_pages": 5})
    assert r.status_code == 200  # read-only audit no longer requires WordPress
    assert "crawl_id" in r.json()


def test_detect_persists_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_detect(url: str, **kw: Any) -> DetectionResult:
        return DetectionResult(stack="shopify", confidence=0.8)

    monkeypatch.setattr(detect_mod, "detect_stack", fake_detect)
    c = _new_client()
    r = client.post(f"/api/clients/{c['id']}/detect")
    assert r.status_code == 200
    assert r.json()["detection"]["stack"] == "shopify"
    assert r.json()["preset"]["label"] == "Shopify"
    # Persisted on the client.
    got = client.get(f"/api/clients/{c['id']}").json()
    assert got["detected_stack"]["stack"] == "shopify"


def test_verify_token_is_stable_and_scoped() -> None:
    c = _new_client()
    t1 = client.get(f"/api/clients/{c['id']}/verify-token").json()
    t2 = client.get(f"/api/clients/{c['id']}/verify-token").json()
    assert t1["token"] == t2["token"]  # stable (derived, not stored)
    assert t1["token"].startswith("scrawly-verify-")
    assert t1["path"].endswith(".txt")
