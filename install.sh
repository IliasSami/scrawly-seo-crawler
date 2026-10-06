#!/usr/bin/env bash
# Scrawly one-line installer for macOS and Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/IliasSami/scrawly-seo-crawler/main/install.sh | bash
#
# Checks for git and Python 3.11+, downloads Scrawly into ~/Scrawly (or
# $SCRAWLY_HOME), and runs its installer, which adds Scrawly to your apps.
# Re-running it updates an existing install.
set -euo pipefail

REPO="${SCRAWLY_REPO:-https://github.com/IliasSami/scrawly-seo-crawler.git}"
DEST="${SCRAWLY_HOME:-$HOME/Scrawly}"
OS="$(uname -s)"

say()  { printf '%s\n' "$*"; }
fail() { printf '\n✗ %s\n' "$*" >&2; exit 1; }

say "Scrawly installer"
say "================="
say "Installing into: $DEST"

# --- git ------------------------------------------------------------------------
if ! command -v git >/dev/null 2>&1; then
  if [ "$OS" = "Darwin" ]; then
    xcode-select --install >/dev/null 2>&1 || true
    fail "git is needed. macOS is now offering to install the Command Line Tools; when that finishes, run this command again."
  fi
  fail "git is needed. Install it with your package manager (for example: sudo apt install git), then run this again."
fi

# --- Python 3.11+ ---------------------------------------------------------------
find_python() {
  for c in python3.13 python3.12 python3.11 python3; do
    if command -v "$c" >/dev/null 2>&1 &&
       "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      command -v "$c"; return 0
    fi
  done
  return 1
}

PY="$(find_python || true)"
if [ -z "$PY" ]; then
  if [ "$OS" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
    say "Installing Python 3.12 with Homebrew…"
    brew install python@3.12
    PY="$(find_python || true)"
  fi
fi
if [ -z "$PY" ]; then
  if [ "$OS" = "Darwin" ]; then
    fail "Python 3.11 or newer is needed. Install it from https://www.python.org/downloads/macos/ (or with Homebrew: brew install python@3.12), then run this again."
  fi
  fail "Python 3.11 or newer is needed. For example: sudo apt install python3.12 python3.12-venv (Debian/Ubuntu) or sudo dnf install python3.12 (Fedora), then run this again."
fi
if ! "$PY" -c 'import venv, ensurepip' >/dev/null 2>&1; then
  fail "Python's venv module is missing. On Debian/Ubuntu: sudo apt install python3-venv (or python3.12-venv), then run this again."
fi
say "Using $("$PY" --version) at $PY"

# --- download or update -----------------------------------------------------------
if [ -d "$DEST/.git" ]; then
  say "Updating the existing copy…"
  git -C "$DEST" pull --ff-only || say "(Couldn't update automatically; continuing with the current copy.)"
elif [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
  fail "$DEST already exists and isn't a Scrawly folder. Choose another folder with: SCRAWLY_HOME=/path/to/folder"
else
  say "Downloading Scrawly…"
  git clone "$REPO" "$DEST"
fi

# --- install ----------------------------------------------------------------------
cd "$DEST"
"$PY" scripts/install.py
