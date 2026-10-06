"""Spelling & grammar (SF Pattern I).

Two backends, because LanguageTool's local engine needs a JRE that most machines
don't have:

  * ``public`` (default) — LanguageTool's free hosted API. No Java, no key, but
    rate-limited (~20 req/min) and **it sends page text to languagetool.org**, so
    it's off by default and flagged in the UI.
  * ``local``  — a JRE-backed LanguageTool. Nothing leaves the machine and there's
    no rate limit; requires ``java`` on PATH (auto-detected).

Runs over the *content-area* text (same input as duplicates/embeddings), so nav
and footer boilerplate don't generate thousands of false hits. Language comes from
``<html lang>`` unless overridden.
"""
from __future__ import annotations

import functools
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional

# LanguageTool wants a locale; map bare codes onto its defaults.
_LANG_DEFAULTS = {
    "en": "en-US", "de": "de-DE", "pt": "pt-PT", "fa": "fa-IR",
    "es": "es", "fr": "fr", "it": "it", "nl": "nl", "pl": "pl", "ru": "ru",
}


@functools.lru_cache(maxsize=1)
def java_available() -> bool:
    """A real, runnable JRE — not just a `java` on PATH.

    macOS ships a /usr/bin/java *stub* that exists (so shutil.which finds it) but
    exits non-zero with "Unable to locate a Java Runtime" when no JDK is
    installed. Trusting `which` here silently selects local mode, which then
    fails and returns zero spelling issues — worse than saying so up front.
    """
    if shutil.which("java") is None:
        return False
    try:
        proc = subprocess.run(
            ["java", "-version"], capture_output=True, timeout=15, check=False
        )
        return proc.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def backend_available(probe: bool = False) -> Dict[str, Any]:
    """What the Settings UI needs to explain the choice.

    `probe=True` actually calls the backend — the free public API is rate-limited
    (~20 req/min) and will refuse mid-crawl, so the UI should be able to show that
    truthfully rather than presenting a toggle that quietly does nothing.
    """
    try:
        import language_tool_python  # noqa: F401
        installed = True
    except Exception:  # noqa: BLE001
        installed = False
    has_java = java_available()
    out: Dict[str, Any] = {
        "installed": installed,
        "local_available": installed and has_java,
        "public_available": installed,
        "mode": "local" if (installed and has_java) else ("public" if installed else "none"),
        "note": "" if has_java else (
            "No Java runtime found — local mode unavailable. The free public API is "
            "rate-limited (~20 req/min) and sends page text to languagetool.org. "
            "Install a JRE (e.g. `brew install openjdk`) for unlimited local checking."
        ),
    }
    if probe and installed:
        try:
            check_text("A quick test of the speling backend.", mode=out["mode"])
            out["probe_ok"] = True
        except SpellingBackendError as e:
            out["probe_ok"] = False
            out["probe_error"] = str(e)
    return out


# Script subtags LanguageTool expresses as a region (e.g. zh-Hans → zh-CN).
_SCRIPT_TO_LOCALE = {"hans": "zh-CN", "hant": "zh-TW"}


def normalize_language(lang: Optional[str], override: str = "auto") -> str:
    """Resolve a checking locale from <html lang> or an explicit override.

    LanguageTool locales are case-sensitive — 'en-GB' works, 'en-gb' 404s — so
    normalize to lowercase-language / UPPERCASE-region. The override path runs
    through the SAME normalization (a user typing 'en_gb' or 'en-gb' shouldn't
    silently 404 and yield zero issues).
    """
    code = (override if (override and override != "auto") else (lang or "en"))
    code = code.strip().replace("_", "-")
    if not code:
        return "en-US"
    if "-" in code:                     # locale or lang-script, e.g. en-gb / zh-Hans
        base, _, tail = code.partition("-")
        if tail.lower() in _SCRIPT_TO_LOCALE:
            return _SCRIPT_TO_LOCALE[tail.lower()]
        return f"{base.lower()}-{tail.upper()}"
    return _LANG_DEFAULTS.get(code.lower(), code.lower())


@functools.lru_cache(maxsize=8)
def _tool(language: str, mode: str) -> Any:
    import language_tool_python

    if mode == "local" and java_available():
        return language_tool_python.LanguageTool(language)
    return language_tool_python.LanguageToolPublicAPI(language)


class SpellingBackendError(RuntimeError):
    """The backend failed (rate limit, no JRE, network). Distinct from 'clean text'.

    This exists because swallowing the failure and returning [] is indistinguishable
    from "no mistakes found" — which silently reports a misspelled site as perfect.
    The caller is expected to stop and surface it, not retry 500 more times.
    """


def check_text(
    text: str,
    language: str = "en-US",
    mode: str = "public",
    ignore: Optional[List[str]] = None,
    max_chars: int = 18_000,
) -> List[Dict[str, Any]]:
    """Spelling/grammar issues in `text`.

    Raises SpellingBackendError if the backend itself failed — an empty list here
    means "checked, nothing wrong", never "couldn't check".
    """
    body = (text or "").strip()
    if not body:
        return []
    body = body[:max_chars]             # the public API rejects large payloads
    ignore_set = {w.strip().lower() for w in (ignore or []) if w.strip()}
    try:
        matches = _tool(language, mode).check(body)
    except Exception as e:  # noqa: BLE001
        raise SpellingBackendError(f"{type(e).__name__}: {str(e)[:180]}") from e

    out: List[Dict[str, Any]] = []
    for m in matches:
        word = str(getattr(m, "matchedText", "") or body[m.offset:m.offset + m.errorLength])
        if word.lower() in ignore_set:
            continue
        rule = getattr(m, "ruleId", "") or ""
        out.append({
            "message": str(getattr(m, "message", ""))[:180],
            "word": word[:60],
            "rule": rule,
            "kind": "spelling" if "SPELL" in rule.upper() or "MORFOLOGIK" in rule.upper() else "grammar",
            "suggestions": [str(r) for r in (getattr(m, "replacements", []) or [])[:3]],
            "context": str(getattr(m, "context", ""))[:120],
        })
    return out


_WORD_RE = re.compile(r"\b[\w'-]+\b")


def summarize(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "total": len(issues),
        "spelling": sum(1 for i in issues if i["kind"] == "spelling"),
        "grammar": sum(1 for i in issues if i["kind"] == "grammar"),
    }
