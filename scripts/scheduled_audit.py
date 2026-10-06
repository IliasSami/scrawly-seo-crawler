#!/usr/bin/env python3
"""Scheduled audit with regression alerts (for cron / Task Scheduler / CI).

Runs a new audit for one of your sites (a "client" in the app), compares it with
that site's previous audit, and reports regressions: newly introduced Critical or
High issues. Exits with code 2 when regressions are found, so a scheduler can
alert you.

Scrawly must be open (it serves the local engine). Examples:

    # daily at 03:00, client 15, default settings
    0 3 * * *  cd ~/Scrawly && .venv/bin/python scripts/scheduled_audit.py 15

    # a saved crawl profile, explicit engine address
    .venv/bin/python scripts/scheduled_audit.py 15 --profile 2 --api http://127.0.0.1:53480

The engine address is found automatically from the running app; pass --api to
override it.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def _data_dir() -> Path:
    home = Path.home()
    if os.environ.get("SCRAWLY_DATA_DIR"):
        return Path(os.environ["SCRAWLY_DATA_DIR"]).expanduser()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Scrawly"
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", str(home))) / "Scrawly"
    return Path(os.environ.get("XDG_DATA_HOME", str(home / ".local" / "share"))) / "scrawly"


def _default_api() -> str:
    """The running app's engine: it remembers its port in the data folder."""
    try:
        port = int((_data_dir() / "port").read_text(encoding="utf-8").strip())
        return f"http://127.0.0.1:{port}"
    except (OSError, ValueError):
        return "http://127.0.0.1:8000"


def _call(api: str, path: str, data: Any = None, timeout: float = 30.0) -> Any:
    body = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{api}/api{path}", data=body,
        headers={"Content-Type": "application/json"} if body else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (local engine)
        return json.loads(r.read() or b"null")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run a scheduled audit and report regressions.")
    ap.add_argument("client_id", type=int, help="the site's client id (shown in the app)")
    ap.add_argument("--profile", type=int, help="saved crawl profile id")
    ap.add_argument("--api", default=_default_api(), help="engine address (default: the running app)")
    args = ap.parse_args()
    api = args.api.rstrip("/")

    try:
        crawls = _call(api, "/crawls")
    except OSError as exc:
        print(f"Can't reach Scrawly at {api} ({exc}). Is the app open?", file=sys.stderr)
        return 1
    mine = sorted((c for c in crawls if c.get("client_id") == args.client_id),
                  key=lambda c: c["id"], reverse=True)
    prev_id = mine[0]["id"] if mine else None

    payload: dict[str, Any] = {"client_id": args.client_id}
    if args.profile:
        payload["profile_id"] = args.profile
    crawl_id = _call(api, "/audit/start", payload)["crawl_id"]
    print(f"Started audit {crawl_id} for client {args.client_id}")

    status: dict[str, Any] = {}
    for _ in range(1800):   # up to an hour
        time.sleep(2)
        status = _call(api, f"/audit/status/{crawl_id}")
        if status.get("phase") in ("complete", "failed") or status.get("progress", 0) >= 100:
            break
    print("Audit status:", status.get("status"))

    if not prev_id:
        print("No previous audit to compare with yet.")
        return 0
    query = urllib.parse.urlencode({"crawl1": prev_id, "crawl2": crawl_id})
    diff = _call(api, f"/compare?{query}", timeout=120)
    summary = diff.get("summary", {})
    print(f"Compared with audit {prev_id}: resolved={summary.get('resolved')} "
          f"new={summary.get('new')} regressions={summary.get('regressions')}")
    for r in diff.get("regressions", [])[:25]:
        print(f"  REGRESSION [{r['severity']}] {r['key']}")
    return 2 if summary.get("regressions") else 0


if __name__ == "__main__":
    sys.exit(main())
