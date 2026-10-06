"""Backlink metrics (SF Pattern L) — bring your own subscription.

There is no free backlink API worth shipping: Majestic, Ahrefs and Moz each
require the user's own paid plan, and Ahrefs v3 only issues tokens through its
OAuth app (a raw key won't work). So Scrawly ships the *connection surface*, not
a credential — the operator supplies their own and Scrawly verifies it live.

Credentials are read from the environment (Invariant I5) and never persisted in
the profile or returned by the API:

    SCRAWLY_MOZ_ACCESS_ID / SCRAWLY_MOZ_SECRET_KEY
    SCRAWLY_AHREFS_TOKEN
    SCRAWLY_MAJESTIC_KEY
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

PROVIDERS: Dict[str, Dict[str, Any]] = {
    "moz": {
        "label": "Moz Links API",
        "env": ["SCRAWLY_MOZ_ACCESS_ID", "SCRAWLY_MOZ_SECRET_KEY"],
        "signup": "https://moz.com/products/api/pricing",
        "note": "Access ID + Secret Key from your Moz API account (paid plan).",
    },
    "ahrefs": {
        "label": "Ahrefs",
        "env": ["SCRAWLY_AHREFS_TOKEN"],
        "signup": "https://ahrefs.com/api",
        "note": "API token from Ahrefs (subscription; consumes API units).",
    },
    "majestic": {
        "label": "Majestic",
        "env": ["SCRAWLY_MAJESTIC_KEY"],
        "signup": "https://developer-support.majestic.com/api/",
        "note": "OpenApps API key from your Majestic subscription.",
    },
}


def _creds(provider: str, settings: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    # ENV ONLY. These are secrets — reading them from the persisted, user-editable
    # settings dict would both let PUT /api/settings inject them and cause
    # GET /api/settings to echo them in cleartext (I5). `settings` is ignored.
    out: Dict[str, str] = {}
    for key in PROVIDERS.get(provider, {}).get("env", []):
        out[key] = str(os.environ.get(key) or "").strip()
    return out


def is_connected(provider: str, settings: Optional[Dict[str, Any]] = None) -> bool:
    c = _creds(provider, settings)
    return bool(c) and all(c.values())


def providers_status(settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """What the Settings UI renders: each provider, connected or not, + how to get it."""
    out: Dict[str, Any] = {"providers": [], "any_connected": False}
    for key, meta in PROVIDERS.items():
        connected = is_connected(key, settings)
        out["any_connected"] = out["any_connected"] or connected
        out["providers"].append({
            "id": key,
            "label": meta["label"],
            "connected": connected,
            "env": meta["env"],          # names only — never the values
            "signup": meta["signup"],
            "note": meta["note"],
        })
    return out


def test_provider(provider: str, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Live credential check against the provider's cheapest endpoint."""
    if provider not in PROVIDERS:
        return {"ok": False, "detail": f"Unknown provider '{provider}'."}
    if not is_connected(provider, settings):
        need = ", ".join(PROVIDERS[provider]["env"])
        return {"ok": False, "detail": f"Not connected — set {need} in your environment."}

    import httpx

    c = _creds(provider, settings)
    try:
        if provider == "moz":
            r = httpx.post(
                "https://lsapi.seomoz.com/v2/url_metrics",
                auth=(c["SCRAWLY_MOZ_ACCESS_ID"], c["SCRAWLY_MOZ_SECRET_KEY"]),
                json={"targets": ["moz.com"]}, timeout=20,
            )
        elif provider == "ahrefs":
            r = httpx.get(
                "https://api.ahrefs.com/v3/site-explorer/domain-rating",
                headers={"Authorization": f"Bearer {c['SCRAWLY_AHREFS_TOKEN']}"},
                params={"target": "ahrefs.com", "date": "2024-01-01"}, timeout=20,
            )
        else:  # majestic
            r = httpx.get(
                "https://api.majestic.com/api/json",
                params={"app_api_key": c["SCRAWLY_MAJESTIC_KEY"],
                        "cmd": "GetIndexItemInfo", "items": "1", "item0": "majestic.com"},
                timeout=20,
            )
        if r.status_code == 200:
            return {"ok": True, "provider": provider, "detail": "Credential accepted."}
        return {"ok": False, "detail": f"{provider} returned HTTP {r.status_code}: {r.text[:160]}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": f"{type(e).__name__}: {str(e)[:160]}"}


def fetch_metrics(
    provider: str, targets: List[str], settings: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Backlink metrics keyed by target URL. Empty when not connected.
    Only Moz is implemented (its API is documented + testable without OAuth);
    Ahrefs/Majestic report as connected-but-unimplemented rather than silently
    returning nothing."""
    if not is_connected(provider, settings) or not targets:
        return {}
    import httpx

    c = _creds(provider, settings)
    if provider != "moz":
        return {"_error": f"{provider} metric fetching is not implemented yet."}
    try:
        r = httpx.post(
            "https://lsapi.seomoz.com/v2/url_metrics",
            auth=(c["SCRAWLY_MOZ_ACCESS_ID"], c["SCRAWLY_MOZ_SECRET_KEY"]),
            json={"targets": targets[:50]}, timeout=30,
        )
        if r.status_code != 200:
            return {"_error": f"HTTP {r.status_code}: {r.text[:160]}"}
        out: Dict[str, Any] = {}
        for row in r.json().get("results", []):
            out[row.get("page", "")] = {
                "domain_authority": row.get("domain_authority"),
                "page_authority": row.get("page_authority"),
                "linking_domains": row.get("root_domains_to_page"),
                "spam_score": row.get("spam_score"),
            }
        return out
    except Exception as e:  # noqa: BLE001
        return {"_error": f"{type(e).__name__}: {str(e)[:160]}"}
