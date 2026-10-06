"""Scrawly desktop launcher: a real GUI app, cross-platform (macOS/Windows/Linux).

Runs the Scrawly engine locally (so audits use THIS machine's resources) and
opens it in a native window via pywebview. Everything runs on this computer.

Run:  scrawly           (console entry, after install)
  or: python -m sentinelseo.desktop

On launch it self-updates from the git checkout unless SCRAWLY_AUTO_UPDATE=0.
"""
from __future__ import annotations

import os
import shutil
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

import structlog

from sentinelseo import edition

log = structlog.get_logger(__name__)


def _app_data_dir() -> Path:
    """Per-user data dir where the local audit DB lives (stays on this machine).
    ``SCRAWLY_DATA_DIR`` overrides it (portable installs, testing)."""
    home = Path.home()
    if os.environ.get("SCRAWLY_DATA_DIR"):
        base = Path(os.environ["SCRAWLY_DATA_DIR"]).expanduser()
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support" / "Scrawly"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", str(home))) / "Scrawly"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(home / ".local" / "share"))) / "scrawly"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _port_is_free(port: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _stable_port() -> int:
    """Reuse the same local port across launches so the app's origin stays constant.

    The webview's storage (UI preferences, and the signed-in session in the managed
    edition) is keyed by origin (host:port). A fresh random port every launch would
    be a new origin each time, so we remember the port and reuse it when free."""
    if os.environ.get("SCRAWLY_PORT"):
        return int(os.environ["SCRAWLY_PORT"])
    pf = _app_data_dir() / "port"
    try:
        saved = int(pf.read_text(encoding="utf-8").strip())
        if 1024 <= saved <= 65535 and _port_is_free(saved):
            return saved
    except (OSError, ValueError):
        pass
    port = _free_port()
    try:
        pf.write_text(str(port), encoding="utf-8")
    except OSError:
        pass
    return port


def _wait_for_http(url: str, timeout: float = 40.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=1.5)  # noqa: S310 (localhost only)
            return True
        except OSError:
            time.sleep(0.3)
    return False


def _has_audits(db: Path) -> bool:
    """True when the database holds any project or crawl. Unreadable counts as
    True, so a database we can't inspect is never replaced."""
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            for table in ("crawl", "client"):
                try:
                    if con.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():  # noqa: S608
                        return True
                except sqlite3.OperationalError:
                    continue  # table not created yet
            return False
        finally:
            con.close()
    except sqlite3.Error:
        return True


def _carry_over_audits(data_dir: Path) -> None:
    """Free edition: keep earlier audits visible after switching from the managed
    edition. Managed builds keep each account's audits in ``scrawly_ws_<id>.db``;
    the Free edition has one local database (``scrawly.db``). On the first Free
    launch, copy (never move) the most recently used workspace database so nothing
    the user already ran disappears. An existing but empty ``scrawly.db`` is kept
    as a backup, never deleted."""
    target = data_dir / "scrawly.db"
    if target.exists() and _has_audits(target):
        return
    candidates = sorted((p for p in data_dir.glob("scrawly_ws_*.db") if _has_audits(p)),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return
    try:
        if target.exists():
            target.replace(data_dir / "scrawly.db.empty-backup")
        shutil.copy2(candidates[0], target)
        log.info("desktop.audits_carried_over", source=candidates[0].name)
    except OSError as exc:
        log.warning("desktop.carry_over_failed", error=str(exc))


class _DesktopApi:
    """Bridge for things a sandboxed webview can't do on its own. The UI can't use
    window.open() or trigger downloads inside pywebview, so it calls these instead:
    open the audit report in the system browser, save files (report PDF, exports,
    the WordPress plugin) via a native Save dialog, and open external links.
    Fetches go to the local backend with the workspace header, so the right
    per-workspace data is used."""

    def __init__(self, port: int) -> None:
        self._port = port
        # The pywebview window, set right after creation. Private (leading underscore)
        # so pywebview doesn't try to expose the window object itself to JavaScript.
        self._window: Any = None

    def _fetch(self, path: str, owner: str, timeout: float = 180.0) -> bytes:
        req = urllib.request.Request(
            f"http://127.0.0.1:{self._port}{path}",
            headers={"X-Scrawly-Owner": owner or ""})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (localhost only)
            return bytes(r.read())

    def open_report(self, crawl_id: int, owner: str) -> bool:
        """Open the HTML report in the user's default browser."""
        try:
            html = self._fetch(f"/api/report/{int(crawl_id)}", owner)
            with tempfile.NamedTemporaryFile(
                    prefix=f"scrawly-report-{int(crawl_id)}-", suffix=".html",
                    delete=False) as fd:
                fd.write(html)
            webbrowser.open(Path(fd.name).as_uri())
            return True
        except (OSError, ValueError) as exc:
            log.warning("desktop.open_report_failed", crawl_id=crawl_id, error=str(exc))
            return False

    def _ask_save_path(self, filename: str) -> str | bool | None:
        """Native Save dialog (default location: Desktop). Returns the chosen path,
        None if the user cancelled, or False if the dialog couldn't be shown."""
        import webview

        desktop = Path.home() / "Desktop"
        if not desktop.is_dir():
            desktop = Path.home()
        file_dialog = getattr(webview, "FileDialog", None)
        save_kind = file_dialog.SAVE if file_dialog is not None else webview.SAVE_DIALOG
        try:
            result = self._window.create_file_dialog(
                save_kind, directory=str(desktop), save_filename=Path(filename).name)
        except Exception as exc:  # noqa: BLE001 (GUI backends raise assorted errors)
            log.warning("desktop.save_dialog_failed", error=str(exc))
            return False
        path = result[0] if isinstance(result, (list, tuple)) and result else result
        return str(path) if path else None

    def _save_fetched(self, api_path: str, owner: str, filename: str,
                      timeout: float) -> str | bool | None:
        target = self._ask_save_path(filename)
        if not isinstance(target, str):
            return target  # None = cancelled, False = dialog failed
        try:
            Path(target).write_bytes(self._fetch(api_path, owner, timeout=timeout))
            return target
        except (OSError, ValueError) as exc:
            log.warning("desktop.save_failed", path=api_path, error=str(exc))
            return False

    def save_pdf(self, crawl_id: int, owner: str, filename: str) -> str | bool | None:
        """Save the report PDF via a native dialog (default location: Desktop).
        Returns the saved path on success, False on error, None if cancelled."""
        # Generous timeout: the first PDF on a new machine may need to fetch the
        # browser component before rendering.
        return self._save_fetched(f"/api/report/{int(crawl_id)}/pdf", owner,
                                  filename or f"scrawly-report-{int(crawl_id)}.pdf", 900.0)

    def save_download(self, api_path: str, owner: str, filename: str) -> str | bool | None:
        """Save any file the local backend serves (e.g. the WordPress Connector
        plugin) via a native dialog. Only local /api/ paths are allowed."""
        if not isinstance(api_path, str) or not api_path.startswith("/api/") or ".." in api_path:
            return False
        return self._save_fetched(api_path, owner, filename or "download", 300.0)

    def save_text(self, filename: str, text: str) -> str | bool | None:
        """Save text produced in the UI (e.g. a CSV export) via a native dialog."""
        target = self._ask_save_path(filename or "scrawly-export.txt")
        if not isinstance(target, str):
            return target
        try:
            Path(target).write_text(str(text), encoding="utf-8", newline="")
            return target
        except OSError as exc:
            log.warning("desktop.save_text_failed", error=str(exc))
            return False

    def open_external(self, url: str) -> bool:
        """Open a web or mail link in the user's default app. Only http(s): and
        mailto: links are allowed, so page content can't launch anything else."""
        if not isinstance(url, str) or not url.lower().startswith(
                ("https://", "http://", "mailto:")):
            return False
        return bool(webbrowser.open(url))


def main() -> None:
    # 0) Settings from the .env file in the Scrawly folder (e.g. SCRAWLY_AUTO_UPDATE,
    #    SCRAWLY_DATA_DIR), loaded first so every step below sees them. Values
    #    already set in the environment win.
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    edition.apply_desktop_defaults()

    # 1) Self-update from the git checkout (best effort) so installs stay current.
    if os.environ.get("SCRAWLY_AUTO_UPDATE", "1").lower() not in ("0", "false", "off", "no"):
        try:
            from sentinelseo.updater import self_update
            self_update()
        except Exception as exc:  # noqa: BLE001 (an update failure must never block launch)
            log.warning("desktop.update_check_skipped", error=str(exc))

    # 2) Local, per-user audit database (audit data never leaves this machine).
    data_dir = _app_data_dir()
    if edition.is_free():
        _carry_over_audits(data_dir)
    os.environ.setdefault("SCRAWLY_DB_PATH", str(data_dir / "scrawly.db"))

    # 3) Start the local backend in the background.
    try:
        import uvicorn

        from sentinelseo.web.api import app
    except ImportError as exc:
        sys.exit(f"[scrawly] backend not installed ({exc}).\n"
                 "Run the installer first:  python3 scripts/install.py")

    # Make sure the browser used for PDF reports, screenshots and JS rendering
    # matches the installed Playwright (an update can leave it missing). Runs in
    # the background so the window opens immediately; quick when nothing's needed.
    from sentinelseo.crawl.browser import install_chromium_sync
    threading.Thread(target=install_chromium_sync, daemon=True).start()

    port = _stable_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()

    url = f"http://127.0.0.1:{port}/"
    if not _wait_for_http(url):
        sys.exit("[scrawly] the local backend didn't start in time.")

    # 4) Open the native GUI window (blocks until closed).
    try:
        import webview
    except ImportError:
        sys.exit("[scrawly] pywebview isn't installed.\n"
                 "  macOS/Windows:  pip install pywebview\n"
                 "  Linux: also install a webview backend (see docs/DESKTOP.md)")
    api = _DesktopApi(port)
    api._window = webview.create_window(
        "Scrawly", url, width=1360, height=900, min_size=(1024, 700), js_api=api)
    # Persist storage (not private/ephemeral) so UI preferences (and the managed
    # edition's signed-in session) survive across launches.
    webview.start(private_mode=False, storage_path=str(data_dir / "webview"))
    server.should_exit = True


if __name__ == "__main__":
    main()
