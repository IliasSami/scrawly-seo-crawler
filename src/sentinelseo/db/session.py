import os
import re
from collections.abc import Iterator
from contextvars import ContextVar
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DB_PATH = os.getenv("SCRAWLY_DB_PATH", "scrawly.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Base (shared) engine. Used for anonymous work (the public-audit window) and as
# the schema template. AUTHENTICATED requests are routed to a per-workspace
# database instead — see `_maker_for` — so no user ever sees another workspace's
# clients, crawls or audits. Each new workspace therefore starts with a fresh,
# empty dashboard.
engine = create_engine(DATABASE_URL, echo=False)
_base_maker = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# The workspace whose data the current request touches. Set per-request by the
# OwnerScope middleware from the `X-Scrawly-Owner` header; empty => base DB.
_current_owner: ContextVar[str] = ContextVar("scrawly_owner", default="")

_owner_makers: dict[str, Any] = {}


def _safe_owner(owner: str) -> str:
    """Filesystem-safe, bounded token for the per-workspace DB filename."""
    return re.sub(r"[^A-Za-z0-9_-]", "", owner or "")[:64]


def _owner_db_path(safe: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(DB_PATH)) or "."
    return os.path.join(base_dir, f"scrawly_ws_{safe}.db")


def _maker_for(owner: str) -> Any:
    safe = _safe_owner(owner)
    if not safe:
        return _base_maker
    maker = _owner_makers.get(safe)
    if maker is None:
        # Provision (and migrate) this workspace's own database on first touch.
        from sentinelseo.db.migrate import run_migrations
        eng = create_engine(f"sqlite:///{_owner_db_path(safe)}", echo=False)
        run_migrations(eng)
        maker = sessionmaker(autocommit=False, autoflush=False, bind=eng)
        _owner_makers[safe] = maker
    return maker


def set_current_owner(owner: str) -> None:
    """Bind subsequent SessionLocal() calls on this request to a workspace."""
    _current_owner.set(owner or "")


def current_owner() -> str:
    return _current_owner.get()


def SessionLocal() -> Session:  # noqa: N802 — preserve the call-site name/shape
    """A session bound to the current request's workspace database (or the shared
    base DB when no workspace is set)."""
    return _maker_for(_current_owner.get())()


def get_db() -> Iterator[Any]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
