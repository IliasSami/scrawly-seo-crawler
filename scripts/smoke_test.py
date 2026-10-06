#!/usr/bin/env python3
"""Post-install smoke test: run with Scrawly's own environment after installing.

    .venv/bin/python scripts/smoke_test.py        (macOS / Linux)
    .venv\\Scripts\\python scripts\\smoke_test.py   (Windows)

Starts the local engine, checks the API and the bundled interface respond, and
renders a PDF with the crawler browser. Exits non-zero on any failure. CI runs it
on macOS, Windows and Linux after the one-line installer. It touches no website
and uses a throwaway database.
"""
import asyncio
import json
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=10) as r:  # noqa: S310 (localhost only)
        return bytes(r.read())


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="scrawly-smoke-"))
    os.environ["SCRAWLY_DB_PATH"] = str(tmp / "smoke.db")
    os.environ["SCRAWLY_AUTO_UPDATE"] = "0"

    import uvicorn

    from sentinelseo.report.pdf import html_to_pdf
    from sentinelseo.web.api import app

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 90
    edition = None
    while time.time() < deadline:
        try:
            edition = json.loads(_get(f"{base}/api/edition"))
            break
        except OSError:
            time.sleep(0.5)
    results: dict[str, object] = {"engine": bool(edition), "edition": edition}
    try:
        index = _get(f"{base}/")
        results["interface"] = b"SCRAWLY_EDITION" in index and b"<div" in index
    except OSError as exc:
        results["interface"] = f"failed: {exc}"
    try:
        pdf = asyncio.run(html_to_pdf("<h1>Scrawly smoke test</h1><p>PDF rendering works.</p>"))
        results["pdf"] = pdf[:5] == b"%PDF-"
    except Exception as exc:  # noqa: BLE001 (report any failure)
        results["pdf"] = f"failed: {type(exc).__name__}: {exc}"
    server.should_exit = True

    print(json.dumps(results, indent=2))
    ok = results["engine"] is True and results["interface"] is True and results["pdf"] is True
    print("SMOKE TEST", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
