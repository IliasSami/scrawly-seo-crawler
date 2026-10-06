"""Crawl gate (Free edition): every crawl is allowed. There are no accounts,
quotas or authorizations, so there is nothing to check."""
from __future__ import annotations

from typing import Any

from fastapi import Request


def authz_required() -> bool:
    return False


def require_crawl_authz(request: Request) -> Any:
    return None
