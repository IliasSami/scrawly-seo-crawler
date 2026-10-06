"""Auto-update CI gate (updater._ci_passed).

The gate must block a *reachable* API that reports a failed or pending check, but
must NOT strand a machine whose network/rate-limit makes the API unreachable — that
was the real-world bug where an install could never update on a rate-limited IP.
"""
import json
import urllib.request
from typing import Any, Callable

import pytest

import sentinelseo.updater as upd


def _fake_urlopen(payload: dict[str, Any]) -> Callable[..., Any]:
    data = json.dumps(payload).encode()

    class _Resp:
        def read(self, *a: Any) -> bytes:
            return data

        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *a: Any) -> None:
            return None

    def _open(req: Any, timeout: Any = None) -> "_Resp":
        return _Resp()

    return _open


def _github(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(upd, "_github_repo", lambda: "owner/repo")
    monkeypatch.delenv("SCRAWLY_REQUIRE_CI", raising=False)


def test_allows_update_when_api_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    _github(monkeypatch)

    def _boom(*a: Any, **k: Any) -> None:
        raise OSError("network down / rate limited")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    assert upd._ci_passed("abc") is True  # can't verify -> don't strand the install


def test_true_when_all_checks_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    _github(monkeypatch)
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen({"check_runs": [
        {"status": "completed", "conclusion": "success"},
        {"status": "completed", "conclusion": "success"}]}))
    assert upd._ci_passed("abc") is True


def test_false_on_definitive_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _github(monkeypatch)
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen({"check_runs": [
        {"status": "completed", "conclusion": "success"},
        {"status": "completed", "conclusion": "failure"}]}))
    assert upd._ci_passed("abc") is False


def test_false_while_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    _github(monkeypatch)
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(
        {"check_runs": [{"status": "in_progress", "conclusion": None}]}))
    assert upd._ci_passed("abc") is False


def test_false_when_no_checks_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    _github(monkeypatch)
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen({"check_runs": []}))
    assert upd._ci_passed("abc") is False


def test_gate_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRAWLY_REQUIRE_CI", "0")
    assert upd._ci_passed("abc") is True


def test_true_when_not_a_github_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCRAWLY_REQUIRE_CI", raising=False)
    monkeypatch.setattr(upd, "_github_repo", lambda: "")
    assert upd._ci_passed("abc") is True


# --- dependency + UI refresh after a pull ------------------------------------
class _Done:
    def __init__(self, code: int = 0) -> None:
        self.returncode = code
        self.stdout = ""
        self.stderr = ""


def test_dependency_refresh_leaves_browser_download_to_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    """The (slow) browser download must not hold up the update step: the app does
    it in the background after launch, and browser launches self-heal."""
    cmds: list[list[str]] = []

    def _run(cmd: list[str], timeout: int = 300) -> _Done:
        cmds.append(cmd)
        return _Done()

    monkeypatch.setattr(upd, "_run", _run)
    upd._refresh_python_deps()
    assert any(c[1:4] == ["-m", "pip", "install"] for c in cmds)
    assert not any("playwright" in c for c in cmds)


def test_ui_rebuild_skipped_when_release_ships_prebuilt_ui(
        tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "ui" / "dist").mkdir(parents=True)
    (tmp_path / "ui" / "package.json").write_text("{}")
    (tmp_path / "ui" / "dist" / "index.html").write_text("<html></html>")
    monkeypatch.setattr(upd, "ROOT", tmp_path)
    cmds: list[list[str]] = []

    def _run(cmd: list[str], timeout: int = 300) -> _Done:
        cmds.append(cmd)
        return _Done(0)   # `git ls-files --error-unmatch` succeeds: dist is tracked

    monkeypatch.setattr(upd, "_run", _run)
    upd._rebuild_ui()
    assert all("npm" not in c[0] for c in cmds)


def test_ui_rebuilt_when_dist_is_not_tracked(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/npm" if name == "npm" else None)
    (tmp_path / "ui" / "dist").mkdir(parents=True)
    (tmp_path / "ui" / "node_modules").mkdir()
    (tmp_path / "ui" / "package.json").write_text("{}")
    (tmp_path / "ui" / "dist" / "index.html").write_text("<html></html>")
    monkeypatch.setattr(upd, "ROOT", tmp_path)
    cmds: list[list[str]] = []

    def _run(cmd: list[str], timeout: int = 300) -> _Done:
        cmds.append(cmd)
        return _Done(1 if cmd[0] == "git" else 0)   # dist not tracked (dev checkout)

    monkeypatch.setattr(upd, "_run", _run)
    upd._rebuild_ui()
    assert any(c[0] == "/usr/bin/npm" and "build" in c for c in cmds)
