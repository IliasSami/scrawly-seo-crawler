"""Auto-update from the git checkout.

Because Scrawly is installed by cloning the repo, "shipping an update" is just
pushing to GitHub: on next launch each install fetches, fast-forwards to the
latest commit, refreshes deps + rebuilds the UI, and re-executes so the new code
runs immediately. Disable with SCRAWLY_AUTO_UPDATE=0.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)

# repo root: …/Scrawly (this file is …/Scrawly/src/sentinelseo/updater.py)
ROOT = Path(__file__).resolve().parents[2]


def _run(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)


def _git(*args: str) -> str:
    return _run(["git", *args], timeout=60).stdout.strip()


def _has_git() -> bool:
    if not (ROOT / ".git").exists():
        return False
    try:
        return _run(["git", "--version"], timeout=15).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def self_update() -> None:
    """Fast-forward to the latest pushed commit and rebuild, then re-exec. No-op
    when this isn't a git checkout, there's no upstream, or already up to date."""
    if not _has_git():
        return
    if _run(["git", "fetch", "--quiet"], timeout=60).returncode != 0:
        return  # offline / no remote — carry on with what's installed
    local = _git("rev-parse", "@")
    upstream = _git("rev-parse", "@{u}")
    if not upstream or local == upstream:
        return  # already current

    # Only advance to a commit whose CI gate passed, so an install never pulls a
    # broken version even though pushes go straight to main.
    if not _ci_passed(upstream):
        log.info("updater.waiting_for_ci",
                 message="The newest version hasn't passed CI yet; staying on the current tested version.")
        return

    log.info("updater.updating", message="A new (CI-passed) version is available; updating.")
    pull = _run(["git", "pull", "--ff-only"])
    if pull.returncode != 0:
        log.warning("updater.skipped_local_changes",
                    message="Auto-update skipped (local changes on this checkout). Run `git pull` to update.")
        return

    _refresh_python_deps()
    _rebuild_ui()

    log.info("updater.restarting", message="Updated to the latest version; restarting.")
    os.execv(sys.executable, [sys.executable, "-m", "sentinelseo.desktop"])


def _github_repo() -> str:
    """`owner/repo` from the origin remote, or '' if it isn't a GitHub checkout."""
    url = _git("config", "--get", "remote.origin.url")
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", url)
    return m.group(1) if m else ""


def _ci_passed(sha: str) -> bool:
    """True when CI for `sha` is green — or when its status genuinely can't be reached.

    The gate blocks a *reachable* API that reports a failed or still-pending check, so
    an install never advances to a commit CI rejected or hasn't vetted yet. But if the
    GitHub API is unreachable (offline, or the unauthenticated 60/hour rate limit is
    exhausted — common on shared or NAT'd IPs), we can't verify, and blocking on that
    forever would mean the machine never updates at all. In that case we allow the
    fast-forward and log why, rather than stranding the install. Set
    SCRAWLY_REQUIRE_CI=0 to skip the gate entirely (e.g. a fork without CI)."""
    if os.getenv("SCRAWLY_REQUIRE_CI", "1").lower() in ("0", "false", "off", "no"):
        return True
    repo = _github_repo()
    if not repo:
        return True  # not a GitHub checkout — nothing to gate against
    api = f"https://api.github.com/repos/{repo}/commits/{sha}/check-runs"
    try:
        req = urllib.request.Request(api, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "scrawly-updater",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            runs = json.load(resp).get("check_runs", [])
    except Exception as exc:  # noqa: BLE001
        # Can't reach GitHub (offline / rate-limited): we can't verify CI, so don't
        # strand this machine on an old version forever — allow the update and log it.
        log.info("updater.ci_unverifiable", error=type(exc).__name__, message="Updating anyway.")
        return True
    return _checks_allow_update(runs)


# Scrawly's own CI checks: the quality gate, plus the cross-platform installer
# test on the public repo. Other check runs on a commit (GitHub's dependency
# graph, Pages, future integrations) must not decide whether users update.
def _is_scrawly_check(run: dict[str, Any]) -> bool:
    name = str(run.get("name") or "")
    return name == "gate" or name.startswith("install")


def _checks_allow_update(runs: list[dict[str, Any]]) -> bool:
    """The gate passed and none of Scrawly's checks failed or are still running.
    Skipped or neutral checks (a job that only runs on the public repo) are fine."""
    ours = [r for r in runs if _is_scrawly_check(r)]
    gate = [r for r in ours if r.get("name") == "gate"]
    if not gate:
        return False  # CI hasn't reported the gate yet: wait for the next launch
    ok_states = {"success", "skipped", "neutral"}
    finished = all(r.get("status") == "completed" for r in ours)
    clean = all(r.get("conclusion") in ok_states for r in ours)
    gate_passed = all(r.get("conclusion") == "success" for r in gate)
    return finished and clean and gate_passed


def _refresh_python_deps() -> None:
    # Idempotent + fast when nothing changed; keeps new deps in sync after a pull.
    try:
        _run([sys.executable, "-m", "pip", "install", "-q", "-e", ".[desktop]"])
        # A newer Playwright needs its matching browser build. That download can
        # take minutes, so it isn't done here (it would hold up the window): the
        # app fetches it in the background right after launch, and any browser
        # launch heals a missing build on demand (crawl/browser.py).
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("updater.deps_refresh_skipped", error=str(exc))


def _ui_prebuilt() -> bool:
    """True when the checkout ships a prebuilt UI (release builds commit ui/dist), so
    a pull already brought the new UI and Node.js isn't needed at all."""
    if not (ROOT / "ui" / "dist" / "index.html").exists():
        return False
    return _run(["git", "ls-files", "--error-unmatch", "ui/dist/index.html"],
                timeout=30).returncode == 0


def _rebuild_ui() -> None:
    ui = ROOT / "ui"
    if not (ui / "package.json").exists() or _ui_prebuilt():
        return
    npm = shutil.which("npm")   # npm.cmd on Windows; a bare "npm" isn't found there
    if not npm:
        log.warning("updater.ui_rebuild_skipped", error="npm not found")
        return
    try:
        if not (ui / "node_modules").is_dir():
            _run([npm, "--prefix", str(ui), "install"], timeout=600)
        _run([npm, "--prefix", str(ui), "run", "build"], timeout=600)
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("updater.ui_rebuild_skipped", error=str(exc))
