"""Test isolation + schema reconcile.

CRITICAL: point the DB at a throwaway temp file *before* importing anything that
builds the engine. Several tests (notably the MCP fix-layer tests) insert and then
DELETE Issue/Fix rows in teardown — without this they would wipe the developer's
real `scrawly.db`. Setting SCRAWLY_DB_PATH here makes the whole suite use an
isolated database.
"""
import os
import tempfile

os.environ["SCRAWLY_DB_PATH"] = os.path.join(tempfile.gettempdir(), "scrawly_test.db")
# The app modules call load_dotenv() at import (override=False), so a real .env
# with SCRAWLY_REQUIRE_AUTHZ=1 would silently switch the hard crawl gate on for
# the whole suite. Pin it off here (set before that import) — the authz tests
# turn it on explicitly via monkeypatch.
os.environ["SCRAWLY_REQUIRE_AUTHZ"] = ""

import pytest  # noqa: E402

from sentinelseo.db.migrate import run_migrations  # noqa: E402
from sentinelseo.db.session import engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _reconcile_schema() -> None:
    run_migrations(engine)
