#!/usr/bin/env python3
"""One-command installer for the Scrawly desktop app (macOS / Windows / Linux).

From a copy of the repository, run:

    python3 scripts/install.py      # macOS / Linux
    py scripts\\install.py           # Windows

It sets up an isolated environment, installs Scrawly, the window runtime and the
crawler browser, makes sure the user interface is ready (release downloads ship
it prebuilt, so Node.js is only needed when building from source), and adds
Scrawly to your apps: Applications on macOS, the app menu on Linux, and the Start
Menu plus a Desktop shortcut on Windows. Audits run on THIS machine.

Environment switches:
  SCRAWLY_NO_SHORTCUTS=1   don't add Scrawly to Applications / app menu / Start Menu
  SCRAWLY_SKIP_LAUNCHER=1  internal: used by the launcher's self-repair

This script deliberately uses only the standard library and plain print(): it runs
before any of Scrawly's own dependencies exist.
"""
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
UI = ROOT / "ui"
ICONS = ROOT / "assets" / "icons"
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"


def _venv_bin(name: str) -> Path:
    d = VENV / ("Scripts" if IS_WIN else "bin")
    return d / (name + (".exe" if IS_WIN else ""))


def _run(cmd: list, **kw) -> None:
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, cwd=str(ROOT), **kw)


def _need(cmd: str, hint: str) -> str:
    found = shutil.which(cmd)
    if found is None:
        sys.exit(f"  ✗ '{cmd}' not found. {hint}")
    return found


def _ensure_modern_python() -> None:
    """`python3` is often an old system build (e.g. 3.9 on macOS). If we're too
    old, re-launch with a newer interpreter that's already installed, so the
    documented `python3 scripts/install.py` just works."""
    if sys.version_info >= (3, 11):
        return
    for name in ("python3.13", "python3.12", "python3.11"):
        exe = shutil.which(name)
        if exe:
            print(f"  (using {name}: your default python3 is {sys.version.split()[0]})")
            os.execv(exe, [exe, *sys.argv])
    sys.exit(
        f"  ✗ Python 3.11 or newer is required (your python3 is {sys.version.split()[0]}).\n"
        "    Install a newer Python, then run this again:\n"
        "      macOS:    brew install python@3.12\n"
        "      Windows:  winget install Python.Python.3.12\n"
        "      Linux:    sudo apt install python3.12  (or your distribution's package)\n"
        "      or download it from https://www.python.org/downloads/")


def _ui_is_tracked() -> bool:
    """Release downloads commit the built UI (ui/dist) so no Node.js is needed."""
    if not (UI / "dist" / "index.html").exists() or not (ROOT / ".git").exists():
        return False
    git = shutil.which("git")
    if not git:
        return False
    r = subprocess.run([git, "ls-files", "--error-unmatch", "ui/dist/index.html"],
                       cwd=str(ROOT), capture_output=True, text=True)
    return r.returncode == 0


def _prepare_ui() -> str:
    """Use the prebuilt UI when present; otherwise build it with Node.js."""
    if _ui_is_tracked():
        return "ready (prebuilt)"
    npm = shutil.which("npm")   # npm.cmd on Windows: a bare "npm" isn't runnable there
    if npm:
        _run([npm, "--prefix", "ui", "install", "--silent"])
        _run([npm, "--prefix", "ui", "run", "build"])
        return "built"
    if (UI / "dist" / "index.html").exists():
        print("   (Node.js not found: using the existing build of the interface.)")
        return "ready (existing build)"
    sys.exit("  ✗ Node.js is needed to build the interface from source.\n"
             "    Install Node.js 18 or newer from https://nodejs.org, then run this again.\n"
             "    (Release downloads include the interface prebuilt and don't need it.)")


def _first_run_hint() -> str:
    hint = "A window opens and you're ready: no account, no sign-up, no limits."
    return hint


