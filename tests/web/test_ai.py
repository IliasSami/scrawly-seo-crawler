"""AI provider config: presets, secret masking, and fix-suggest guard."""
import pytest
from fastapi.testclient import TestClient

from sentinelseo.ai.provider import AI_PRESETS, is_configured
from sentinelseo.web.api import app

client = TestClient(app)


def test_presets_cover_popular_providers() -> None:
    for p in ("anthropic", "openai", "deepseek", "openrouter", "glm", "nara", "custom"):
        assert p in AI_PRESETS
    assert AI_PRESETS["anthropic"]["kind"] == "anthropic"
    assert AI_PRESETS["deepseek"]["kind"] == "openai"  # OpenAI-compatible


def test_is_configured() -> None:
    assert not is_configured({})
    assert not is_configured({"api_key": "k", "base_url": "u"})  # missing model
    assert is_configured({"api_key": "k", "base_url": "u", "model": "m"})


def test_api_key_masked_on_get_and_preserved_on_blank_put() -> None:
    # Save a key.
    client.put("/api/settings", json={"ai_api_key": "secret-123", "ai_model": "m", "ai_base_url": "u"})
    got = client.get("/api/settings").json()
    assert got["ai_api_key"] == ""          # never echoed
    assert got["ai_api_key_set"] is True     # but presence is exposed
    # A blank key in a later PUT must NOT wipe the saved one.
    client.put("/api/settings", json={"ai_model": "m2", "ai_api_key": ""})
    assert client.get("/api/settings").json()["ai_api_key_set"] is True


def _clear_ai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("SCRAWLY_AI_KIND", "SCRAWLY_AI_BASE_URL", "SCRAWLY_AI_MODEL", "SCRAWLY_AI_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_fix_suggest_requires_ai_config(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_ai_env(monkeypatch)
    client.put("/api/settings", json={"ai_base_url": "", "ai_model": "", "ai_kind": ""})
    r = client.post("/api/fix/suggest", json={"url": "https://x.com/", "field": "title"})
    assert r.status_code == 400


def test_ai_test_reports_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_ai_env(monkeypatch)
    client.put("/api/settings", json={"ai_base_url": "", "ai_model": ""})
    d = client.post("/api/ai/test").json()
    assert d["ok"] is False


def test_audit_requires_a_connection_method(monkeypatch: pytest.MonkeyPatch) -> None:
    # New model: read-only audit works for any connection method (URL-only is the
    # default), but a client with *no* method configured is still blocked.
    monkeypatch.delenv("SCRAWLY_WP_KEY", raising=False)
    client.put("/api/settings", json={"wp_connection_key": "", "wp_url": ""})
    c = client.post("/api/clients", json={"name": "NoConn", "base_url": "https://noconn.example"}).json()
    # Force an unconfigured client to exercise the gate (the API never leaves one
    # method-less on its own — creation defaults to url_only).
    from sentinelseo.db.models import Client as _C
    from sentinelseo.db.session import SessionLocal
    db = SessionLocal()
    row = db.query(_C).filter(_C.id == c["id"]).first()
    row.connection_method = None
    db.commit()
    db.close()
    r = client.post("/api/audit/start", json={"client_id": c["id"]})
    assert r.status_code == 400 and "connection method" in r.json()["detail"].lower()


def test_fix_apply_requires_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_ai_env(monkeypatch)
    client.put("/api/settings", json={"ai_base_url": "", "ai_model": "", "ai_kind": ""})
    r = client.post("/api/fix/apply", json={"issue_id": 1, "url": "https://x.com/", "new_value": "v", "confirm": True})
    assert r.status_code == 400 and "AI" in r.json()["detail"]
