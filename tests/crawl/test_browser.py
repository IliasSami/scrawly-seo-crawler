"""launch_chromium heals a missing browser build instead of failing (the cause of
"PDF report won't download" after Playwright was upgraded without its browser)."""
import asyncio
from typing import Any

import pytest
from playwright.async_api import Error as PlaywrightError

import sentinelseo.crawl.browser as browser

MISSING = ("BrowserType.launch: Executable doesn't exist at /x/chrome-headless-shell\n"
           "Please run the following command to download new browsers: playwright install")


class _Chromium:
    def __init__(self, errors: list[Exception]) -> None:
        self.errors = list(errors)
        self.calls = 0

    async def launch(self, **kwargs: Any) -> str:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return "browser"


class _PW:
    def __init__(self, errors: list[Exception]) -> None:
        self.chromium = _Chromium(errors)


def _run(pw: _PW) -> Any:
    return asyncio.run(browser.launch_chromium(pw, headless=True))  # type: ignore[arg-type]


def test_detects_missing_browser_message() -> None:
    assert browser.is_missing_browser(PlaywrightError(MISSING))
    assert not browser.is_missing_browser(PlaywrightError("Target page closed"))


def test_launch_succeeds_without_install(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[bool] = []

    async def _install(timeout_s: float = 0) -> bool:
        called.append(True)
        return True

    monkeypatch.setattr(browser, "install_chromium", _install)
    pw = _PW([])
    assert _run(pw) == "browser"
    assert pw.chromium.calls == 1 and not called


def test_missing_browser_is_installed_then_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[bool] = []

    async def _install(timeout_s: float = 0) -> bool:
        called.append(True)
        return True

    monkeypatch.setattr(browser, "install_chromium", _install)
    pw = _PW([PlaywrightError(MISSING)])
    assert _run(pw) == "browser"
    assert called == [True]
    assert pw.chromium.calls == 2


def test_other_errors_are_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _install(timeout_s: float = 0) -> bool:
        raise AssertionError("must not install for unrelated errors")

    monkeypatch.setattr(browser, "install_chromium", _install)
    with pytest.raises(PlaywrightError, match="sandbox"):
        _run(_PW([PlaywrightError("sandbox crashed")]))


def test_failed_install_reraises_original(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _install(timeout_s: float = 0) -> bool:
        return False

    monkeypatch.setattr(browser, "install_chromium", _install)
    with pytest.raises(PlaywrightError, match="Executable doesn't exist"):
        _run(_PW([PlaywrightError(MISSING)]))


def test_install_sync_reports_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    def _boom(*a: Any, **k: Any) -> Any:
        raise OSError("no python")

    monkeypatch.setattr(subprocess, "run", _boom)
    assert browser.install_chromium_sync(timeout_s=1) is False
