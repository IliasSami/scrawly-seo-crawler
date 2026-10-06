"""Desktop launcher helpers: data dir override, Free-edition audit carry-over,
and the native bridge the UI uses for reports and external links (no GUI needed)."""
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import sentinelseo.desktop as desktop


def _db(path: Path, crawls: int = 0) -> Path:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE crawl (id INTEGER PRIMARY KEY)")
    con.execute("CREATE TABLE client (id INTEGER PRIMARY KEY)")
    for i in range(crawls):
        con.execute("INSERT INTO crawl (id) VALUES (?)", (i + 1,))
    con.commit()
    con.close()
    return path


class TestDataDir:
    def test_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "portable"
        monkeypatch.setenv("SCRAWLY_DATA_DIR", str(target))
        assert desktop._app_data_dir() == target
        assert target.is_dir()


class TestCarryOver:
    def test_copies_workspace_audits_over_empty_db(self, tmp_path: Path) -> None:
        _db(tmp_path / "scrawly.db", crawls=0)
        _db(tmp_path / "scrawly_ws_ws1.db", crawls=3)
        desktop._carry_over_audits(tmp_path)
        assert desktop._has_audits(tmp_path / "scrawly.db")
        assert (tmp_path / "scrawly.db.empty-backup").exists()     # kept, not deleted
        assert (tmp_path / "scrawly_ws_ws1.db").exists()           # copied, not moved

    def test_copies_when_no_base_db(self, tmp_path: Path) -> None:
        _db(tmp_path / "scrawly_ws_ws7.db", crawls=1)
        desktop._carry_over_audits(tmp_path)
        assert desktop._has_audits(tmp_path / "scrawly.db")
        assert not (tmp_path / "scrawly.db.empty-backup").exists()

    def test_never_overwrites_existing_audits(self, tmp_path: Path) -> None:
        _db(tmp_path / "scrawly.db", crawls=2)
        _db(tmp_path / "scrawly_ws_ws1.db", crawls=5)
        before = (tmp_path / "scrawly.db").read_bytes()
        desktop._carry_over_audits(tmp_path)
        assert (tmp_path / "scrawly.db").read_bytes() == before

    def test_noop_without_workspace_dbs(self, tmp_path: Path) -> None:
        desktop._carry_over_audits(tmp_path)
        assert not (tmp_path / "scrawly.db").exists()

    def test_unreadable_db_counts_as_having_audits(self, tmp_path: Path) -> None:
        bad = tmp_path / "scrawly.db"
        bad.write_bytes(b"not a database")
        assert desktop._has_audits(bad) is True


class _Win:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def create_file_dialog(self, kind: Any, **kw: Any) -> Any:
        self.calls.append(kw)
        return self.result


@pytest.fixture(autouse=True)
def _stub_webview(monkeypatch: pytest.MonkeyPatch) -> None:
    """CI installs the dev extras only (no GUI toolkit); save_pdf just needs the
    dialog-kind constant from pywebview."""
    monkeypatch.setitem(sys.modules, "webview",
                        SimpleNamespace(FileDialog=SimpleNamespace(SAVE=30), SAVE_DIALOG=30))


def _capture_opens(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    opened: list[str] = []

    def _open(url: str, *a: Any, **k: Any) -> bool:
        opened.append(url)
        return True

    monkeypatch.setattr("webbrowser.open", _open)
    return opened


class TestBridge:
    def test_open_external_allowlist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        opened = _capture_opens(monkeypatch)
        api = desktop._DesktopApi(1)
        assert api.open_external("https://iliassami.com/") is True
        assert api.open_external("mailto:me@iliassami.com") is True
        assert api.open_external("HTTP://example.com/") is True
        for bad in ("file:///etc/passwd", "javascript:alert(1)", "smb://x", "", 42):
            assert api.open_external(bad) is False  # type: ignore[arg-type]
        assert len(opened) == 3

    def test_open_report_writes_html_and_opens_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        opened = _capture_opens(monkeypatch)
        api = desktop._DesktopApi(1)
        monkeypatch.setattr(api, "_fetch", lambda path, owner, timeout=0: b"<html>report</html>")
        assert api.open_report(5, "") is True
        assert opened and opened[0].startswith("file://")
        path = Path(opened[0][len("file://"):])
        assert path.read_bytes() == b"<html>report</html>"
        path.unlink()

    def test_open_report_failure_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = desktop._DesktopApi(1)

        def _fail(path: str, owner: str, timeout: float = 0) -> bytes:
            raise OSError("backend down")

        monkeypatch.setattr(api, "_fetch", _fail)
        assert api.open_report(5, "") is False

    def test_save_pdf_writes_chosen_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        api = desktop._DesktopApi(1)
        target = tmp_path / "report.pdf"
        api._window = _Win(str(target))
        seen: dict[str, Any] = {}

        def _fetch(path: str, owner: str, timeout: float = 0) -> bytes:
            seen.update(path=path, timeout=timeout)
            return b"%PDF-1.7 test"

        monkeypatch.setattr(api, "_fetch", _fetch)
        assert api.save_pdf(9, "ws1", "scrawly-report-example.com.pdf") == str(target)
        assert target.read_bytes() == b"%PDF-1.7 test"
        assert seen["path"] == "/api/report/9/pdf"
        assert seen["timeout"] >= 600       # first PDF may download the browser
        assert api._window.calls[0]["save_filename"] == "scrawly-report-example.com.pdf"

    def test_save_pdf_cancel_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = desktop._DesktopApi(1)
        api._window = _Win(None)
        assert api.save_pdf(9, "", "") is None

    def test_save_pdf_render_error_returns_false(self, tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
        api = desktop._DesktopApi(1)
        api._window = _Win([str(tmp_path / "r.pdf")])   # some backends return a list

        def _fail(path: str, owner: str, timeout: float = 0) -> bytes:
            raise OSError("HTTP 500")

        monkeypatch.setattr(api, "_fetch", _fail)
        assert api.save_pdf(9, "", "r.pdf") is False
