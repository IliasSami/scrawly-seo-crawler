"""Agentic fix — plan pre-flight + guards (no live AI/WP calls needed)."""
from typing import Any

import pytest
from fastapi.testclient import TestClient

import sentinelseo.web.api as api
from sentinelseo.db.models import URL, Client, Crawl, Issue
from sentinelseo.db.session import SessionLocal
from sentinelseo.web.api import app

client = TestClient(app)

_CONFIGURED = {"kind": "openai", "base_url": "http://x", "model": "m", "api_key": "k"}


def _seed(*, wp: bool = True, tier: str = "REVIEW", check_id: str = "D08",
          fix: str = "Rewrite the duplicate meta descriptions") -> int:
    db = SessionLocal()
    cl = Client(
        name="Site", base_url="https://wp.example/",
        wp_connection_key="key" if wp else None,
        detected_stack={"stack": "wordpress"} if wp else {"stack": "react"},
    )
    db.add(cl)
    db.commit()
    db.refresh(cl)
    crawl = Crawl(client_id=cl.id, target_url="https://wp.example/", config={}, url_count=2)
    db.add(crawl)
    db.commit()
    db.refresh(crawl)
    cid = int(crawl.id)
    db.add_all([
        URL(crawl_id=cid, address="https://wp.example/a", status=200, indexable=True),
        URL(crawl_id=cid, address="https://wp.example/b", status=200, indexable=True),
    ])
    db.commit()
    url_ids = [u.id for u in db.query(URL).filter(URL.crawl_id == cid).all()]
    issue = Issue(
        crawl_id=cid, check_id=check_id, severity="Medium", tier=tier,
        affected_url_ids=url_ids, evidence={}, recommended_fix=fix,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    iid = int(issue.id)
    db.close()
    return iid


def test_plan_flag_is_manual_only() -> None:
    iid = _seed(tier="FLAG")
    d = client.post("/api/fix/agent/plan", json={"issue_id": iid}).json()
    assert d["ok"] is False and d["reason"] == "flag"


def test_plan_requires_ai(monkeypatch: Any) -> None:
    monkeypatch.setattr(api, "_ai_config", lambda: {"kind": "openai", "base_url": "", "model": "", "api_key": ""})
    iid = _seed()
    d = client.post("/api/fix/agent/plan", json={"issue_id": iid}).json()
    assert d["ok"] is False and d["reason"] == "no_ai"


def test_plan_apply_on_wordpress_asks_to_confirm(monkeypatch: Any) -> None:
    monkeypatch.setattr(api, "_ai_config", lambda: _CONFIGURED)
    iid = _seed(wp=True)
    d = client.post("/api/fix/agent/plan", json={"issue_id": iid}).json()
    assert d["ok"] is True
    assert d["mode"] == "apply"
    assert d["field"] == "meta_desc"
    assert d["count"] == 2
    assert d["needs_confirm"] is True
    values = [o["value"] for o in d["options"]]
    assert "all" in values and "cancel" in values


def test_plan_non_wordpress_cannot_apply(monkeypatch: Any) -> None:
    monkeypatch.setattr(api, "_ai_config", lambda: _CONFIGURED)
    iid = _seed(wp=False)  # detected react, no connector
    d = client.post("/api/fix/agent/plan", json={"issue_id": iid}).json()
    assert d["ok"] is False and d["reason"] == "no_wp"


def test_plan_suggest_mode_no_confirm(monkeypatch: Any) -> None:
    monkeypatch.setattr(api, "_ai_config", lambda: _CONFIGURED)
    iid = _seed(check_id="H01", fix="Add descriptive alt text to the image")
    d = client.post("/api/fix/agent/plan", json={"issue_id": iid}).json()
    assert d["ok"] is True
    assert d["mode"] == "suggest"
    assert d["needs_confirm"] is False


def test_run_flag_streams_error() -> None:
    iid = _seed(tier="FLAG")
    r = client.post("/api/fix/agent/run", json={"issue_id": iid})
    assert r.status_code == 200
    assert "manual only" in r.text.lower()
    assert r.text.startswith("data:")


def test_plan_deterministic_canonical_needs_no_ai(monkeypatch: Any) -> None:
    # A missing canonical is fixed with the page's own clean URL: computed, so it
    # works with the connector even when NO AI provider is configured.
    monkeypatch.setattr(api, "_ai_config", lambda: {"kind": "openai", "base_url": "", "model": "", "api_key": ""})
    iid = _seed(check_id="C01", fix="Add a self-referencing canonical")
    d = client.post("/api/fix/agent/plan", json={"issue_id": iid}).json()
    assert d["ok"] is True
    assert d["field"] == "canonical"
    assert d["mode"] == "apply"


def test_noindex_issue_is_guidance_not_an_automatic_write(monkeypatch: Any) -> None:
    # A page may be noindexed on purpose: the agent advises, it never flips it.
    monkeypatch.setattr(api, "_ai_config", lambda: _CONFIGURED)
    iid = _seed(check_id="A04", fix="Remove the noindex directive so the page can rank")
    d = client.post("/api/fix/agent/plan", json={"issue_id": iid}).json()
    assert d["ok"] is True and d["mode"] == "guidance"


@pytest.mark.parametrize("check_id,field", [
    ("D01", "title"), ("D09", "meta_desc"), ("C01", "canonical"), ("H01", "alt"),
    ("D12", "h1"), ("F06", "anchor"), ("P03", ""), ("K03", ""), ("A04", ""), ("zz9", ""),
])
def test_fix_plan_is_an_explicit_map(check_id: str, field: str) -> None:
    """Wording no longer decides the field: P03 ("Title/meta/canonical/robots
    differ...") or K03 (sitemap contains noindex URLs) must not trigger a write."""
    assert api._fix_field_plan(check_id)["field"] == field


def test_live_write_requires_confirmation(monkeypatch: Any) -> None:
    monkeypatch.setattr(api, "_ai_config", lambda: _CONFIGURED)
    iid = _seed(wp=True)   # D08 -> apply meta description
    r = client.post("/api/fix/agent/run", json={"issue_id": iid, "scope": "all"})
    assert r.status_code == 200
    assert "confirm" in r.text.lower()
    assert '"stage": "error"' in r.text


def test_fixes_endpoint_shape() -> None:
    iid = _seed()
    # crawl id is the issue's crawl; fetch its fixes (none applied yet).
    from sentinelseo.db.models import Issue
    from sentinelseo.db.session import SessionLocal
    db = SessionLocal()
    cid = db.query(Issue).filter(Issue.id == iid).first().crawl_id
    db.close()
    d = client.get(f"/api/fixes/{cid}").json()
    assert d["count"] == 0
    assert d["fixes"] == []
    assert d["by_issue"] == {}


def test_revert_uses_the_sites_own_connection(monkeypatch: Any) -> None:
    """A fix written through a site's own Connector must be reverted on that same
    site (it used to fall back to the global connection: Invariant I2)."""
    from sentinelseo.db.models import Fix

    iid = _seed(wp=True)
    db = SessionLocal()
    issue = db.query(Issue).filter(Issue.id == iid).first()
    assert issue is not None
    crawl = db.query(Crawl).filter(Crawl.id == issue.crawl_id).first()
    assert crawl is not None
    expected_client = crawl.client_id
    fix = Fix(issue_id=iid, check_id="D08", tier="AUTO", before_state={"post_id": 7},
              after_state={}, applied_by="agent")
    db.add(fix)
    db.commit()
    fix_id = fix.id
    db.close()

    seen: dict[str, Any] = {}

    class _Fixer:
        def revert_fix(self, kind: str, before: dict[str, Any]) -> bool:
            seen.update(kind=kind, before=before)
            return True

    def _fixer(client_id: Any = None) -> _Fixer:
        seen["client_id"] = client_id
        return _Fixer()

    monkeypatch.setattr(api, "_get_wp_fixer", _fixer)
    r = client.post("/api/fix/revert", json={"fix_id": fix_id})
    assert r.status_code == 200 and r.json()["reverted"] is True
    assert seen["client_id"] == expected_client
    assert seen["kind"] == "meta" and seen["before"] == {"post_id": 7}
    again = client.post("/api/fix/revert", json={"fix_id": fix_id}).json()
    assert again["status"] == "already_reverted"
