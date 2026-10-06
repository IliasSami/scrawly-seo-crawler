"""Per-workspace data isolation.

Each signed-in workspace gets its own database, selected by the `X-Scrawly-Owner`
header. A user must never see another workspace's projects/audits, and a brand new
workspace must start with an empty dashboard. This also proves the ContextVar the
owner-scope middleware sets reaches the sync endpoints running on the threadpool.

Note: IDs restart per database, so isolation is asserted by unique *name* — the
same id can legitimately exist in two different workspace DBs.
"""
import glob
import os

import pytest
from fastapi.testclient import TestClient

from sentinelseo.db import session as sess
from sentinelseo.web.api import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_workspace_dbs() -> None:
    """Start each test from clean per-workspace DBs so runs are deterministic."""
    sess._owner_makers.clear()
    base_dir = os.path.dirname(os.path.abspath(sess.DB_PATH)) or "."
    for f in glob.glob(os.path.join(base_dir, "scrawly_ws_*.db")):
        try:
            os.remove(f)
        except OSError:
            pass


def _add(owner: str, name: str) -> None:
    r = client.post("/api/clients",
                    headers={"X-Scrawly-Owner": owner},
                    json={"name": name, "base_url": f"https://{name}.example.com"})
    assert r.status_code == 200, r.text


def _names(owner: str | None) -> set[str]:
    headers = {"X-Scrawly-Owner": owner} if owner else {}
    r = client.get("/api/clients", headers=headers)
    assert r.status_code == 200, r.text
    return {c["name"] for c in r.json()}


class TestWorkspaceIsolation:
    def test_workspaces_cannot_see_each_others_projects(self) -> None:
        _add("ws_iso_a", "alpha-proj")
        _add("ws_iso_b", "bravo-proj")

        names_a = _names("ws_iso_a")
        names_b = _names("ws_iso_b")

        assert "alpha-proj" in names_a and "bravo-proj" not in names_a
        assert "bravo-proj" in names_b and "alpha-proj" not in names_b

    def test_new_workspace_starts_empty(self) -> None:
        _add("ws_iso_populated", "gamma-proj")
        assert _names("ws_iso_brand_new") == set()

    def test_team_members_share_one_workspace(self) -> None:
        # Same workspace id = same DB, so team members share projects.
        _add("ws_team_42", "delta-proj")
        assert "delta-proj" in _names("ws_team_42")   # a second member, same ws

    def test_workspace_data_is_invisible_to_the_base_db(self) -> None:
        _add("ws_iso_scoped", "zeta-proj")
        assert "zeta-proj" not in _names(None)   # anonymous/base DB can't see it
