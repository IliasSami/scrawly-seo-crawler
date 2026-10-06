from unittest.mock import Mock, patch

import pytest

from sentinelseo.db.models import Base, Fix, Issue
from sentinelseo.db.session import SessionLocal, engine
from sentinelseo.mcp.server import apply_fix, revert


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Create test issues
    issue_flag = Issue(
        crawl_id=1,
        check_id="M01",
        severity="Critical",
        tier="FLAG",
        affected_url_ids=[],
        evidence={},
    )
    issue_auto = Issue(
        crawl_id=1,
        check_id="D01",
        severity="High",
        tier="AUTO-SAFE",
        affected_url_ids=[],
        evidence={},
    )
    db.add(issue_flag)
    db.add(issue_auto)
    db.commit()
    db.refresh(issue_flag)
    db.refresh(issue_auto)

    yield {"flag": issue_flag.id, "auto": issue_auto.id}

    db.query(Fix).delete()
    db.query(Issue).delete()
    db.commit()
    db.close()


def test_apply_fix_flag_tier_refused_even_with_confirm(setup_db):
    flag_id = setup_db["flag"]
    with pytest.raises(ValueError, match="Cannot auto-fix FLAG tier issue."):
        apply_fix(flag_id, confirm=True)


def test_apply_fix_without_confirm_true_raises(setup_db):
    auto_id = setup_db["auto"]
    with pytest.raises(ValueError, match="confirm=True is required to apply fixes."):
        apply_fix(auto_id, confirm=False)


@patch("sentinelseo.mcp.server._get_fixer")
def test_apply_fix_snapshot_failure_prevents_write(mock_get_fixer, setup_db):
    auto_id = setup_db["auto"]
    mock_fixer = Mock()
    # Snapshot (the read of before-state) fails -> nothing is written, no Fix row.
    mock_fixer.snapshot.side_effect = Exception("Network timeout during fetch")
    mock_get_fixer.return_value = mock_fixer

    with pytest.raises(Exception, match="Network timeout during fetch"):
        args = {"post_id": 1, "field": "title", "new_value": "test"}
        apply_fix(auto_id, confirm=True, fix_type="meta", args=args)

    mock_fixer.commit_write.assert_not_called()
    db = SessionLocal()
    assert db.query(Fix).count() == 0
    db.close()


@patch("sentinelseo.mcp.server._get_fixer")
def test_apply_fix_write_failure_leaves_valid_rollback(mock_get_fixer, setup_db):
    # I2: the before-state must be persisted to the `fix` table BEFORE the write,
    # so a mid-write failure still leaves a valid rollback record.
    auto_id = setup_db["auto"]
    mock_fixer = Mock()
    mock_fixer.snapshot.return_value = {
        "fix_type": "meta", "post_id": 1, "field": "title",
        "meta_key": "test_key", "before_val": "old", "new_value": "new",
        "action": "pending",
    }
    mock_fixer.commit_write.side_effect = Exception("Write failed mid-flight")
    mock_get_fixer.return_value = mock_fixer

    with pytest.raises(Exception, match="rollback record preserved"):
        args = {"post_id": 1, "field": "title", "new_value": "new"}
        apply_fix(auto_id, confirm=True, fix_type="meta", args=args)

    db = SessionLocal()
    fixes = db.query(Fix).all()
    assert len(fixes) == 1  # rollback record persisted before the write
    assert fixes[0].before_state["before_val"] == "old"  # valid rollback data
    db.close()


@patch("sentinelseo.mcp.server._get_fixer")
def test_revert_restores_state(mock_get_fixer, setup_db):
    auto_id = setup_db["auto"]
    mock_fixer = Mock()
    mock_fixer.snapshot.return_value = {
        "fix_type": "meta", "post_id": 1, "field": "title",
        "meta_key": "test_key", "before_val": "old", "new_value": "test",
        "action": "pending",
    }
    mock_fixer.commit_write.return_value = {
        "fix_type": "meta", "post_id": 1, "field": "title",
        "meta_key": "test_key", "before_val": "old", "new_value": "test",
        "action": "updated",
    }
    mock_get_fixer.return_value = mock_fixer

    args = {"post_id": 1, "field": "title", "new_value": "test"}
    resp = apply_fix(auto_id, confirm=True, fix_type="meta", args=args)
    fix_id = resp["fix_id"]

    mock_fixer.revert_fix.return_value = True
    rev_resp = revert(fix_id)
    assert rev_resp["status"] == "success"
    assert rev_resp["reverted"] is True

    # Check DB
    db = SessionLocal()
    fix = db.query(Fix).filter(Fix.id == fix_id).first()
    assert fix.reverted is True
    db.close()


# --- tools fixed for the public release ---------------------------------------
def test_create_redirect_is_tier_gated(setup_db):
    from sentinelseo.mcp.server import create_redirect
    with pytest.raises(ValueError, match="FLAG"):
        create_redirect(setup_db["flag"], "https://x.test/a", "https://x.test/b", confirm=True)


def test_create_redirect_requires_confirm(setup_db):
    from sentinelseo.mcp.server import create_redirect
    with pytest.raises(ValueError, match="confirm=True"):
        create_redirect(setup_db["auto"], "https://x.test/a", "https://x.test/b")


@patch("sentinelseo.mcp.server._get_fixer")
def test_create_redirect_records_rollback_before_writing(mock_get_fixer, setup_db):
    """I2: a redirect gets a Fix row (before-state) before the live write."""
    from sentinelseo.mcp.server import create_redirect
    order = []
    fixer = Mock()
    def _snapshot(kind, args):
        order.append("snapshot")
        return {"fix_type": "redirect", "source_url": args["source_url"],
                "target_url": args["target_url"], "existing_id": None, "action": "pending"}

    fixer.snapshot.side_effect = _snapshot

    def _write(before):
        db = SessionLocal()
        assert db.query(Fix).count() == 1   # rollback record already durable
        db.close()
        order.append("write")
        return {**before, "redirect_id": 42, "action": "created"}

    fixer.commit_write.side_effect = _write
    mock_get_fixer.return_value = fixer
    out = create_redirect(setup_db["auto"], "https://x.test/a", "https://x.test/b", confirm=True)
    assert order == ["snapshot", "write"]
    db = SessionLocal()
    fix = db.query(Fix).filter(Fix.id == out["fix_id"]).first()
    assert fix is not None and fix.before_state["redirect_id"] == 42
    db.close()


def test_propose_fix_returns_the_real_recommendation(setup_db):
    from sentinelseo.mcp.server import propose_fix
    out = propose_fix(setup_db["flag"])
    assert out["check_id"] == "M01"
    assert out["auto_fixable"] is False
    assert "proposal" not in out   # no placeholder text


def test_list_crawls_tool_exists_and_fake_crawl_site_is_gone():
    import sentinelseo.mcp.server as server
    assert not hasattr(server, "crawl_site")
    assert isinstance(server.list_crawls(limit=5), list)
