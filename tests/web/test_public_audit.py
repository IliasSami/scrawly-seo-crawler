"""Public-window audit: tech detection + clientless read-only audit path."""
from typing import Any

import pytest
from fastapi.testclient import TestClient

import sentinelseo.detect as detect_mod
import sentinelseo.web.api as api
from sentinelseo.detect.fingerprint import DetectionResult
from sentinelseo.web.api import app

client = TestClient(app)


def _stub_detect(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_detect(url: str, **kw: Any) -> DetectionResult:
        return DetectionResult(stack="wordpress", subcategory="woocommerce", confidence=0.9)

    monkeypatch.setattr(detect_mod, "detect_stack", fake_detect)


def test_detect_endpoint_returns_preset(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_detect(monkeypatch)
    r = client.get("/api/detect", params={"url": "example.com"})
    assert r.status_code == 200
    body = r.json()
    assert body["url"] == "https://example.com"  # scheme coerced
    assert body["detection"]["stack"] == "wordpress"
    # The matching preset is resolved and returned for the customize panel.
    assert body["preset"]["label"] == "WordPress"
    assert "/wp-admin/" in body["preset"]["config"]["exclude_patterns"]
    assert "/cart/" in body["preset"]["config"]["exclude_patterns"]  # woo sub-type


def test_public_audit_bypasses_wp_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_detect(monkeypatch)
    launched: dict[str, Any] = {}

    async def fake_audit(crawl_id: int, target: str, config: dict[str, Any],
                         owner: str = "") -> None:
        launched["crawl_id"] = crawl_id
        launched["target"] = target
        launched["config"] = config

    monkeypatch.setattr(api, "do_audit", fake_audit)

    r = client.post("/api/public/audit", json={"url": "shop.example.com"})
    assert r.status_code == 200  # no WordPress connection required
    body = r.json()
    cid = body["crawl_id"]
    assert body["detection"]["stack"] == "wordpress"
    # The audit actually launched against the coerced URL with the preset config.
    assert launched["crawl_id"] == cid
    assert launched["target"] == "https://shop.example.com"
    assert launched["config"]["psi_enrich"] is False  # read-only recon
    assert launched["config"]["max_pages"] <= 500  # bounded public ceiling

    # The public bucket + its crawl stay hidden from the agency-facing lists...
    assert all(c["name"] != api.PUBLIC_CLIENT_NAME for c in client.get("/api/clients").json())
    assert all(c["id"] != cid for c in client.get("/api/crawls").json())
    # ...but are visible when explicitly requested.
    pub = client.get("/api/crawls", params={"include_public": True}).json()
    row = next(c for c in pub if c["id"] == cid)
    assert row["public"] is True
    assert row["target_url"] == "https://shop.example.com"


def test_public_audit_requires_url() -> None:
    r = client.post("/api/public/audit", json={"url": ""})
    assert r.status_code == 400


def test_public_audit_retention_and_latest(monkeypatch: pytest.MonkeyPatch) -> None:
    """The public window keeps only the newest audit, and /public/latest exposes it
    so the read-only audit can be restored after the user navigates away."""
    _stub_detect(monkeypatch)

    async def fake_audit(crawl_id: int, target: str, config: dict[str, Any],
                         owner: str = "") -> None:
        return None

    monkeypatch.setattr(api, "do_audit", fake_audit)

    # Clean slate: remove any public crawls left by earlier tests.
    for c in client.get("/api/crawls", params={"include_public": True}).json():
        if c["public"]:
            client.delete(f"/api/crawls/{c['id']}")
    assert client.get("/api/public/latest").json()["crawl_id"] is None

    first = client.post("/api/public/audit", json={"url": "one.example.com"}).json()["crawl_id"]
    assert client.get("/api/public/latest").json()["crawl_id"] == first

    second = client.post("/api/public/audit", json={"url": "two.example.com"}).json()["crawl_id"]
    assert second != first

    # Retention: only the newest public crawl survives; the older one is gone.
    pub_ids = [c["id"] for c in
               client.get("/api/crawls", params={"include_public": True}).json() if c["public"]]
    assert pub_ids == [second]
    assert client.delete(f"/api/crawls/{first}").status_code == 404

    # /public/latest points at the newest, with a friendly host for the UI card.
    latest = client.get("/api/public/latest").json()
    assert latest["crawl_id"] == second
    assert latest["host"] == "two.example.com"
    assert latest["url"] == "https://two.example.com"


def test_public_latest_includes_health_score() -> None:
    """The card shows the headline grade, so /public/latest must carry the same
    health score the dashboard computes for that crawl."""
    from sentinelseo.db.models import URL, Crawl, Issue
    from sentinelseo.db.session import SessionLocal

    db = SessionLocal()
    public = api._public_client(db)
    crawl = Crawl(client_id=public.id, target_url="https://health.example/",
                  config={}, url_count=3)
    db.add(crawl)
    db.commit()
    db.refresh(crawl)
    cid = int(crawl.id)  # newest id → the latest public crawl
    db.add_all([
        URL(crawl_id=cid, address="https://health.example/", status=200, indexable=True, depth=0),
        URL(crawl_id=cid, address="https://health.example/a", status=200, indexable=True, depth=1),
        URL(crawl_id=cid, address="https://health.example/b", status=404, indexable=False, depth=1),
    ])
    db.add(Issue(crawl_id=cid, check_id="B01", severity="Critical", tier="REVIEW",
                 affected_url_ids=[], evidence={}))
    db.commit()
    db.close()

    latest = client.get("/api/public/latest").json()
    assert latest["crawl_id"] == cid
    assert latest["running"] is False
    dash = client.get(f"/api/dashboard/{cid}").json()
    assert latest["health_score"] == dash["health_score"]
    assert isinstance(latest["health_score"], int)
