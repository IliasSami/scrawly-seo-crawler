"""Universal Google OAuth 2.0 — one consent, both Search Console and GA4.

Why OAuth and not the service account: a service account only sees properties an
admin has explicitly granted it. OAuth lets any user connect *their own* GSC
properties and GA4 accounts in one click, which is what a multi-client tool needs.
The service-account path stays as a fallback for headless/CI use.

Tokens are encrypted at rest with SCRAWLY_ENCRYPTION_KEY (Invariant I5) and the
refresh token is never returned by the API — only whether one exists.
"""
from __future__ import annotations

import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Any, Optional

# GSC read + GA4 read + identity (so the UI can show which account is connected).
SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

_CLIENT_ENV = "SCRAWLY_GOOGLE_OAUTH_CLIENT"
_TOKEN_ENV = "SCRAWLY_GOOGLE_OAUTH_TOKEN"
_DEFAULT_CLIENT = "secrets/google_oauth_client.json"
_DEFAULT_TOKEN = "secrets/google_oauth_token.enc"


def client_path() -> Path:
    return Path(os.environ.get(_CLIENT_ENV) or _DEFAULT_CLIENT)


def token_path() -> Path:
    return Path(os.environ.get(_TOKEN_ENV) or _DEFAULT_TOKEN)


def client_configured() -> bool:
    return client_path().exists()


def _client_config() -> dict[str, Any]:
    with open(client_path()) as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def redirect_uri() -> str:
    cfg = _client_config()
    node = cfg.get("web") or cfg.get("installed") or {}
    uris = node.get("redirect_uris") or []
    return str(uris[0]) if uris else "http://localhost:8000/api/oauth/google/callback"


def _fernet() -> Any:
    from cryptography.fernet import Fernet

    key = os.environ.get("SCRAWLY_ENCRYPTION_KEY")
    if not key:
        raise ValueError("SCRAWLY_ENCRYPTION_KEY is not set — cannot store OAuth tokens.")
    return Fernet(key.encode())


# Per-flow CSRF nonce for the OAuth handshake (module-global — single worker,
# flow completes in seconds). Prevents a login-CSRF that would connect the
# operator's Scrawly to an attacker's Google account.
_pending_state: Optional[str] = None


def new_state() -> str:
    global _pending_state
    _pending_state = secrets.token_urlsafe(24)
    return _pending_state


def _state_ok(state: str) -> bool:
    # No pending state (e.g. server restarted mid-flow) → accept, to avoid locking
    # the user out; otherwise require a constant-time match.
    return _pending_state is None or hmac.compare_digest(state or "", _pending_state)


def _save_token(data: dict[str, Any]) -> None:
    p = token_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(p.parent, 0o700)
    except OSError:
        pass
    blob = _fernet().encrypt(json.dumps(data).encode())
    # Create with 0o600 from the start — never a world-readable window before chmod.
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, blob)
    finally:
        os.close(fd)


def _load_token() -> Optional[dict[str, Any]]:
    p = token_path()
    if not p.exists():
        return None
    try:
        out: dict[str, Any] = json.loads(_fernet().decrypt(p.read_bytes()).decode())
        return out
    except Exception:  # noqa: BLE001 - corrupt/undecryptable token behaves as "not connected"
        return None


def auth_url(state: Optional[str] = None) -> str:
    """The Google consent URL to send the user to (with a fresh CSRF state)."""
    from google_auth_oauthlib.flow import Flow  # type: ignore[import-untyped]

    st = state or new_state()
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=st)
    flow.redirect_uri = redirect_uri()
    url, _ = flow.authorization_url(
        access_type="offline",        # we need a refresh token
        include_granted_scopes="true",
        prompt="consent",             # force a refresh token even on re-connect
    )
    return str(url)


def exchange_code(code: str, state: str = "") -> dict[str, Any]:
    """Swap the callback code for tokens and persist them (encrypted).
    Rejects a mismatched CSRF state so a forged callback can't connect us to
    someone else's Google account."""
    if not _state_ok(state):
        raise ValueError("OAuth state mismatch — the sign-in didn't originate here.")
    global _pending_state
    _pending_state = None            # single-use

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state or None)
    flow.redirect_uri = redirect_uri()
    flow.fetch_token(code=code)
    c = flow.credentials
    data = {
        "token": c.token,
        "refresh_token": c.refresh_token,
        "token_uri": c.token_uri,
        "client_id": c.client_id,
        "client_secret": c.client_secret,
        "scopes": list(c.scopes or []),
        "expiry": c.expiry.isoformat() if c.expiry else None,
    }
    _save_token(data)
    return {"connected": True, "scopes": data["scopes"]}


def load_credentials() -> Any:
    """Stored credentials, refreshed if expired. None when not connected."""
    data = _load_token()
    if not data:
        return None
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=data.get("scopes"),
        )
        if not creds.valid and creds.refresh_token:
            creds.refresh(Request())
            data["token"] = creds.token
            data["expiry"] = creds.expiry.isoformat() if creds.expiry else None
            _save_token(data)   # persist the rotated access token
        return creds
    except Exception:  # noqa: BLE001
        return None


def status() -> dict[str, Any]:
    """Connection state for the UI. Never returns the tokens themselves."""
    data = _load_token()
    if not data:
        return {
            "connected": False,
            "client_configured": client_configured(),
            "redirect_uri": redirect_uri() if client_configured() else "",
        }
    email = ""
    try:
        creds = load_credentials()
        if creds:
            import httpx

            r = httpx.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {creds.token}"}, timeout=10,
            )
            if r.status_code == 200:
                email = str(r.json().get("email", ""))
    except Exception:  # noqa: BLE001 - identity is cosmetic
        pass
    return {
        "connected": True,
        "client_configured": True,
        "email": email,
        "scopes": data.get("scopes", []),
        "has_refresh_token": bool(data.get("refresh_token")),
    }


def disconnect() -> dict[str, Any]:
    """Revoke with Google (best-effort) then delete the local token."""
    data = _load_token()
    if data and data.get("token"):
        try:
            import httpx

            httpx.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": data["token"]},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
        except Exception:  # noqa: BLE001
            pass
    p = token_path()
    if p.exists():
        p.unlink()
    return {"connected": False}


def list_gsc_sites() -> list[str]:
    creds = load_credentials()
    if not creds:
        return []
    try:
        from googleapiclient.discovery import build  # type: ignore[import-untyped]

        svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        sites = svc.sites().list().execute()
        return [s["siteUrl"] for s in sites.get("siteEntry", [])]
    except Exception:  # noqa: BLE001
        return []


def list_ga4_properties() -> list[dict[str, str]]:
    """GA4 accounts → properties the connected user can read."""
    creds = load_credentials()
    if not creds:
        return []
    out: list[dict[str, str]] = []
    try:
        from googleapiclient.discovery import build

        admin = build("analyticsadmin", "v1beta", credentials=creds, cache_discovery=False)
        summaries = admin.accountSummaries().list(pageSize=200).execute()
        for acc in summaries.get("accountSummaries", []):
            for prop in acc.get("propertySummaries", []):
                out.append({
                    # "properties/123456789" -> "123456789"
                    "property_id": str(prop.get("property", "")).split("/")[-1],
                    "display_name": prop.get("displayName", ""),
                    "account": acc.get("displayName", ""),
                })
    except Exception:  # noqa: BLE001
        return out
    return out
