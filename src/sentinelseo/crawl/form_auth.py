"""Web-form authentication (SF §12).

Logs in through a real browser once, then hands the resulting session cookies to
the crawler so gated pages return content instead of a login redirect.

Safety, deliberately: credentials are read **only** from the environment — never
a config profile, never the API, never git (Invariant I5) — and the crawler is
pointed away from destructive links. SF's own warning applies and is the reason
for the `_DANGEROUS` exclusions below: an authenticated crawler clicks *every*
link, including logout, delete and admin actions. Use a scoped throwaway account.

    SCRAWLY_FORM_LOGIN_URL=https://example.com/wp-login.php
    SCRAWLY_FORM_USER=...
    SCRAWLY_FORM_PASS=...
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

# Links an authenticated crawler must never follow — clicking these while logged
# in ends the session or mutates the site. CMS-agnostic and matched
# case-insensitively (see fetcher.py, which compiles these with re.IGNORECASE).
# A denylist can never be exhaustive — the real guarantee is a scoped throwaway
# account (see module docstring); this just removes the obvious footguns.
DANGEROUS_PATTERNS = [
    r"/wp-admin\b", r"/administrator\b", r"/user/logout",
    # logout/signout as a whole path SEGMENT, not a substring — so /logout and
    # /logout/ match but a content URL like /logout-tips does not.
    r"/log-?out(?![\w-])", r"/sign-?out(?![\w-])",
    r"[?&]_wpnonce=", r"[?&]logout=",
    r"[?&](action|do|task|op|cmd|method)=(logout|signout|sign-out|delete|trash|remove|destroy|unpublish)",
    r"/node/\d+/delete",
]

# Field-name candidates, in order — covers WordPress plus common CMS logins.
_USER_FIELDS = ["#user_login", "input[name=log]", "input[name=username]",
                "input[name=email]", "input[type=email]", "input[name=user]"]
_PASS_FIELDS = ["#user_pass", "input[name=pwd]", "input[name=password]", "input[type=password]"]
_SUBMIT = ["#wp-submit", "button[type=submit]", "input[type=submit]"]


def form_config() -> Dict[str, str]:
    return {
        "login_url": (os.environ.get("SCRAWLY_FORM_LOGIN_URL") or "").strip(),
        "user": (os.environ.get("SCRAWLY_FORM_USER") or "").strip(),
        "password": (os.environ.get("SCRAWLY_FORM_PASS") or "").strip(),
    }


def is_configured(cfg: Optional[Dict[str, str]] = None) -> bool:
    c = cfg or form_config()
    return bool(c.get("login_url") and c.get("user") and c.get("password"))


def status() -> Dict[str, Any]:
    """For the UI. Reports *whether* creds exist — never what they are."""
    c = form_config()
    return {
        "configured": is_configured(c),
        "login_url": c["login_url"],
        "user": c["user"],                       # a username is not a secret
        "password_set": bool(c["password"]),     # the password never leaves .env
        "note": "Credentials are read from the environment only. Use a scoped "
                "test account — an authenticated crawl follows every link.",
    }


async def _fill_first(page: Any, selectors: List[str], value: str) -> bool:
    for sel in selectors:
        try:
            if await page.locator(sel).count():
                await page.fill(sel, value)
                return True
        except Exception:  # noqa: BLE001 - try the next candidate
            continue
    return False


async def login_and_get_cookies(
    browser: Any, cfg: Optional[Dict[str, str]] = None, timeout_ms: int = 30_000
) -> List[Dict[str, Any]]:
    """Drive the login form in a real browser; return the session cookies.
    Any failure yields [] — the crawl then simply runs unauthenticated."""
    c = cfg or form_config()
    if not is_configured(c):
        return []
    ctx = None
    try:
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto(c["login_url"], timeout=timeout_ms, wait_until="domcontentloaded")
        if not await _fill_first(page, _USER_FIELDS, c["user"]):
            return []
        if not await _fill_first(page, _PASS_FIELDS, c["password"]):
            return []
        for sel in _SUBMIT:
            try:
                if await page.locator(sel).count():
                    await page.click(sel)
                    break
            except Exception:  # noqa: BLE001
                continue
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:  # noqa: BLE001 - some sites never go idle; cookies may still be set
            pass
        cookies: List[Dict[str, Any]] = await ctx.cookies()
        return cookies
    except Exception:  # noqa: BLE001
        return []
    finally:
        if ctx:
            try:
                await ctx.close()
            except Exception:  # noqa: BLE001
                pass


def cookies_to_header(cookies: List[Dict[str, Any]]) -> str:
    """Fold Playwright cookies into a Cookie header for the httpx crawler."""
    parts = [f"{c.get('name')}={c.get('value')}" for c in cookies if c.get("name")]
    return "; ".join(parts)


def looks_authenticated(cookies: List[Dict[str, Any]]) -> bool:
    """WordPress sets wordpress_logged_in_*; otherwise accept any session cookie."""
    names = [str(c.get("name", "")) for c in cookies]
    if any(n.startswith("wordpress_logged_in_") for n in names):
        return True
    return any("session" in n.lower() or n.lower() in ("sid", "phpsessid") for n in names)