def _safe_console() -> None:
    """Windows consoles often use a legacy code page that can't show characters
    like ✅ or …; replace those instead of crashing the installer."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):
                pass


def main() -> None:
    _safe_console()
    print("Scrawly installer\n=================")
    _ensure_modern_python()
    _need("git", "Install git (https://git-scm.com). It powers Scrawly's automatic updates.")

    print("\n[1/5] Creating Scrawly's private Python environment (.venv)…")
    if not _venv_bin("python").exists():
        venv.EnvBuilder(with_pip=True).create(str(VENV))
    py = _venv_bin("python")

    print("\n[2/5] Installing Scrawly and its window runtime…")
    _run([py, "-m", "pip", "install", "-q", "--upgrade", "pip"])
    _run([py, "-m", "pip", "install", "-q", "-e", ".[desktop]"])
    if sys.platform.startswith("linux") and os.environ.get("SCRAWLY_LINUX_GUI", "qt") == "qt":
        # The window needs a webview toolkit. Qt installs inside Scrawly's own
        # environment from pip, so no system packages are required.
        _run([py, "-m", "pip", "install", "-q", "pywebview[qt]"])

    print("\n[3/5] Installing the crawler browser (one-time download, about 150 MB)…")
    _run([py, "-m", "playwright", "install", "chromium"])

    print("\n[4/5] Preparing the user interface…")
    ui_state = _prepare_ui()
    print(f"   interface {ui_state}")

    print("\n[5/5] Creating the launcher…")
    # A self-repair run comes from inside the launcher: don't rewrite it then.
    repairing = os.environ.get("SCRAWLY_SKIP_LAUNCHER") == "1"
    launcher = "your existing launcher" if repairing else _make_launcher()
    entry = ""
    if not repairing and os.environ.get("SCRAWLY_NO_SHORTCUTS") != "1":
        try:
            entry = _make_app_entry()
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"   (Couldn't add Scrawly to your apps: {exc}. The launcher above still works.)")

    print("\n✅ Scrawly is installed.\n")
    print("Open Scrawly:")
    if entry:
        print(f"   • {entry}")
    print(f"   • {launcher}")
    print(f"   • or run:  {_venv_bin('scrawly')}\n")
    print(_first_run_hint())
    print("Scrawly updates itself automatically when a new version is released.")
    if sys.platform.startswith("linux"):
        print("\nLinux note: if the window doesn't open, see docs/DESKTOP.md (Linux).")


def _make_launcher() -> str:
    """Write a launcher that (a) self-heals a venv broken by a Python upgrade
    (common on macOS when `brew upgrade python` removes the version the venv was
    built against) and (b) tees output to a log file so problems are diagnosable."""
    scrawly = _venv_bin("scrawly")
    vpy = _venv_bin("python")
    if IS_WIN:
        p = ROOT / "Scrawly.bat"
        p.write_text(
            "@echo off\r\n"
            f'cd /d "{ROOT}"\r\n'
            f'"{vpy}" -c "import sys" >nul 2>&1\r\n'
            "if errorlevel 1 (\r\n"
            "  echo Repairing Scrawly after a Python change...\r\n"
            f'  rmdir /s /q "{ROOT}\\.venv"\r\n'
            "  set SCRAWLY_SKIP_LAUNCHER=1\r\n"
            "  (py scripts\\install.py) || (python scripts\\install.py)\r\n"
            ")\r\n"
            f'"{scrawly}"\r\n', encoding="utf-8")
        return f"double-click  {p.name}  (in the Scrawly folder)"
    # macOS + Linux share a bash launcher; only the log directory differs.
    if IS_MAC:
        log_dir, name, where = ('"$HOME/Library/Application Support/Scrawly"',
                                "Scrawly.command", "double-click  Scrawly.command  (in the Scrawly folder)")
    else:
        log_dir, name, where = ('"${XDG_DATA_HOME:-$HOME/.local/share}/scrawly"',
                                "scrawly.sh", "run  ./scrawly.sh  (in the Scrawly folder)")
    p = ROOT / name
    # The whole run lives inside a { ... } group so bash parses it fully before
    # executing: the self-heal may rewrite deps, but never the script mid-read.
    p.write_text(
        "#!/bin/bash\n"
        f'cd "{ROOT}" || exit 1\n'
        f'LOG_DIR={log_dir}; mkdir -p "$LOG_DIR"; LOG="$LOG_DIR/scrawly.log"\n'
        '[ -f "$LOG" ] && [ "$(wc -c < "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ] '
        '&& mv -f "$LOG" "$LOG.1"\n'
        "{\n"
        '  echo "=== Scrawly launch $(date) ==="\n'
        f'  if ! "{vpy}" -c "import sys" >/dev/null 2>&1; then\n'
        '    echo "[scrawly] Python environment broken (upgraded/moved?) - rebuilding..."\n'
        f'    rm -rf "{ROOT}/.venv"\n'
        f'    SCRAWLY_SKIP_LAUNCHER=1 python3 "{ROOT}/scripts/install.py" '
        '|| { echo "[scrawly] repair failed - run: python3 scripts/install.py"; exit 1; }\n'
        "  fi\n"
        f'  exec "{scrawly}"\n'
        '} 2>&1 | tee -a "$LOG"\n', encoding="utf-8")
    os.chmod(p, 0o755)
    return where


# --- "Add to my apps" -----------------------------------------------------------
def _make_app_entry() -> str:
    if IS_MAC:
        return _mac_app()
    if IS_WIN:
        return _windows_shortcuts()
    return _linux_desktop_entry()


def _mac_app() -> str:
    """A real Scrawly.app in ~/Applications (Launchpad, Spotlight, the Dock). It
    starts the launcher in the background, so no Terminal window appears."""
    osacompile = shutil.which("osacompile")
    if not osacompile:
        return ""
    apps = Path.home() / "Applications"
    apps.mkdir(exist_ok=True)
    app = apps / "Scrawly.app"
    if app.exists():
        shutil.rmtree(app)
    command = ROOT / "Scrawly.command"
    script = f'do shell script "nohup " & quoted form of "{command}" & " >/dev/null 2>&1 &"'
    subprocess.run([osacompile, "-o", str(app), "-e", script], check=True,
                   capture_output=True, text=True)
    icns = ICONS / "scrawly.icns"
    if icns.exists():
        res = app / "Contents" / "Resources"
        shutil.copyfile(icns, res / "applet.icns")
        # Newer macOS prefers the compiled asset catalog's icon; drop it so the
        # Scrawly icon is used, then re-seal the bundle (ad-hoc signature).
        (res / "Assets.car").unlink(missing_ok=True)
        subprocess.run(["/usr/bin/plutil", "-remove", "CFBundleIconName",
                        str(app / "Contents" / "Info.plist")], capture_output=True)
        subprocess.run(["/usr/bin/codesign", "--force", "--deep", "--sign", "-", str(app)],
                       capture_output=True)
        os.utime(app, None)
    return "open  Scrawly  from Launchpad, Spotlight or ~/Applications"


def _windows_shortcuts() -> str:
    """Start Menu + Desktop shortcuts (the console window starts minimized)."""
    def q(path: Path) -> str:   # PowerShell single-quoted string
        return "'" + str(path).replace("'", "''") + "'"

    bat = ROOT / "Scrawly.bat"
    ico = ICONS / "scrawly.ico"
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        "foreach ($dir in @([Environment]::GetFolderPath('Programs'), "
        "[Environment]::GetFolderPath('Desktop'))) { "
        "$s = $ws.CreateShortcut((Join-Path $dir 'Scrawly.lnk')); "
        f"$s.TargetPath = {q(bat)}; $s.WorkingDirectory = {q(ROOT)}; "
        f"$s.IconLocation = {q(ico)}; $s.WindowStyle = 7; "
        "$s.Description = 'Scrawly: free SEO and GEO site audit'; $s.Save() }"
    )
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        return ""
    subprocess.run([exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                   check=True, capture_output=True, text=True)
    return "open  Scrawly  from the Start Menu or the Desktop shortcut"


def _linux_desktop_entry() -> str:
    apps = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    entry = apps / "scrawly.desktop"
    entry.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Scrawly\n"
        "GenericName=SEO Site Audit\n"
        "Comment=Free, open-source technical SEO and GEO crawler\n"
        f'Exec="{ROOT / "scrawly.sh"}"\n'
        f"Icon={ICONS / 'scrawly.png'}\n"
        "Terminal=false\n"
        "Categories=Network;WebDevelopment;Development;\n"
        "Keywords=SEO;crawler;audit;GEO;website;\n", encoding="utf-8")
    os.chmod(entry, 0o755)
    return "open  Scrawly  from your applications menu"


if __name__ == "__main__":
    main()
