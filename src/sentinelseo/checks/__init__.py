"""Check package.

`load_all_checks()` registers every check (per-URL + site-level). Previously
registration only happened as a side effect of the display endpoints running
`walk_packages`, so a fresh process running an audit before any UI call saw
*only* D01. Callers on the audit path (`run_audit`) invoke `load_all_checks()`
explicitly so registration is deterministic regardless of entry point.

NOTE: this is intentionally NOT auto-run at import time. `audit.context` imports
`checks.registry`, which would trigger this module's init; eagerly importing
`site_level.checks` here creates a circular import back into a half-initialised
`audit.context`. Call `load_all_checks()` from a fully-initialised context.
"""
from __future__ import annotations

import importlib
import pkgutil

import structlog

log = structlog.get_logger(__name__)

_loaded = False


def load_all_checks(force: bool = False) -> int:
    """Import every `*.checks` submodule so their `@register` decorators run.

    Idempotent (guards on `_loaded`). Resilient: a failure in one module logs and
    continues rather than blanking the whole registry. Returns modules imported.
    """
    global _loaded
    if _loaded and not force:
        return 0
    imported = 0
    for _finder, name, _is_pkg in pkgutil.walk_packages(__path__, __name__ + "."):
        if not name.endswith(".checks"):
            continue
        try:
            importlib.import_module(name)
            imported += 1
        except Exception as exc:  # noqa: BLE001 - one bad module must not blank all
            log.warning("check_module_import_failed", module=name, error=str(exc))
    _loaded = True
    return imported
