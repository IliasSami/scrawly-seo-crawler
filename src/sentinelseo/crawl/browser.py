"""Launch the crawler's Chromium, downloading it first if it's missing.

Playwright's Python package and its browser build are versioned together. An
update (or a rebuilt environment) can bring a newer package whose matching
browser hasn't been downloaded yet, and then every launch fails with
"Executable doesn't exist": no PDF reports, no screenshots, no JavaScript
rendering. Instead of failing, fetch the matching browser once and retry.
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
import threading
from typing import Any

import structlog
from playwright.async_api import Browser, Playwright
from playwright.async_api import Error as PlaywrightError

log = structlog.get_logger(__name__)

_install_lock = threading.Lock()
_MISSING_MARKERS = ("Executable doesn't exist", "playwright install")


def is_missing_browser(exc: BaseException) -> bool:
    """True when a launch failed because the browser build isn't downloaded."""
    msg = str(exc)
    return any(marker in msg for marker in _MISSING_MARKERS)


def install_chromium_sync(timeout_s: float = 900.0) -> bool:
    """Download the Chromium build matching the installed Playwright. Idempotent and
    quick when it's already present. Serialized so concurrent callers don't race."""
    with _install_lock:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True, text=True, timeout=timeout_s, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("browser.install_failed", error=str(exc))
            return False
        if result.returncode != 0:
            log.warning("browser.install_failed", output=(result.stdout + result.stderr)[-500:])
            return False
        return True


async def install_chromium(timeout_s: float = 900.0) -> bool:
    return await asyncio.to_thread(install_chromium_sync, timeout_s)


async def launch_chromium(pw: Playwright, **kwargs: Any) -> Browser:
    """``pw.chromium.launch(**kwargs)``, but a missing browser build is downloaded
    and the launch retried once instead of failing."""
    try:
        return await pw.chromium.launch(**kwargs)
    except PlaywrightError as exc:
        if not is_missing_browser(exc):
            raise
        log.info("browser.missing_installing")
        if not await install_chromium():
            raise
    return await pw.chromium.launch(**kwargs)
