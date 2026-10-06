import asyncio
import html
import json
import os
import re
from typing import Any

import httpx
import structlog
from dotenv import load_dotenv

load_dotenv()  # pick up .env (PSI key, GSC creds, WP fix credentials)
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse

from sentinelseo import edition
from sentinelseo.audit.context import SiteContext
from sentinelseo.audit.runner import run_audit
from sentinelseo.checks import load_all_checks
from sentinelseo.checks.registry import CrawlContext
from sentinelseo.checks.site_level.registry import get_site_level_checks
from sentinelseo.crawl.fetcher import Crawler
from sentinelseo.db.migrate import run_migrations
from sentinelseo.db.models import (
    URL,
    Client,
    ConfigProfile,
    Crawl,
    Fix,
    Issue,
    Resource,
)
from sentinelseo.db.session import (
    SessionLocal,
    current_owner,
    engine,
    set_current_owner,
)
from sentinelseo.web import crawl_gate

app = FastAPI(title="Scrawly Execution Hub API")


class _OwnerScopeMiddleware:
    """Route each request's database work to the caller's workspace.

    The signed-in UI sends its workspace id in `X-Scrawly-Owner`; this binds the
    request (and every SessionLocal() it opens) to that workspace's own database,
    so a user's clients, crawls and audits are never visible to anyone else. A
    missing header (the anonymous public-audit window) falls back to the shared
    base DB. Runs as pure ASGI middleware so the ContextVar it sets is visible to
    the sync endpoints executed on the threadpool.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            owner = ""
            for key, value in scope.get("headers", []):
                if key == b"x-scrawly-owner":
                    owner = value.decode("latin-1")
                    break
            set_current_owner(owner)
        await self.app(scope, receive, send)


app.add_middleware(_OwnerScopeMiddleware)

log = structlog.get_logger(__name__)


# --- crawl gate ---------------------------------------------------------------
# Edition-specific (web/crawl_gate.py). Wrapped here so call sites stay unchanged.
# Upper bound for one quick audit in the Free edition (a sanity limit, not a quota).
PUBLIC_AUDIT_MAX_PAGES_FREE = 100_000


def _require_crawl_authz(request: Request) -> Any:
    return crawl_gate.require_crawl_authz(request)


def _crawl_owner(claims: Any) -> str:
    """The workspace key the crawl's data must be written under: the signed one
    when enforced (unspoofable), else whatever the request context resolved."""
    if claims and claims.get("ws"):
        return f"ws{int(claims['ws'])}"
    return current_owner()

# --- local-only guard ---------------------------------------------------------
# The engine serves exactly one client: the Scrawly window on this machine (same
# origin; the Vite dev server proxies /api, so it is same-origin too). Any other
# website the user happens to visit must not be able to drive it: no CORS, a Host
# check against DNS rebinding, and an Origin check on every state-changing call.
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]", "testserver"})


def _allowed_hosts() -> frozenset[str]:
    extra = {h.strip().lower() for h in os.getenv("SCRAWLY_ALLOWED_HOSTS", "").split(",")
             if h.strip()}
    return _LOCAL_HOSTS | extra


def _host_of(value: str) -> str:
    """Host part of a Host header value (``127.0.0.1:8000``, ``[::1]:8000``)."""
    v = value.strip().lower()
    if v.startswith("["):
        end = v.find("]")
        return v[: end + 1] if end != -1 else v
    return v.split(":", 1)[0]


def _request_blocked(method: str, host_header: str, origin: str) -> bool:
    allowed = _allowed_hosts()
    if _host_of(host_header) not in allowed:
        return True
    if method in ("GET", "HEAD", "OPTIONS") or not origin:
        return False
    from urllib.parse import urlparse

    origin_host = (urlparse(origin).hostname or "").lower()   # "null" -> ""
    return origin_host not in allowed


class _LocalOnlyMiddleware:
    """Refuse requests that don't come from this machine's own app window."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            headers = dict(scope.get("headers") or [])
            host = headers.get(b"host", b"").decode("latin-1")
            origin = headers.get(b"origin", b"").decode("latin-1")
            if _request_blocked(str(scope.get("method", "GET")), host, origin):
                body = json.dumps({"detail": {
                    "code": "forbidden_origin",
                    "message": "This request didn't come from the Scrawly app."}}).encode()
                await send({"type": "http.response.start", "status": 403,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


# Optional cross-origin access for unusual dev setups (comma-separated origins).
_dev_origins = [o.strip() for o in os.getenv("SCRAWLY_DEV_CORS_ORIGINS", "").split(",")
                if o.strip()]
if _dev_origins:
    app.add_middleware(CORSMiddleware, allow_origins=_dev_origins,
                       allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(_LocalOnlyMiddleware)   # added last = runs first

# Reconcile the schema (adds missing columns) and register all checks at boot.
run_migrations(engine)
load_all_checks()

# Crawl-config keys carried by a ConfigProfile (WP connection is per-client, not
# part of a profile).
CRAWL_CONFIG_DEFAULTS: dict[str, Any] = {
    "user_agent": "ScrawlyBot/1.0",
    "concurrency": 8,
    "max_depth": 3,
    "max_pages": 500,
    "js_render": True,
    "respect_robots": True,
    "render_sample": 0,
    "include_patterns": "",
    "exclude_patterns": "",
    "psi_enrich": False,
    "gsc_enrich": False,
    # Crawl limits + speed cap (0 = unlimited).
    "max_requests_per_sec": 0,
    "max_url_length": 2000,
    "max_query_params": 0,
    "max_links_per_page": 0,
    "max_folder_depth": 0,
    "max_redirects": 5,
    "render_timeout_s": 15,  # AJAX timeout for JS render + on-demand screenshots
    # Sitemap handling.
    "discover_sitemap": True,   # find sitemap via robots.txt / common paths + seed it
    "sitemap_only": False,      # crawl ONLY sitemap URLs (don't follow links)
    # Custom extraction (site-wide scraper) — opt-in, empty by default.
    "custom_extractors": [],
    "custom_searches": [],
    # ---------- SF-parity config surface (Phase 1) ----------
    # [WIRED] = honored by the crawler now; [planned] = persisted, engine phase next.
    # Robots (Pattern G)
    "robots_mode": "respect",            # [WIRED] respect | ignore | ignore_but_report
    "robots_user_agent": "",             # [WIRED] UA matched against robots groups (blank = HTTP UA)
    # Scope booleans (surfaced in the UI as planned)
    "crawl_subdomains": False,           # [planned]
    "crawl_outside_start_folder": False,  # [planned]
    "follow_nofollow": False,            # [planned] force-follow rel=nofollow
    "crawl_fragment_identifiers": False,  # [WIRED] treat #hash as distinct URL
    # URL rewriting (Pattern F) — all [WIRED]
    "remove_parameters": "",             # comma-separated query keys to strip
    "regex_replace": [],                 # ordered [{pattern, replacement}]
    "lowercase_urls": False,
    # Limits (Pattern C) — added
    "max_urls_per_depth": 0,             # [WIRED]
    "max_per_subdomain": 0,              # [WIRED]
    "max_page_size_kb": 0,               # [planned] fetch guard
    "response_timeout_s": 20,            # [WIRED]
    # HTTP headers (§9) — [WIRED]
    "custom_headers": {},                # {name: value}
    # Resource crawl gates (Pattern A) — [planned] (crawler is pages-only today)
    "crawl_images": True, "crawl_css": True, "crawl_js": True, "crawl_media": True,
    "crawl_external": True, "crawl_hreflang": False, "crawl_amp": False,
    "crawl_pagination": False,
    # Extraction store flags (Pattern B) — [planned]
    "store_html": False, "store_rendered_html": False, "store_hash": True,
    "extract_structured_data": True, "extract_cookies": False, "extract_http_headers": True,
    "extract_pdf": True,
    # Rendering (Pattern D) — [planned] viewport/flatten
    "window_width": 1024, "window_height": 768,
    "flatten_shadow_dom": True, "flatten_iframes": True, "js_error_reporting": False,
    # Advanced — [planned]
    "ignore_non_indexable_issues": False, "respect_noindex": False,
    "respect_canonical": False, "html_validation": False, "assume_html": True,
    "extract_srcset": True,
    # CDNs (§5) — [planned]
    "cdns": "",
    # Content area (§2.1) — [planned]
    "content_include": "", "content_exclude": "",
    # Duplicates (Pattern H)
    "near_dup_threshold": 90, "ignore_paginated_dupes": True,
    # List mode (§17) — [WIRED] check exactly these URLs, no link discovery
    "list_mode": False, "list_urls": "",
    # Segments (Pattern N) — [WIRED] ordered [{name, pattern, color}], first match wins
    "segments": [],
    # GA4 (Pattern M) — [WIRED] needs the Google OAuth connection + a property id
    "ga4_enrich": False,
    "ga4_property_id": "",
    "ga4_days": 28,
    "ga4_fuzzy_match": True,   # try trailing-slash / lowercase variants when matching
    # Spelling & grammar (Pattern I) — [WIRED] when language-tool is installed
    "spelling_enrich": False,
    "spelling_language": "auto",   # auto = from <html lang>, else e.g. en-US
    "spelling_ignore": "",         # comma-separated words to ignore
    # Embeddings (Pattern J) — [WIRED] when an embeddings provider is configured
    "embeddings_enrich": False,
    "embeddings_similarity_threshold": 0.92,
    # Web-form auth (§12) — [WIRED]; credentials come from env only, never here.
    "form_auth": False,
}

# Config keys the crawler engine actually honors today (Phase 1). Everything else
# in CRAWL_CONFIG_DEFAULTS is persisted with the profile and consumed by later phases.
_ENGINE_WIRED_KEYS = frozenset({
    "robots_mode", "robots_user_agent", "crawl_fragment_identifiers",
    "remove_parameters", "regex_replace", "lowercase_urls",
    "max_urls_per_depth", "max_per_subdomain",
    "response_timeout_s", "render_timeout_s", "custom_headers",
    # Phase 2 — resource + extraction gates (Pattern A/B)
    "crawl_images", "crawl_external", "store_hash", "extract_structured_data",
    "extract_http_headers", "extract_cookies", "store_html", "store_rendered_html",
    # Phase 3 — resource-fetch subsystem
    "crawl_css", "crawl_js", "crawl_media",
    # Phase 4 — link-target gates + PDF
    "crawl_hreflang", "crawl_amp", "crawl_pagination", "extract_pdf",
    # Phase 5 — scope + rendering + extraction
    "crawl_subdomains", "crawl_outside_start_folder", "follow_nofollow", "cdns",
    "assume_html", "max_page_size_kb", "window_width", "window_height",
    "js_error_reporting", "extract_srcset",
    # Phase 6 — report-level (do_audit)
    "respect_noindex", "respect_canonical", "ignore_non_indexable_issues",
    # Phase 7 — content area, duplicate tuning, DOM flatten, HTML validation
    "content_include", "content_exclude", "near_dup_threshold",
    "ignore_paginated_dupes", "flatten_shadow_dom", "flatten_iframes",
    "html_validation",
})

_GOOGLEBOT_MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile "
    "Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)

_PROFILE_PRESETS: list[dict[str, Any]] = [
    {"name": "Quick Check", "default": False, "data": {
        "js_render": False, "max_depth": 2, "max_pages": 100, "concurrency": 8}},
    {"name": "Full Technical", "default": True, "data": {
        "js_render": True, "max_depth": 5, "max_pages": 500, "concurrency": 5,
        "psi_enrich": True, "gsc_enrich": True}},
    {"name": "Content Audit", "default": False, "data": {
        "js_render": True, "max_depth": 4, "max_pages": 300, "render_sample": 20}},
    {"name": "JS Mobile", "default": False, "data": {
        "js_render": True, "max_depth": 3, "max_pages": 200,
        "user_agent": _GOOGLEBOT_MOBILE_UA}},
]


def _seed_profiles() -> None:
    """Insert the built-in presets once, on a fresh install."""
    db = SessionLocal()
    try:
        if db.query(ConfigProfile).count() == 0:
            for p in _PROFILE_PRESETS:
                db.add(ConfigProfile(
                    name=p["name"],
                    data={**CRAWL_CONFIG_DEFAULTS, **p["data"]},
                    is_default=p["default"],
                    is_preset=True,
                ))
            db.commit()
    finally:
        db.close()


_seed_profiles()

active_tasks: dict[int, dict[str, Any]] = {}

def _client_public(c: Client) -> dict[str, Any]:
    """Serialize a Client for the UI. Never returns the raw connection key —
    only whether one is set (I5-style: write credentials aren't echoed back)."""
    return {
        "id": c.id,
        "name": c.name,
        "base_url": c.base_url,
        "wp_url": c.wp_url or "",
        "connected": bool(c.wp_connection_key),
        "connection_method": c.connection_method or "url_only",
        "detected_stack": c.detected_stack or None,
    }


@app.get("/api/clients")
def get_clients() -> list[dict[str, Any]]:
    db = SessionLocal()
    # The hidden bucket that owns anonymous public-window audits never appears
    # in the agency client list.
    clients = db.query(Client).filter(Client.is_public.isnot(True)).all()
    res = [_client_public(c) for c in clients]
    db.close()
    return res


PUBLIC_CLIENT_NAME = "__scrawly_public__"


def _public_client(db: Any) -> Client:
    """Get-or-create the singleton hidden client that owns public-window audits.
    Public audits still need a Crawl row (FK to a client), but must not pollute
    the real client list, so they all hang off this one internal bucket."""
    c: Client | None = db.query(Client).filter(Client.name == PUBLIC_CLIENT_NAME).first()
    if c is None:
        c = Client(name=PUBLIC_CLIENT_NAME, base_url="", is_public=True)
        db.add(c)
        db.commit()
        db.refresh(c)
    return c


def _normalize_target(raw: str) -> str:
    """Coerce a user-typed target into a fetchable http(s) URL."""
    u = (raw or "").strip()
    if not u:
        raise HTTPException(status_code=400, detail="A URL is required.")
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    return u


@app.get("/api/clients/{client_id}")
def get_client(client_id: int) -> dict[str, Any]:
    db = SessionLocal()
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        db.close()
        raise HTTPException(status_code=404, detail="Client not found")
    res = _client_public(client)
    db.close()
    return res


@app.post("/api/clients")
def add_client(data: dict[str, str]) -> dict[str, Any]:
    db = SessionLocal()
    client = Client(
        name=data["name"],
        base_url=data["base_url"],
        wp_url=(data.get("wp_url") or data.get("base_url") or "").strip() or None,
        wp_connection_key=(data.get("wp_connection_key") or "").strip() or None,
        # Every client reaches its site through some method; URL-only (read-only
        # crawl) is the universal default and works for any tech stack.
        connection_method=(data.get("connection_method") or "url_only").strip(),
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    res = _client_public(client)
    db.close()
    return res


@app.put("/api/clients/{client_id}")
def update_client(client_id: int, data: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        db.close()
        raise HTTPException(status_code=404, detail="Client not found")
    if "name" in data and data["name"]:
        client.name = data["name"]
    if "base_url" in data and data["base_url"]:
        client.base_url = data["base_url"]
    if "wp_url" in data:
        client.wp_url = (str(data.get("wp_url") or "")).strip() or None
    # Only overwrite the key when a non-empty value is supplied (blank keeps it).
    if data.get("wp_connection_key"):
        client.wp_connection_key = str(data["wp_connection_key"]).strip()
    if data.get("connection_method"):
        client.connection_method = str(data["connection_method"]).strip()
    if "detected_stack" in data:
        client.detected_stack = data["detected_stack"] or None
    db.commit()
    db.refresh(client)
    res = _client_public(client)
    db.close()
    return res


@app.delete("/api/clients/{client_id}")
def delete_client(client_id: int) -> dict[str, Any]:
    """Remove a client and everything under it (crawls → issues/urls/fixes)."""
    db = SessionLocal()
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        db.close()
        raise HTTPException(status_code=404, detail="Client not found")
    crawl_ids = [c.id for c in db.query(Crawl).filter(Crawl.client_id == client_id)]
    if crawl_ids:
        issue_ids = [
            i.id for i in db.query(Issue).filter(Issue.crawl_id.in_(crawl_ids))
        ]
        if issue_ids:
            db.query(Fix).filter(Fix.issue_id.in_(issue_ids)).delete(
                synchronize_session=False
            )
        db.query(Issue).filter(Issue.crawl_id.in_(crawl_ids)).delete(
            synchronize_session=False
        )
        db.query(Resource).filter(Resource.crawl_id.in_(crawl_ids)).delete(
            synchronize_session=False
        )
        db.query(URL).filter(URL.crawl_id.in_(crawl_ids)).delete(
            synchronize_session=False
        )
        db.query(Crawl).filter(Crawl.id.in_(crawl_ids)).delete(
            synchronize_session=False
        )
    db.delete(client)
    db.commit()
    db.close()
    return {"deleted": client_id, "crawls_removed": len(crawl_ids)}


def _purge_crawl(db: Any, crawl_id: int) -> dict[str, int]:
    """Delete a crawl and everything it produced. The caller commits.

    Order matters — children before parents, since SQLite has no cascade here:
    fixes → issues → resources → urls → crawl. Also drops any live telemetry so a
    deleted crawl cannot keep being polled."""
    issue_ids = [i.id for i in db.query(Issue).filter(Issue.crawl_id == crawl_id)]
    removed = {"fixes": 0, "issues": len(issue_ids), "resources": 0, "urls": 0}
    if issue_ids:
        removed["fixes"] = db.query(Fix).filter(
            Fix.issue_id.in_(issue_ids)).delete(synchronize_session=False)
        db.query(Issue).filter(Issue.crawl_id == crawl_id).delete(
            synchronize_session=False)
    removed["resources"] = db.query(Resource).filter(
        Resource.crawl_id == crawl_id).delete(synchronize_session=False)
    removed["urls"] = db.query(URL).filter(
        URL.crawl_id == crawl_id).delete(synchronize_session=False)
    db.query(Crawl).filter(Crawl.id == crawl_id).delete(synchronize_session=False)
    active_tasks.pop(crawl_id, None)
    return removed


def _prune_public_crawls(db: Any, keep_id: int | None = None) -> int:
    """Enforce the public window's 'keep only the latest audit' rule: delete every
    anonymous public-client crawl except ``keep_id``. Returns how many were removed.
    The caller commits."""
    public = _public_client(db)
    q = db.query(Crawl).filter(Crawl.client_id == public.id)
    if keep_id is not None:
        q = q.filter(Crawl.id != keep_id)
    ids = [c.id for c in q.all()]
    for cid in ids:
        _purge_crawl(db, cid)
    return len(ids)


@app.delete("/api/crawls/{crawl_id}")
def delete_crawl(crawl_id: int) -> dict[str, Any]:
    """Delete one audit and everything it produced.

    Separate from deleting a client: a user usually wants to discard a single
    bad or superseded run (a mis-configured crawl, a duplicate) while keeping
    the site connected and its other audits intact.
    """
    db = SessionLocal()
    try:
        crawl = db.query(Crawl).filter(Crawl.id == crawl_id).first()
        if not crawl:
            raise HTTPException(status_code=404, detail="Crawl not found")
        removed = _purge_crawl(db, crawl_id)
        db.commit()
        return {"deleted": crawl_id, "removed": removed}
    finally:
        db.close()


@app.post("/api/clients/{client_id}/wp-test")
def test_client_connection(client_id: int, data: dict[str, str]) -> dict[str, Any]:
    """Live handshake with a client's Scrawly Connector plugin.

    Tests the values in the request body if provided (so the wizard can verify
    before saving), otherwise the stored connection.
    """
    db = SessionLocal()
    client = db.query(Client).filter(Client.id == client_id).first()
    db.close()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    stored_url = (client.wp_url or client.base_url or "").strip()
    wp_url = (data.get("wp_url") or stored_url).strip()
    key = (data.get("wp_connection_key") or "").strip()
    # A stored key is only ever sent to the site it was saved for: testing another
    # address needs that site's own key.
    if not key and _same_host(wp_url, stored_url):
        key = (client.wp_connection_key or "").strip()
    if not (wp_url and key):
        return {"connected": False, "detail": "Enter a Site URL and Connection Key."}
    try:
        from sentinelseo.wp.connector import ScrawlyConnectorClient

        conn = ScrawlyConnectorClient(wp_url, key)
        status = conn.status()
        conn.close()
        return {"connected": True, **status}
    except Exception as e:  # noqa: BLE001
        return {"connected": False, "detail": str(e)[:200]}


@app.post("/api/clients/{client_id}/detect")
async def detect_client_stack(client_id: int) -> dict[str, Any]:
    """Fingerprint a client's site and persist the detected stack. The wizard
    calls this on connect so the matching crawl preset is applied automatically."""
    from sentinelseo.detect import detect_stack

    db = SessionLocal()
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        db.close()
        raise HTTPException(status_code=404, detail="Client not found")
    target = _normalize_target(client.wp_url or client.base_url)
    det = await detect_stack(target)
    preset = _preset_for(det.stack, det.subcategory)
    client.detected_stack = det.to_dict()
    db.commit()
    db.close()
    return {"detection": det.to_dict(), "preset": preset}


def _verify_token(client_id: int) -> str:
    """A stable, unguessable ownership token for a client — derived from the app
    secret so we never have to store it. The user drops it on their site; we
    fetch it back to prove they control the origin."""
    import hashlib

    secret = os.environ.get("SCRAWLY_SECRET") or _load_settings().get("app_secret") or "scrawly"
    digest = hashlib.sha256(f"{secret}:{client_id}:scrawly-verify".encode()).hexdigest()
    return f"scrawly-verify-{digest[:32]}"


@app.get("/api/clients/{client_id}/verify-token")
def get_verify_token(client_id: int) -> dict[str, str]:
    """Return the ownership token + the file the user should place at site root."""
    token = _verify_token(client_id)
    return {"token": token, "filename": f"{token}.txt", "path": f"/.well-known/{token}.txt"}


@app.post("/api/clients/{client_id}/verify-file")
async def verify_client_file(client_id: int) -> dict[str, Any]:
    """Confirm site ownership by fetching the token file the user placed at root
    (or a <meta name="scrawly-verify"> tag). Universal — works on any stack.
    On success, marks the client connected via the drop-in file method."""
    db = SessionLocal()
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        db.close()
        raise HTTPException(status_code=404, detail="Client not found")
    base = _normalize_target(client.base_url).rstrip("/")
    token = _verify_token(client_id)
    candidates = [
        f"{base}/.well-known/{token}.txt",
        f"{base}/{token}.txt",
    ]
    found = False
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=12.0) as hc:
            for url in candidates:
                try:
                    r = await hc.get(url)
                    if r.status_code == 200 and token in r.text:
                        found = True
                        break
                except Exception:  # noqa: BLE001 - try the next candidate
                    continue
            if not found:  # fall back to a homepage <meta> tag
                r = await hc.get(base)
                if r.status_code == 200 and token in r.text:
                    found = True
    except Exception as e:  # noqa: BLE001
        db.close()
        return {"verified": False, "detail": str(e)[:200]}

    if found:
        client.connection_method = "connector_file"
        db.commit()
    db.close()
    return {
        "verified": found,
        "detail": "" if found else "Token not found yet. Place the file and retry.",
    }


@app.get("/api/connector/download")
def download_connector() -> Response:
    """Serve the Scrawly Connector plugin zip so users can install it in one click."""
    from pathlib import Path

    zip_path = (
        Path(__file__).resolve().parents[1]
        / "wp"
        / "companion_plugin"
        / "dist"
        / "scrawly-connector.zip"
    )
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Plugin package not found.")
    return Response(
        content=zip_path.read_bytes(),
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=scrawly-connector.zip"
        },
    )

def _compute_link_graph(urls: list[Any]) -> None:
    """Populate inlink_count/outlink_count on each URLRow from internal_links.

    Without this, both counts stay 0 and orphan/architecture checks are inert.
    Exact-address match for now; URL normalization is a separate improvement.
    """
    addrs = {u.address for u in urls}
    inlinks: dict[str, int] = dict.fromkeys(addrs, 0)
    for u in urls:
        targets = {
            link
            for link in (getattr(u, "internal_links", None) or [])
            if link in inlinks and link != u.address
        }
        u.outlink_count = len(targets)
        for t in targets:
            inlinks[t] += 1
    for u in urls:
        u.inlink_count = inlinks.get(u.address, 0)


async def _enrich_site(
    target_url: str, urls: list[Any], crawler: Crawler
) -> tuple[str, dict[str, Any], dict[str, tuple[int, int]], dict[str, Any]]:
    """Fetch robots.txt + sitemaps + llms.txt and derive the site probes.

    Populates SiteContext inputs the audit needs (robots_txt, probe,
    sitemap_files, llms_txt_*) and marks `in_sitemap` on each row — none of which
    the old path wired, so R/S/K/M/W checks could never fire correctly.
    """
    import re as _re
    from urllib.parse import urlparse

    base_p = urlparse(target_url)
    base = f"{base_p.scheme}://{base_p.netloc}"
    robots_txt = ""
    sitemap_files: dict[str, tuple[int, int]] = {}
    locs: set[str] = set()

    robots_status = 404
    robots_content_type = "text/plain"
    async with httpx.AsyncClient(follow_redirects=True, verify=False) as c:
        try:
            r = await c.get(f"{base}/robots.txt", timeout=5.0)
            robots_status = r.status_code
            robots_content_type = r.headers.get("content-type", "") or ""
            if r.status_code == 200:
                robots_txt = r.text
        except Exception:
            pass

        sitemap_urls = _re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots_txt) or [
            f"{base}/sitemap.xml",
            f"{base}/sitemap_index.xml",
            f"{base}/wp-sitemap.xml",  # WordPress core sitemap
        ]
        queue = list(dict.fromkeys(sitemap_urls))
        seen: set[str] = set()
        while queue and len(seen) < 50:
            sm = queue.pop(0)
            if sm in seen:
                continue
            seen.add(sm)
            try:
                r = await c.get(sm, timeout=8.0)
            except Exception:
                continue
            if r.status_code != 200:
                continue
            found = _re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text)
            children = [x for x in found if x.lower().endswith(".xml")]
            page_locs = [x for x in found if not x.lower().endswith(".xml")]
            locs.update(page_locs)
            sitemap_files[sm] = (len(page_locs), len(r.text.encode("utf-8")))
            queue.extend(children)

        # llms.txt (curated AI index) + optional llms-full.txt
        llms: dict[str, Any] = {"status": 404, "content": "", "links": [], "has_h1": False}
        try:
            r = await c.get(f"{base}/llms.txt", timeout=5.0)
            llms["status"] = r.status_code
            if r.status_code == 200:
                llms["content"] = r.text
                md_links = _re.findall(r"\]\(([^)]+)\)", r.text)
                llms["links"] = md_links or _re.findall(r"https?://\S+", r.text)
                llms["has_h1"] = bool(_re.search(r"(?m)^#\s+\S", r.text))
        except Exception:
            pass
        llms_full_status = 404
        try:
            llms_full_status = (await c.get(f"{base}/llms-full.txt", timeout=5.0)).status_code  # noqa: E501
        except Exception:
            pass

        # 404-handling probe: a URL that should not exist must return 404.
        notfound_status = 0
        try:
            notfound_status = (await c.get(f"{base}/scrawly-404-probe-x9z", timeout=5.0)).status_code  # noqa: E501
        except Exception:
            pass

        # Homepage-duplication + WP-hardening probes.
        homepage_200 = 0
        for path in ("/", "/index.php", "/home"):
            try:
                rr = await c.get(f"{base}{path}", timeout=5.0)
                if rr.status_code == 200:
                    homepage_200 += 1
            except Exception:
                pass
        xmlrpc_open = False
        try:
            rr = await c.get(f"{base}/xmlrpc.php", timeout=5.0)
            xmlrpc_open = rr.status_code in (200, 405)
        except Exception:
            pass
        rest_users_open = False
        try:
            rr = await c.get(f"{base}/wp-json/wp/v2/users", timeout=5.0)
            rest_users_open = rr.status_code == 200 and bool(rr.json())
        except Exception:
            pass

    loc_set = {x.split("#")[0] for x in locs}
    for u in urls:
        if u.address.split("#")[0] in loc_set:
            u.in_sitemap = True

    # TLS certificate health (M04): the crawl runs with verification off so it can
    # audit broken sites, so the certificate gets its own verified probe.
    cert_days: int | None = None
    if base_p.scheme == "https" and base_p.hostname:
        from sentinelseo.crawl.tls import tls_cert_days
        cert_days = await tls_cert_days(base_p.hostname, base_p.port or 443)

    probe: dict[str, Any] = {
        "homepage_versions_200": homepage_200,
        "xmlrpc_open": xmlrpc_open,
        "rest_users_open": rest_users_open,
        "robots_status": robots_status,
        "robots_content_type": robots_content_type,
        "cert_days_valid": cert_days,
        "notfound_status": notfound_status,
        "llms_full_status": llms_full_status,
    }
    if crawler.ai_access:
        m = crawler.ai_access.matrix
        probe["ai_training_crawlers_blocked"] = any(
            not m[b]["robots_allowed"]
            for b in ("GPTBot", "CCBot", "ClaudeBot", "Google-Extended")
            if b in m
        )
        probe["ai_search_crawlers_blocked"] = any(
            not m[b]["robots_allowed"]
            for b in ("OAI-SearchBot", "Claude-SearchBot", "PerplexityBot")
            if b in m
        )
        probe["waf_blocks_ai_silently"] = any(
            m[b]["robots_allowed"] and not m[b]["live_ok"] for b in m
        )
    return robots_txt, probe, sitemap_files, llms


def _cookie_names(set_cookie: Any) -> list[str]:
    """Best-effort cookie names from a (possibly comma-joined) Set-Cookie header."""
    if not set_cookie:
        return []
    import re as _re

    s = set_cookie if isinstance(set_cookie, str) else str(set_cookie)
    names = _re.findall(r"(?:^|,\s*)([A-Za-z0-9_\-.]+)=", s)
    skip = {"expires", "path", "domain", "max-age", "samesite", "secure", "httponly"}
    return [n for n in dict.fromkeys(names) if n.lower() not in skip]


def _parse_url_list(raw: Any) -> list[str]:
    """Split a pasted URL list (newline/comma separated) into fetchable URLs.
    Non-URL lines are ignored, so a raw export pastes in unmodified (SF §17)."""
    if isinstance(raw, list):
        items = [str(x) for x in raw]
    else:
        items = re.split(r"[\n,]", str(raw or ""))
    out: list[str] = []
    for line in items:
        u = line.strip()
        if not u:
            continue
        if not re.match(r"^https?://", u, re.I):
            if not re.match(r"^[\w.-]+\.[a-z]{2,}", u, re.I):
                continue  # not a URL — skip (raw exports carry stray text)
            u = "https://" + u
        out.append(u)
    return list(dict.fromkeys(out))  # de-dup, preserve order


def _apply_segments(urls: list[Any], config: dict[str, Any]) -> None:
    """SF Pattern N — assign each URL the first matching segment (cascade
    precedence: order defines priority, first match wins). Rules are URL regexes;
    an unmatched URL gets no segment."""
    rules = config.get("segments") or []
    compiled: list[tuple[str, Any]] = []
    for r in rules:
        name = str(r.get("name") or "").strip()
        pattern = str(r.get("pattern") or "").strip()
        if not name or not pattern:
            continue
        try:
            compiled.append((name, re.compile(pattern)))
        except re.error:
            compiled.append((name, re.compile(re.escape(pattern))))
    if not compiled:
        return
    for u in urls:
        for name, rx in compiled:
            if rx.search(u.address):
                u.segment = name
                break


def _apply_extraction_gates(urls: list[Any], config: dict[str, Any]) -> None:
    """SF Pattern B — mutate crawled rows so disabled extraction flags empty
    their field. Applied before audit + persist so both honor the config."""
    store_hash = config.get("store_hash", True)
    structured = config.get("extract_structured_data", True)
    for u in urls:
        if not store_hash:
            u.content_hash = ""            # kills exact-duplicate detection
        if not structured:
            u.jsonld = []
            u.microdata_types = []
            u.rdfa_types = []


async def do_audit(crawl_id: int, target_url: str, config: dict[str, Any],
                   owner: str = "") -> None:
    # Bind this background crawl's DB writes to the owning workspace explicitly,
    # so every URL/issue/resource row lands in the same per-workspace database as
    # the crawl record — independent of any request context.
    set_current_owner(owner)
    active_tasks[crawl_id] = {"status": "Starting Crawl...", "progress": 5}

    js_render = config.get("js_render", True)
    concurrency = config.get("concurrency", 5)
    max_depth = config.get("max_depth", 3)
    user_agent = config.get("user_agent", "ScrawlyBot/1.0")
    respect_robots = config.get("respect_robots", True)
    render_sample = config.get("render_sample", 0)
    include_patterns = config.get("include_patterns", "")
    exclude_patterns = config.get("exclude_patterns", "")
    max_pages = config.get("max_pages", 500)

    db = None
    try:
        crawler = Crawler(
            concurrency=concurrency,
            max_depth=max_depth,
            render=js_render,
            user_agent=user_agent,
            respect_robots=respect_robots,
            render_sample=render_sample,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            max_pages=max_pages,
            max_requests_per_sec=config.get("max_requests_per_sec", 0),
            max_url_length=config.get("max_url_length", 2000),
            max_query_params=config.get("max_query_params", 0),
            max_links_per_page=config.get("max_links_per_page", 0),
            max_folder_depth=config.get("max_folder_depth", 0),
            max_redirects=config.get("max_redirects", 5),
            discover_sitemap=config.get("discover_sitemap", True),
            sitemap_only=config.get("sitemap_only", False),
            # SF-parity engine-wired config (Phase 1).
            robots_mode=config.get("robots_mode", "respect"),
            robots_user_agent=config.get("robots_user_agent", ""),
            remove_parameters=config.get("remove_parameters", ""),
            regex_replace=config.get("regex_replace", []),
            lowercase_urls=config.get("lowercase_urls", False),
            crawl_fragment_identifiers=config.get("crawl_fragment_identifiers", False),
            max_urls_per_depth=config.get("max_urls_per_depth", 0),
            max_per_subdomain=config.get("max_per_subdomain", 0),
            max_page_size_kb=config.get("max_page_size_kb", 0),
            response_timeout_s=config.get("response_timeout_s", 20),
            custom_headers=config.get("custom_headers", {}),
            crawl_images=config.get("crawl_images", True),
            crawl_external=config.get("crawl_external", True),
            crawl_css=config.get("crawl_css", True),
            crawl_js=config.get("crawl_js", True),
            crawl_media=config.get("crawl_media", True),
            crawl_hreflang=config.get("crawl_hreflang", False),
            crawl_amp=config.get("crawl_amp", False),
            crawl_pagination=config.get("crawl_pagination", False),
            extract_pdf=config.get("extract_pdf", True),
            list_mode=config.get("list_mode", False),
            list_urls=_parse_url_list(config.get("list_urls", "")),
            form_auth=config.get("form_auth", False),
            render_timeout_s=config.get("render_timeout_s", 15),
            crawl_subdomains=config.get("crawl_subdomains", False),
            crawl_outside_start_folder=config.get("crawl_outside_start_folder", False),
            follow_nofollow=config.get("follow_nofollow", False),
            cdns=config.get("cdns", ""),
            assume_html=config.get("assume_html", True),
            window_width=config.get("window_width", 1024),
            window_height=config.get("window_height", 768),
            js_error_reporting=config.get("js_error_reporting", False),
            extract_srcset=config.get("extract_srcset", True),
            content_include=config.get("content_include", ""),
            content_exclude=config.get("content_exclude", ""),
            flatten_shadow_dom=config.get("flatten_shadow_dom", False),
            flatten_iframes=config.get("flatten_iframes", False),
        )
        import time as _time
        active_tasks[crawl_id].update(
            status="Crawling in progress...", progress=10, phase="crawl",
            crawled=0, discovered=1, queue=1, active=[], recent=[],
            status_tally={}, started_at=_time.time(), max_pages=max_pages,
            target=target_url,
        )
        # Point the crawler's telemetry sink at this task so per-URL progress
        # streams live to /api/audit/status.
        crawler.telemetry = active_tasks[crawl_id]

        urls, diffs, images, sds = await crawler.crawl_site(target_url)
        active_tasks[crawl_id].update(phase="enrich", active=[])

        # Extraction-flag gates (SF Pattern B): applied to the in-memory rows so
        # BOTH the audit engine and the persisted data honor them. Disabling a flag
        # empties its field → dependent checks/filters degrade gracefully (no error).
        _apply_extraction_gates(urls, config)
        # Segment each URL (Pattern N) before persist so the column + viz colouring
        # and per-segment filtering all read the same assignment.
        _apply_segments(urls, config)

        # Normalize internal links (drop fragments/tracking params) so they line
        # up with the crawled page addresses for graph edges + link counts.
        from sentinelseo.crawl.fetcher import normalize_url
        for u in urls:
            u.internal_links = list(
                dict.fromkeys(normalize_url(link) for link in (u.internal_links or []))
            )

        # Link graph must be computed before storing + before checks run.
        _compute_link_graph(urls)

        # Internal authority (PageRank over the link graph) — transitive link
        # value, not just raw inlink counts.
        from sentinelseo.audit.authority import compute_pagerank
        _pr = compute_pagerank(
            [u.address for u in urls],
            {u.address: (u.internal_links or []) for u in urls},
        )
        _pr_by_url = _pr  # address -> 0-100 authority

        # PageSpeed Insights enrichment (FR-E2): sample a few 200 pages, prefer
        # CrUX field CWV (LCP/INP/CLS) over the lab render metrics. Opt-in +
        # requires PAGESPEED_API_KEY; capped so it doesn't dominate crawl time.
        if config.get("psi_enrich") and os.environ.get("PAGESPEED_API_KEY"):
            from sentinelseo.enrichment.psi_lighthouse import PSILighthouseEnricher
            enricher = PSILighthouseEnricher()
            active_tasks[crawl_id].update(status="PageSpeed enrichment...", progress=50)
            for u in [x for x in urls if x.status == 200][: config.get("psi_sample", 3)]:
                m = await asyncio.to_thread(enricher.fetch_metrics, u.address)
                if m.get("available"):
                    if m.get("lcp_s") is not None:
                        u.lcp_s = m["lcp_s"]
                    if m.get("cls") is not None:
                        u.cls = m["cls"]
                    if m.get("inp_ms") is not None:
                        u.inp_ms = m["inp_ms"]

        # Google Search Console enrichment (FR-E1): per-URL impressions/clicks so
        # the report can prioritise issues on pages that get real traffic. Opt-in;
        # needs the property in Search Console + the service account granted access.
        gsc_data: dict[str, Any] = {}
        if config.get("gsc_enrich") and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            from sentinelseo.enrichment.gsc import GSCEnricher
            prop = target_url if target_url.endswith("/") else target_url + "/"
            gsc_data = await asyncio.to_thread(GSCEnricher(prop).fetch_top_pages)

        # GA4 engagement (Pattern M) — opt-in; needs the Google OAuth grant + a
        # property id. Page paths are matched onto crawled URLs.
        ga4_by_url: dict[str, Any] = {}
        if config.get("ga4_enrich") and config.get("ga4_property_id"):
            from sentinelseo.enrichment.ga4 import GA4Enricher, match_to_urls

            def _ga4() -> dict[str, Any]:
                raw = GA4Enricher(str(config["ga4_property_id"])).fetch_page_metrics(
                    days=int(config.get("ga4_days", 28) or 28)
                )
                # Surface a GA4 API failure (bad property id / permission / expired
                # grant) instead of it looking like "no pages matched".
                if isinstance(raw, dict) and raw.get("_error"):
                    active_tasks[crawl_id]["ga4_error"] = str(raw["_error"])
                    return {}
                return match_to_urls(
                    raw, [u.address for u in urls],
                    fuzzy=bool(config.get("ga4_fuzzy_match", True)),
                )

            ga4_by_url = await asyncio.to_thread(_ga4)

        # Spelling & grammar (Pattern I) over the content-area text — opt-in.
        spelling_by_url: dict[str, list[dict[str, Any]]] = {}
        if config.get("spelling_enrich"):
            from sentinelseo.enrichment import spelling as _sp

            mode = "local" if _sp.java_available() else "public"
            ignore = [w for w in str(config.get("spelling_ignore", "")).split(",") if w.strip()]
            override = str(config.get("spelling_language", "auto") or "auto")

            def _spell() -> dict[str, list[dict[str, Any]]]:
                out: dict[str, list[dict[str, Any]]] = {}
                for u in urls:
                    text = getattr(u, "main_text", "") or ""
                    if not text.strip():
                        continue
                    lang = _sp.normalize_language(getattr(u, "lang", None), override)
                    try:
                        hits = _sp.check_text(text, language=lang, mode=mode, ignore=ignore)
                    except _sp.SpellingBackendError as e:
                        # The backend is down or rate-limited (the free public API
                        # caps at ~20 req/min). Stop — don't hammer it once per URL
                        # and don't report a misspelled site as clean.
                        active_tasks[crawl_id]["spelling_error"] = str(e)
                        break
                    if hits:
                        out[u.address] = hits
                return out

            spelling_by_url = await asyncio.to_thread(_spell)

        # Semantic similarity / low relevance (Pattern J) — needs an embeddings
        # provider; silently skipped when none is configured.
        embed_report: dict[str, Any] = {}
        if config.get("embeddings_enrich"):
            from sentinelseo.ai import embeddings as _emb

            if _emb.is_configured():
                def _embed() -> dict[str, Any]:
                    pairs = [(u.address, (getattr(u, "main_text", "") or "")[:6000])
                             for u in urls if (getattr(u, "main_text", "") or "").strip()]
                    if not pairs:
                        return {}
                    vecs = _emb.embed_texts([t for _a, t in pairs])
                    if not vecs:
                        return {}
                    if len(vecs) != len(pairs):
                        return {}   # mis-aligned batch — don't attribute vectors wrongly
                    by_url = {a: v for (a, _t), v in zip(pairs, vecs, strict=False)}
                    # The threshold is a free-text UI field; a stray character must
                    # skip embeddings, not crash the whole audit.
                    try:
                        thr = float(config.get("embeddings_similarity_threshold", 0.92) or 0.92)
                    except (TypeError, ValueError):
                        thr = 0.92
                    return {
                        "similar": _emb.find_similar(by_url, thr)[:200],
                        "low_relevance": _emb.find_low_relevance(by_url)[:200],
                    }

                embed_report = await asyncio.to_thread(_embed)

        # Group render diffs (response-vs-rendered element changes) per URL.
        render_by_url: dict[str, list[dict[str, str]]] = {}
        for d in diffs:
            render_by_url.setdefault(d.url, []).append({"element": d.element, "state": d.state})

        active_tasks[crawl_id].update(status="Storing Crawl Data...", progress=60, phase="store")

        # Custom extraction (site-wide scraper) — opt-in; only runs when the
        # profile defines extractors/searches, so the default crawl stays lean.
        extractors = config.get("custom_extractors") or []
        searches = config.get("custom_searches") or []
        custom_by_url: dict[str, Any] = {}
        if extractors or searches:
            from sentinelseo.crawl.custom_extract import run_custom_extraction
            for u in urls:
                if u.html_response:
                    custom_by_url[u.address] = run_custom_extraction(
                        u.html_response, extractors, searches
                    )

        db = SessionLocal()

        crawl_record = db.query(Crawl).filter(Crawl.id == crawl_id).first()
        if crawl_record:
            crawl_record.url_count = len(urls)
            if embed_report:
                crawl_record.embeddings_report = embed_report
            db.commit()

        # --- Agentic Web readiness (origin-level) ---------------------------
        # Probes the site ROOT only — well-known paths, response headers, DNS —
        # so this is a fixed ~25 requests whether the crawl found 6 pages or
        # 100,000. Deliberately additive: a failure here must never fail the
        # audit, so the whole block degrades to "no agentic data".
        active_tasks[crawl_id].update(
            status="Checking agentic readiness...", progress=72, phase="agentic")
        try:
            from sentinelseo.agentic import run_agentic_audit
            _pw = None
            _agentic_browser = None
            try:
                if js_render:
                    from playwright.async_api import async_playwright
                    _pw = await async_playwright().start()
                    from sentinelseo.crawl.browser import launch_chromium
                    _agentic_browser = await launch_chromium(_pw, headless=True)
                agentic_rep = await run_agentic_audit(
                    target_url,
                    browser=_agentic_browser,
                    stack=str(config.get("stack") or ""),
                )
                if crawl_record:
                    crawl_record.agentic_report = agentic_rep.to_dict()
                    db.commit()
            finally:
                if _agentic_browser is not None:
                    await _agentic_browser.close()
                if _pw is not None:
                    await _pw.stop()
        except Exception as exc:
            # Surface it rather than swallowing: a silently missing section is
            # indistinguishable from a site that simply scored zero.
            active_tasks[crawl_id]["agentic_error"] = type(exc).__name__

        # Storage gates (SF Pattern A "store" side / Pattern B).
        _store_headers = config.get("extract_http_headers", True)
        _store_cookies = config.get("extract_cookies", False)
        _store_html = config.get("store_html", False)
        _store_rendered = config.get("store_rendered_html", False)
        # Respect noindex / canonical (SF Advanced): the page was still crawled and
        # its links followed (the graph/authority above used it), but it's hidden
        # from the stored results — so it never appears in the UI.
        _respect_noindex = bool(config.get("respect_noindex"))
        _respect_canonical = bool(config.get("respect_canonical"))

        def _hidden(u: Any) -> bool:
            if _respect_noindex and "noindex" in (
                (u.meta_robots or "") + " " + (u.x_robots or "")
            ).lower():
                return True
            if _respect_canonical and u.canonical:
                from sentinelseo.crawl.fetcher import normalize_url as _nz
                if _nz(u.canonical) != _nz(u.address):
                    return True
            return False

        for u in urls:
            if _hidden(u):
                continue
            db.add(URL(
                crawl_id=crawl_id,
                address=u.address,
                status=u.status,
                redirect_chain=u.redirect_chain,
                title=u.title or "",
                meta_desc=u.meta_desc,
                canonical=u.canonical,
                meta_robots=u.meta_robots,
                x_robots=u.x_robots,
                word_count=u.word_count,
                readability=u.readability,
                text_to_code=u.text_to_code,
                forms_count=u.forms_count,
                microdata_types=u.microdata_types,
                rdfa_types=u.rdfa_types,
                last_modified=(u.headers or {}).get("last-modified"),
                custom_data=custom_by_url.get(u.address),
                prev_url=u.prev_url,
                next_url=u.next_url,
                amp_url=u.amp_url,
                mobile_alternate=u.mobile_alternate,
                cookies=_cookie_names((u.headers or {}).get("set-cookie")) if _store_cookies else [],
                pagerank=_pr_by_url.get(u.address),
                content_hash=u.content_hash,
                near_dup_cluster=u.near_dup_cluster,
                ttfb=u.ttfb,
                size=u.size,
                inlink_count=u.inlink_count,
                outlink_count=u.outlink_count,
                indexable=u.indexable,
                indexability_reason=u.indexability_reason,
                depth=u.depth,
                lcp_s=u.lcp_s,
                cls=u.cls,
                inp_ms=u.inp_ms,
                gsc_impressions=(gsc_data.get(u.address) or {}).get("impressions"),
                gsc_clicks=(gsc_data.get(u.address) or {}).get("clicks"),
                render_diff=render_by_url.get(u.address, []),
                internal_links=u.internal_links,
                h1=u.h1,
                h2=u.h2,
                images=[img.__dict__ for img in u.images],
                jsonld=u.jsonld,
                headers=u.headers if _store_headers else {},
                raw_html=(u.html_response or "") if _store_html else None,
                rendered_html=u.html_render if _store_rendered else None,
                pdf_properties=getattr(u, "pdf_properties", None) or None,
                segment=getattr(u, "segment", None),
                ga4=ga4_by_url.get(u.address) or None,
                spelling=spelling_by_url.get(u.address) or None,
                js_errors=(getattr(u, "js_errors", None) or None),
            ))
        # Persist the swept sub-resources (CSS/JS/media) for the Resources view.
        for r in getattr(crawler, "resources", []) or []:
            db.add(Resource(
                crawl_id=crawl_id, url=r.url, type=r.type, status=r.status,
                content_type=r.content_type, size=r.size,
                ref_count=getattr(r, "ref_count", 0),
            ))
        db.commit()

        active_tasks[crawl_id].update(status="Running Audit Engine...", progress=80, phase="audit")

        robots_txt, probe, sitemap_files, llms = await _enrich_site(
            target_url, urls, crawler
        )

        pages: dict[str, CrawlContext] = {}
        for u in urls:
            pages[u.address] = CrawlContext(
                url=u.address,
                title=u.title or "",
                url_row=u,
                render_diffs=[d for d in diffs if d.url == u.address],
                images=u.images,
                structured_data=u.jsonld,
                raw_html=u.html_response or "",
                rendered_html=u.html_render,
            )

        site = SiteContext(
            base_url=target_url,
            pages=pages,
            robots_txt=robots_txt,
            robots_txt_status=int(probe.get("robots_status") or 404),
            robots_txt_content_type=str(probe.get("robots_content_type") or "text/plain"),
            cert_days_valid=probe.get("cert_days_valid"),
            probe=probe,
            sitemap_files=sitemap_files,
            llms_txt_status=llms["status"],
            llms_txt_content=llms["content"],
            llms_txt_links=llms["links"],
            has_h1_in_llms_txt=llms["has_h1"],
            external_status=dict(crawler.external_cache),
            config=config,
        )

        findings = await asyncio.to_thread(run_audit, site)

        _db_urls = db.query(URL).filter(URL.crawl_id == crawl_id).all()
        url_map = {u.address: u.id for u in _db_urls}
        # Ignore Non-Indexable URLs for Issues (SF Advanced): when on, an issue that
        # only affects non-indexable pages is dropped.
        _ignore_ni = bool(config.get("ignore_non_indexable_issues"))
        _indexable_ids = {u.id for u in _db_urls if u.indexable} if _ignore_ni else None

        # Group findings by check_id (one Issue row per check).
        order = {"Info": 1, "Low": 2, "Medium": 3, "High": 4, "Critical": 5}
        grouped: dict[str, Any] = {}
        for finding in findings:
            existing = grouped.get(finding.check_id)
            if existing is None:
                grouped[finding.check_id] = finding
            else:
                existing.affected_urls = list(
                    set(existing.affected_urls) | set(finding.affected_urls)
                )
                if order.get(finding.severity, 0) > order.get(existing.severity, 0):
                    existing.severity = finding.severity

        for finding in grouped.values():
            affected_url_ids = [
                url_map[a] for a in finding.affected_urls if a in url_map
            ]
            if _indexable_ids is not None and affected_url_ids and not any(
                i in _indexable_ids for i in affected_url_ids
            ):
                continue   # every affected page is non-indexable → skip the issue
            db.add(Issue(
                crawl_id=crawl_id,
                check_id=finding.check_id,
                severity=finding.severity,
                tier=finding.tier,
                affected_url_ids=affected_url_ids,
                evidence=finding.evidence,
                why_it_matters=finding.why_it_matters,
                recommended_fix=finding.recommended_fix,
            ))
        db.commit()

        active_tasks[crawl_id].update(status="Complete", progress=100, phase="complete")
    except Exception as e:
        active_tasks[crawl_id] = {"status": f"Failed: {str(e)}", "progress": 0, "phase": "failed"}
    finally:
        if db is not None:
            db.close()

DEFAULT_CRAWL_SETTINGS: dict[str, Any] = {
    "user_agent": "ScrawlyBot/1.0",
    "concurrency": 8,
    "max_depth": 3,
    "js_render": True,
    "respect_robots": True,
    "render_sample": 0,  # 0 = render every page; N = render first N pages only
    "include_patterns": "",
    "exclude_patterns": "",
    "wp_url": "",             # Scrawly Connector: target site URL
    "wp_connection_key": "",  # Scrawly Connector: connection key from the plugin
    # AI provider for fix suggestions (pluggable: Anthropic / OpenAI-compatible).
    "ai_provider": "",        # preset name (anthropic/openai/deepseek/openrouter/glm/nara/custom)
    "ai_kind": "openai",      # wire format: openai | anthropic
    "ai_base_url": "",
    "ai_model": "",
    "ai_api_key": "",         # secret — masked on GET, preserved on partial PUT
    # White-label report branding (applied to the exported HTML audit report).
    "report_brand_name": "",
    "report_brand_color": "#6366f1",
    "report_brand_logo": "",
    "report_brand_contact": "",
}


def _load_settings() -> dict[str, Any]:
    from sentinelseo.db.models import AppSettings
    db = SessionLocal()
    row = db.query(AppSettings).filter(AppSettings.id == 1).first()
    data = dict(row.data) if row and row.data else {}
    db.close()
    return {**DEFAULT_CRAWL_SETTINGS, **data}


# Settings keys never echoed by GET /api/settings and preserved-on-blank by PUT.
# Credential enrichment providers read their secrets from env only (see
# embeddings.py / backlinks.py), but these are masked as defence-in-depth in case
# a value ever lands in settings.
_SECRET_KEYS = (
    "ai_api_key", "wp_connection_key", "embed_api_key",
    "scrawly_moz_access_id", "scrawly_moz_secret_key",
    "scrawly_ahrefs_token", "scrawly_majestic_key",
)


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    s = _load_settings()
    # Never echo secrets back; expose only whether each is set.
    for k in _SECRET_KEYS:
        s[f"{k}_set"] = bool(s.get(k))
        s[k] = ""
    # AI may be configured via env (SCRAWLY_AI_*) even when not saved in the UI.
    s["ai_api_key_set"] = bool(_ai_config().get("api_key"))
    return s


@app.put("/api/settings")
def put_settings(data: dict[str, Any]) -> dict[str, Any]:
    from sentinelseo.db.models import AppSettings
    db = SessionLocal()
    row = db.query(AppSettings).filter(AppSettings.id == 1).first()
    existing = dict(row.data) if row and row.data else {}
    # Blank secret in the payload means "keep the stored one" (masked round-trip).
    data = dict(data)
    for k in _SECRET_KEYS:
        if k in data and not (data[k] or "").strip():
            data.pop(k)
    # A stored AI key belongs to its provider: if the provider's address moves to
    # another host without a new key, drop the old key instead of sending it there.
    new_base = data.get("ai_base_url")
    if (new_base is not None and "ai_api_key" not in data
            and not _same_host(str(new_base), str(existing.get("ai_base_url") or ""))):
        existing.pop("ai_api_key", None)
    # Merge over defaults + existing so partial updates never clobber other keys.
    merged = {**DEFAULT_CRAWL_SETTINGS, **existing, **data}
    if row is None:
        db.add(AppSettings(id=1, data=merged))
    else:
        row.data = merged
    db.commit()
    db.close()
    out = dict(merged)
    for k in _SECRET_KEYS:
        out[f"{k}_set"] = bool(out.get(k))
        out[k] = ""
    return out


def _same_host(a: str, b: str) -> bool:
    """True when two addresses point at the same host (empty counts as unset)."""
    from urllib.parse import urlparse

    def host(u: str) -> str:
        u = u.strip()
        if u and "://" not in u:
            u = "https://" + u
        return (urlparse(u).hostname or "").lower().removeprefix("www.")

    return host(a) == host(b)


def _ai_config() -> dict[str, Any]:
    """AI provider config — UI settings first, then SCRAWLY_AI_* env vars."""
    s = _load_settings()
    return {
        "kind": s.get("ai_kind") or os.environ.get("SCRAWLY_AI_KIND") or "openai",
        "base_url": s.get("ai_base_url") or os.environ.get("SCRAWLY_AI_BASE_URL") or "",
        "model": s.get("ai_model") or os.environ.get("SCRAWLY_AI_MODEL") or "",
        "api_key": s.get("ai_api_key") or os.environ.get("SCRAWLY_AI_KEY") or "",
    }


@app.post("/api/ai/test")
def ai_test() -> dict[str, Any]:
    """Verify the configured AI provider with a tiny prompt."""
    from sentinelseo.ai.provider import ai_complete, is_configured

    cfg = _ai_config()
    if not is_configured(cfg):
        return {"ok": False, "detail": "AI not configured (api key, base URL, model)."}
    try:
        reply = ai_complete(cfg, "You are a terse assistant.", "Reply with exactly: OK", max_tokens=10)
        return {"ok": True, "model": cfg["model"], "reply": reply[:60]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": str(e)[:200]}


# The assistant is a localized analyst: it may only reason over the active
# crawl's data or explain how to use Scrawly. This scope guard lives in the
# system prompt (the digest is appended below it).
_AI_SYSTEM_PROMPT = (
    "You are Scrawly's audit analyst, embedded in a self-hosted technical-SEO "
    "crawler. You have two jobs and no others:\n"
    "1. Analyse and explain the CURRENT audit using only the data provided below "
    "(counts, health score, issues, segments). Cite concrete numbers; never "
    "invent data that is not present.\n"
    "2. Explain how to use Scrawly's features: crawling and config profiles, the "
    "Dashboard, Site Explorer, Resources, SERP, Issues & fixes, Compare, and "
    "integrations.\n"
    "If asked about anything unrelated to this audit or to Scrawly, briefly "
    "decline and steer back. Be concise, specific and practical."
)


def _ai_context_digest(crawl_id: int) -> str:
    """Build a compact, token-bounded text digest of a crawl for the assistant.

    Reuses the dashboard aggregation and the grouped issue list so the model
    sees the same numbers the UI shows. Never includes secrets."""
    try:
        d = get_dashboard(crawl_id)
    except Exception:  # noqa: BLE001
        return "No audit is currently loaded."
    t = d.get("totals", {})
    sev = d.get("severity", {})
    sc = d.get("status_classes", {})
    lines = [
        f"CURRENT AUDIT — crawl #{crawl_id} · {d.get('target_url') or 'unknown target'}",
        f"Pages crawled: {t.get('urls', 0)} | indexable: {t.get('indexable', 0)} "
        f"({d.get('indexable_pct', 0)}%) | broken (4xx/5xx): {t.get('broken', 0)} "
        f"| avg depth: {t.get('avg_depth', 0)}",
        f"Health score: {d.get('health_score', 0)}/100",
        f"Response codes: 2xx={sc.get('2xx', 0)} 3xx={sc.get('3xx', 0)} "
        f"4xx={sc.get('4xx', 0)} 5xx={sc.get('5xx', 0)}",
        f"Issues: {t.get('issues', 0)} total — Critical {sev.get('Critical', 0)}, "
        f"High {sev.get('High', 0)}, Medium {sev.get('Medium', 0)}, "
        f"Low {sev.get('Low', 0)}, Info {sev.get('Info', 0)}",
    ]
    cats = d.get("issue_categories", [])
    if cats:
        lines.append(
            "Issue categories: "
            + ", ".join(f"{c['category']} ({c['count']})" for c in cats[:8])
        )
    segs = d.get("segments", [])
    if segs:
        lines.append(
            "Segments: " + ", ".join(f"{s['name']} ({s['count']})" for s in segs[:8])
        )

    # Top issues by severity (grouped per check), capped for the token budget.
    try:
        issues = get_issues(crawl_id)
    except Exception:  # noqa: BLE001
        issues = []
    rank = {"Critical": 5, "High": 4, "Medium": 3, "Low": 2, "Info": 1}
    issues.sort(key=lambda i: rank.get(i.get("severity", ""), 0), reverse=True)
    if issues:
        lines.append("Top issues:")
        for i in issues[:12]:
            n = len(i.get("affected_url_ids") or [])
            why = (i.get("why_it_matters") or "").strip()
            lines.append(
                f"- [{i.get('severity')}] {i.get('title')} "
                f"(affects {n} page{'s' if n != 1 else ''}). {why}"[:220]
            )
    return "\n".join(lines)


@app.post("/api/ai/chat")
def ai_chat(body: dict[str, Any]) -> StreamingResponse:
    """Streaming (SSE) chat with the localized audit analyst. Body:
    {crawl_id?: int, messages: [{role, content}]}. The provider key stays
    server-side; only assistant text deltas are streamed back."""
    from sentinelseo.ai.provider import ai_stream, is_configured

    def _sse(payload: dict[str, Any]) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    cfg = _ai_config()
    if not is_configured(cfg):
        def _unconfigured() -> Any:
            yield _sse({"error": "AI is not configured. Add your provider key in Settings → AI provider."})
        return StreamingResponse(_unconfigured(), media_type="text/event-stream")

    # Sanitize the client history: keep only user/assistant string turns, capped.
    raw = body.get("messages") or []
    messages: list[dict[str, str]] = []
    for m in raw[-12:]:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content[:4000]})
    if not messages:
        def _empty() -> Any:
            yield _sse({"error": "No message provided."})
        return StreamingResponse(_empty(), media_type="text/event-stream")

    crawl_id = body.get("crawl_id")
    digest = _ai_context_digest(int(crawl_id)) if crawl_id else "No audit is currently loaded."
    system = f"{_AI_SYSTEM_PROMPT}\n\n{digest}"

    def _gen() -> Any:
        try:
            for chunk in ai_stream(cfg, system, messages, max_tokens=700):
                yield _sse({"delta": chunk})
            yield _sse({"done": True})
        except Exception as e:  # noqa: BLE001
            yield _sse({"error": str(e)[:300]})

    return StreamingResponse(_gen(), media_type="text/event-stream")


def _profile_public(p: ConfigProfile) -> dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "data": {**CRAWL_CONFIG_DEFAULTS, **(p.data or {})},
        "is_default": p.is_default,
        "is_preset": p.is_preset,
    }


@app.get("/api/profiles")
def get_profiles() -> list[dict[str, Any]]:
    db = SessionLocal()
    rows = db.query(ConfigProfile).order_by(ConfigProfile.id).all()
    res = [_profile_public(p) for p in rows]
    db.close()
    return res


@app.get("/api/presets")
def list_presets() -> dict[str, Any]:
    """Tech-stack preset catalogue (labels + sub-categories) for the config UI."""
    from sentinelseo.crawl.presets import get_presets

    return get_presets()


@app.get("/api/presets/{tech}")
def resolve_preset(tech: str, subcategory: str = "") -> dict[str, Any]:
    """Resolve a (tech, subcategory) choice into crawl-config deltas."""
    from sentinelseo.crawl.presets import resolve

    return resolve(tech, subcategory)


def _preset_for(stack: str, subcategory: str) -> dict[str, Any]:
    """Map a detected stack to its crawl-config preset + a human label."""
    from sentinelseo.crawl.presets import get_presets, resolve

    cat = get_presets()
    known = cat.get(stack)
    if not known:
        stack, subcategory = "generic", ""
        known = cat.get("generic", {})
    label = known.get("label", stack.title())
    sub_label = known.get("subcategories", {}).get(subcategory, "")
    return {
        "stack": stack,
        "subcategory": subcategory,
        "label": label,
        "subcategory_label": sub_label,
        "config": resolve(stack, subcategory),
    }


@app.get("/api/detect")
async def detect_endpoint(url: str) -> dict[str, Any]:
    """Fingerprint a URL's tech stack and return the preset Scrawly would apply.
    Read-only reconnaissance used by both the connect wizard and public window."""
    from sentinelseo.detect import detect_stack

    target = _normalize_target(url)
    det = await detect_stack(target)
    preset = _preset_for(det.stack, det.subcategory)
    return {"url": target, "detection": det.to_dict(), "preset": preset}


def _resolve_public_config(data: dict[str, Any], preset: dict[str, Any]) -> dict[str, Any]:
    """Build a crawl config for a public audit: saved defaults <- detected preset
    <- any per-run overrides the user tweaked in the customize panel."""
    settings = {**CRAWL_CONFIG_DEFAULTS, **_load_settings()}
    pc = preset.get("config") or {}
    if "exclude_patterns" in pc:
        settings["exclude_patterns"] = pc["exclude_patterns"]
    if "js_render" in pc:
        settings["js_render"] = pc["js_render"]
    _keys = [
        "js_render", "concurrency", "max_depth", "user_agent", "respect_robots",
        "render_sample", "include_patterns", "exclude_patterns",
        "max_pages", "max_requests_per_sec", "max_url_length",
        "max_query_params", "max_links_per_page", "max_folder_depth", "max_redirects",
        "render_timeout_s", "discover_sitemap", "sitemap_only",
    ]
    config = {k: data.get(k, settings[k]) for k in _keys}
    # Public audits are read-only recon: no enrichment that needs private keys.
    config["psi_enrich"] = False
    config["gsc_enrich"] = False
    config["psi_sample"] = 0
    config["custom_extractors"] = []
    config["custom_searches"] = []
    # Ceiling on a single quick audit. The managed edition can sit behind shared
    # infrastructure, so an anonymous submit is kept small there; the Free
    # edition runs only on the user's own machine, so the user decides.
    ceiling = PUBLIC_AUDIT_MAX_PAGES_FREE if edition.is_free() else 500
    config["max_pages"] = max(1, min(int(config.get("max_pages") or 200), ceiling))
    return config


@app.post("/api/public/audit")
async def start_public_audit(
    data: dict[str, Any], background_tasks: BackgroundTasks, request: Request
) -> dict[str, Any]:
    """Read-only deep audit of any URL — the public-window entry point. No
    WordPress connection required (this path performs no fixes), so the per-client
    audit gate doesn't apply — but a crawl is a crawl, so the same signed
    authorization + quota gate does."""
    claims = _require_crawl_authz(request)
    owner = _crawl_owner(claims)
    set_current_owner(owner)
    target = _normalize_target(str(data.get("url", "")))

    from sentinelseo.detect import detect_stack

    # Respect a stack the caller already chose in the customize panel; otherwise
    # fingerprint it now so the preset is applied automatically.
    stack = (data.get("stack") or "").strip()
    subcategory = (data.get("subcategory") or "").strip()
    detection: dict[str, Any]
    if stack:
        detection = {"stack": stack, "subcategory": subcategory, "confidence": 1.0}
    else:
        det = await detect_stack(target)
        stack, subcategory = det.stack, det.subcategory
        detection = det.to_dict()
    preset = _preset_for(stack, subcategory)
    config = _resolve_public_config(data, preset)
    # Persist the detected stack on the crawl: the agent fix prompts are rendered
    # per-platform, so a lost stack silently downgrades every prompt to generic
    # advice ("edit robots.txt") that is wrong on most frameworks.
    config["stack"] = stack
    config["subcategory"] = subcategory

    db = SessionLocal()
    public = _public_client(db)
    crawl_record = Crawl(
        client_id=public.id, target_url=target, config=config,
    )
    db.add(crawl_record)
    db.commit()
    db.refresh(crawl_record)
    crawl_id = crawl_record.id
    # Retention: the public window keeps only the latest audit. Drop older public
    # crawls now so the window always resolves to exactly this one.
    _prune_public_crawls(db, keep_id=crawl_id)
    db.commit()
    db.close()

    active_tasks[crawl_id] = {"status": "Starting...", "progress": 0}
    background_tasks.add_task(do_audit, crawl_id, target, config, owner)
    return {
        "crawl_id": crawl_id,
        "url": target,
        "detection": detection,
        "preset": {k: preset[k] for k in ("stack", "label", "subcategory_label")},
    }


def _crawl_health(db: Any, crawl_id: int) -> int | None:
    """The 0-100 composite health score for a crawl, using the same model as the
    dashboard (page-coverage of serious issues + indexability + broken pages).
    None while the crawl has no pages yet (still running / empty)."""
    from sentinelseo.audit.health import compute_health
    total = db.query(URL).filter(URL.crawl_id == crawl_id).count()
    if total == 0:
        return None
    indexable = db.query(URL).filter(
        URL.crawl_id == crawl_id, URL.indexable.is_(True)).count()
    broken = db.query(URL).filter(
        URL.crawl_id == crawl_id, URL.status >= 400).count()
    issues = db.query(Issue).filter(Issue.crawl_id == crawl_id).all()
    return compute_health(total, indexable, broken, issues)


@app.get("/api/public/latest")
def public_latest() -> dict[str, Any]:
    """The most recent public-window audit (retention keeps only one). Lets the UI
    restore the last read-only audit after the user navigates away or restarts.
    Returns ``{"crawl_id": null}`` when there's none."""
    db = SessionLocal()
    try:
        # Read-only: don't create the hidden public client just to check (that's a
        # get-or-create). No public client → no public audits yet.
        public = db.query(Client).filter(Client.is_public.is_(True)).first()
        crawl = (db.query(Crawl).filter(Crawl.client_id == public.id)
                 .order_by(Crawl.id.desc()).first()) if public else None
        if not crawl:
            return {"crawl_id": None}
        from urllib.parse import urlparse
        target = crawl.target_url or ""
        host = target
        try:
            host = urlparse(target).hostname or target
        except Exception:
            pass
        task = active_tasks.get(crawl.id)
        # "Ready" once it has produced pages; while a task is live and empty it's
        # still crawling. A finished crawl has no live task entry.
        running = bool(task) and (crawl.url_count or 0) == 0
        return {
            "crawl_id": crawl.id,
            "url": target,
            "host": host,
            "url_count": crawl.url_count or 0,
            "health_score": None if running else _crawl_health(db, crawl.id),
            "started_at": crawl.started_at.isoformat() if crawl.started_at else None,
            "running": running,
        }
    finally:
        db.close()


@app.post("/api/profiles")
def create_profile(data: dict[str, Any]) -> dict[str, Any]:
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Profile name is required.")
    db = SessionLocal()
    prof = ConfigProfile(
        name=name,
        data={**CRAWL_CONFIG_DEFAULTS, **(data.get("data") or {})},
        is_default=False,
        is_preset=False,
    )
    db.add(prof)
    db.commit()
    db.refresh(prof)
    res = _profile_public(prof)
    db.close()
    return res


@app.put("/api/profiles/{profile_id}")
def update_profile(profile_id: int, data: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    prof = db.query(ConfigProfile).filter(ConfigProfile.id == profile_id).first()
    if not prof:
        db.close()
        raise HTTPException(status_code=404, detail="Profile not found")
    if data.get("name"):
        prof.name = data["name"].strip()
    if isinstance(data.get("data"), dict):
        prof.data = {**CRAWL_CONFIG_DEFAULTS, **prof.data, **data["data"]}
    db.commit()
    db.refresh(prof)
    res = _profile_public(prof)
    db.close()
    return res


@app.post("/api/profiles/{profile_id}/default")
def set_default_profile(profile_id: int) -> dict[str, Any]:
    db = SessionLocal()
    prof = db.query(ConfigProfile).filter(ConfigProfile.id == profile_id).first()
    if not prof:
        db.close()
        raise HTTPException(status_code=404, detail="Profile not found")
    db.query(ConfigProfile).update({ConfigProfile.is_default: False})
    prof.is_default = True
    db.commit()
    db.close()
    return {"id": profile_id, "is_default": True}


@app.delete("/api/profiles/{profile_id}")
def delete_profile(profile_id: int) -> dict[str, Any]:
    db = SessionLocal()
    prof = db.query(ConfigProfile).filter(ConfigProfile.id == profile_id).first()
    if not prof:
        db.close()
        raise HTTPException(status_code=404, detail="Profile not found")
    if prof.is_preset:
        db.close()
        raise HTTPException(status_code=400, detail="Built-in presets cannot be deleted.")
    was_default = prof.is_default
    db.delete(prof)
    # If we removed the default, promote the first remaining profile.
    if was_default:
        nxt = db.query(ConfigProfile).order_by(ConfigProfile.id).first()
        if nxt:
            nxt.is_default = True
    db.commit()
    db.close()
    return {"deleted": profile_id}


@app.post("/api/audit/start")
async def start_audit(data: dict[str, Any], background_tasks: BackgroundTasks,
                      request: Request) -> dict[str, Any]:
    # Crawl gate (see web/crawl_gate.py), then scope the crawl's data.
    claims = _require_crawl_authz(request)
    owner = _crawl_owner(claims)
    set_current_owner(owner)
    client_id = data.get("client_id")
    # CRAWL_CONFIG_DEFAULTS is the floor so newer keys always resolve, even for
    # profiles/settings saved before those keys existed.
    settings = {**CRAWL_CONFIG_DEFAULTS, **_load_settings()}
    # A chosen profile is the config base; the saved defaults fill any gaps.
    profile_id = data.get("profile_id")
    if profile_id:
        pdb = SessionLocal()
        prof = pdb.query(ConfigProfile).filter(ConfigProfile.id == profile_id).first()
        pdb.close()
        if prof:
            settings = {**settings, **(prof.data or {})}
    # Per-run request fields override everything.
    # Carry the entire config surface: per-run request field wins, else the
    # resolved profile/settings value, else the default. (Adding a new key to
    # CRAWL_CONFIG_DEFAULTS makes it flow through automatically.)
    config = {k: data.get(k, settings.get(k)) for k in CRAWL_CONFIG_DEFAULTS}
    config["psi_sample"] = data.get("psi_sample", 3)

    db = SessionLocal()
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        db.close()
        raise HTTPException(status_code=404, detail="Client not found")

    # Gate: a client must be connected via *some* method before auditing. Any
    # method qualifies for read-only audit (URL-only works for any tech stack);
    # write/agentic fixes remain gated on the WordPress Connector (see fix flow).
    # The anonymous public window (POST /api/public/audit) has its own path and
    # bypasses this entirely.
    wp_connected = bool(client.wp_connection_key) or bool(
        settings.get("wp_connection_key") or os.environ.get("SCRAWLY_WP_KEY")
    )
    connected = wp_connected or bool(client.connection_method)
    if not connected:
        db.close()
        raise HTTPException(
            status_code=400,
            detail="Connect this site (choose a connection method) before auditing.",
        )

    # Carry the client's detected stack onto the crawl so agent fix prompts can
    # be rendered for the right platform (see _resolve_stack).
    config["stack"] = str((client.detected_stack or {}).get("stack") or "")
    config["subcategory"] = str((client.detected_stack or {}).get("subcategory") or "")

    crawl_record = Crawl(client_id=client.id, target_url=client.base_url, config=config)
    db.add(crawl_record)
    db.commit()
    db.refresh(crawl_record)

    active_tasks[crawl_record.id] = {"status": "Starting...", "progress": 0}
    background_tasks.add_task(do_audit, crawl_record.id, client.base_url,
                             crawl_record.config, owner)

    db.close()
    return {"crawl_id": crawl_record.id, "message": "Audit started"}

@app.get("/api/audit/status/{crawl_id}")
def get_audit_status(crawl_id: int) -> dict[str, Any]:
    import time as _time
    status = dict(active_tasks.get(crawl_id, {"status": "Unknown", "progress": 0}))
    # Snapshot mutable telemetry (mutated by the crawl worker on another thread)
    # into private copies so JSON serialization can't race with a live crawl.
    for _k, _v in list(status.items()):
        if isinstance(_v, list):
            status[_k] = list(_v)
        elif isinstance(_v, dict):
            status[_k] = dict(_v)
    started = status.pop("started_at", None)
    if started:
        elapsed = max(0.001, _time.time() - started)
        status["elapsed_s"] = round(elapsed, 1)
        status["pages_per_sec"] = round((status.get("crawled", 0) or 0) / elapsed, 2)
    return status

@app.get("/api/crawls")
def get_crawls(include_public: bool = False) -> list[dict[str, Any]]:
    db = SessionLocal()
    crawls = db.query(Crawl).order_by(Crawl.id.desc()).all()
    clients = {c.id: c for c in db.query(Client).all()}
    res = []
    for c in crawls:
        client = clients.get(c.client_id)
        is_public = bool(client and client.is_public)
        if is_public and not include_public:
            continue  # anonymous public-window audits are hidden from the agency list
        res.append({
            "id": c.id,
            "client_id": c.client_id,
            "client_name": "Public audit" if is_public else (client.name if client else "Unknown"),
            "base_url": c.target_url or (client.base_url if client else ""),
            "target_url": c.target_url or "",
            "public": is_public,
            "started_at": c.started_at,
            "url_count": c.url_count,
        })
    db.close()
    return res

# Map a check's domain letter (first char of check_id) to a coarse UI category
# used by the Issues Hub filter rail.
_CATEGORY_BY_LETTER = {
    **dict.fromkeys("ABCKL", "Indexability"),
    **dict.fromkeys("DEIJ", "Content & Meta"),
    **dict.fromkeys("FGTU", "Links"),
    **dict.fromkeys("NOMQPH", "Performance"),
    **dict.fromkeys("RSVW", "GEO & Config"),
}


def _category_for(check_id: str) -> str:
    return _CATEGORY_BY_LETTER.get(check_id[:1].upper(), "Other")


def _url_template(url: str) -> str:
    """Cluster a URL into a template pattern (FR-A3): numeric ids -> {id},
    4-digit years -> {year}, long hex/slugs -> {slug}."""
    import re as _re
    from urllib.parse import urlparse

    segs = []
    for s in urlparse(url).path.strip("/").split("/"):
        if not s:
            continue
        if s.isdigit():
            segs.append("{year}" if _re.fullmatch(r"\d{4}", s) else "{id}")
        elif _re.fullmatch(r"[0-9a-f]{8,}", s):
            segs.append("{id}")
        elif "-" in s and len(s) > 12:
            segs.append("{slug}")
        else:
            segs.append(s)
    return "/" + "/".join(segs) if segs else "/"


_SEVERITY_ORDER = ["Critical", "High", "Medium", "Low", "Info"]


@app.get("/api/dashboard/{crawl_id}")
def get_dashboard(crawl_id: int) -> dict[str, Any]:
    """Compact, chart-ready aggregation for the crawl dashboard.

    One server-side call replaces the client fetching every URL row and
    recomputing tiles/charts. Also serves as the AI assistant's context digest
    (Milestone D). All counts are derived from the persisted URL + Issue rows.
    """
    db = SessionLocal()
    try:
        crawl = db.query(Crawl).filter(Crawl.id == crawl_id).first()
        urls = db.query(URL).filter(URL.crawl_id == crawl_id).all()
        issues = db.query(Issue).filter(Issue.crawl_id == crawl_id).all()

        total = len(urls)
        indexable = sum(1 for u in urls if u.indexable)
        non_indexable = total - indexable

        status_classes = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "other": 0}
        depth_counts: dict[int, int] = {}
        segment_counts: dict[str, int] = {}
        reason_counts: dict[str, int] = {}
        broken = 0
        depth_sum = 0
        depth_n = 0
        word_sum = 0
        word_n = 0
        thin_pages = 0
        read_sum = 0.0
        read_n = 0
        lcp_sum = 0.0
        lcp_n = 0
        cls_sum = 0.0
        cls_n = 0
        for u in urls:
            st = u.status or 0
            if 200 <= st < 300:
                status_classes["2xx"] += 1
            elif 300 <= st < 400:
                status_classes["3xx"] += 1
            elif 400 <= st < 500:
                status_classes["4xx"] += 1
                broken += 1
            elif st >= 500:
                status_classes["5xx"] += 1
                broken += 1
            else:
                status_classes["other"] += 1
            if u.depth is not None:
                depth_counts[u.depth] = depth_counts.get(u.depth, 0) + 1
                depth_sum += u.depth
                depth_n += 1
            seg = getattr(u, "segment", None)
            if seg:
                segment_counts[seg] = segment_counts.get(seg, 0) + 1
            # Content stats — only meaningful for indexable HTML pages (2xx).
            if u.indexable and 200 <= st < 300:
                wc = u.word_count or 0
                word_sum += wc
                word_n += 1
                if wc < 200:
                    thin_pages += 1
            if not u.indexable:
                reason = (u.indexability_reason or "Non-indexable").strip() or "Non-indexable"
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            if u.readability is not None:
                read_sum += u.readability
                read_n += 1
            if u.lcp_s is not None:
                lcp_sum += u.lcp_s
                lcp_n += 1
            if u.cls is not None:
                cls_sum += u.cls
                cls_n += 1

        # Issue rows are already one per check_id per crawl (grouped at persist
        # time), so a straight tally reflects distinct findings.
        severity: dict[str, int] = dict.fromkeys(_SEVERITY_ORDER, 0)
        category_counts: dict[str, int] = {}
        tiers: dict[str, int] = {"AUTO": 0, "REVIEW": 0, "FLAG": 0}
        for i in issues:
            if i.severity in severity:
                severity[i.severity] += 1
            cat = _category_for(i.check_id)
            category_counts[cat] = category_counts.get(cat, 0) + 1
            if i.tier in tiers:
                tiers[i.tier] += 1

        avg_depth = round(depth_sum / depth_n, 1) if depth_n else 0.0
        indexable_ratio = (indexable / total) if total else 0.0

        # Composite health (0-100) — page-coverage model shared with the report.
        from sentinelseo.audit.health import compute_health
        health = compute_health(total, indexable, broken, issues)

        depth_hist = [{"depth": d, "count": depth_counts[d]} for d in sorted(depth_counts)]
        segments = [
            {"name": k, "count": v}
            for k, v in sorted(segment_counts.items(), key=lambda kv: kv[1], reverse=True)
        ]
        categories = [
            {"category": k, "count": v}
            for k, v in sorted(category_counts.items(), key=lambda kv: kv[1], reverse=True)
        ]
        indexability_reasons = [
            {"reason": k, "count": v}
            for k, v in sorted(reason_counts.items(), key=lambda kv: kv[1], reverse=True)
        ]

        return {
            "crawl_id": crawl_id,
            "target_url": (crawl.target_url if crawl else "") or "",
            "started_at": crawl.started_at.isoformat() if crawl and crawl.started_at else None,
            "health_score": health,
            "totals": {
                "urls": total,
                "indexable": indexable,
                "non_indexable": non_indexable,
                "broken": broken,
                "redirects": status_classes["3xx"],
                "avg_depth": avg_depth,
                "issues": len(issues),
            },
            "indexable_pct": round(indexable_ratio * 100),
            "status_classes": status_classes,
            "severity": severity,
            "tiers": tiers,
            "issue_categories": categories,
            "segments": segments,
            "depth_histogram": depth_hist,
            "indexability_reasons": indexability_reasons,
            "content": {
                "avg_words": round(word_sum / word_n) if word_n else 0,
                "thin_pages": thin_pages,
                "avg_readability": round(read_sum / read_n, 1) if read_n else None,
            },
            "cwv": {
                "avg_lcp_s": round(lcp_sum / lcp_n, 2) if lcp_n else None,
                "avg_cls": round(cls_sum / cls_n, 3) if cls_n else None,
                "samples": lcp_n,
            },
        }
    finally:
        db.close()


@app.get("/api/issues/{crawl_id}")
def get_issues(crawl_id: int) -> list[dict[str, Any]]:
    db = SessionLocal()
    issues = db.query(Issue).filter(Issue.crawl_id == crawl_id).all()

    # Checks are autoloaded at boot; call is idempotent (belt and suspenders).
    load_all_checks()
    from sentinelseo.checks.registry import get_all_checks
    all_checks = get_all_checks()
    site_level_checks = get_site_level_checks()

    res: dict[str, dict[str, Any]] = {}
    for issue in issues:
        if issue.check_id not in res:
            spec = None
            if issue.check_id in all_checks:
                spec = all_checks[issue.check_id][0]
            elif issue.check_id in site_level_checks:
                spec = site_level_checks[issue.check_id][0]

            # Prefer the rationale/fix stored with the finding; fall back to spec.
            why = issue.why_it_matters or (spec.why_it_matters if spec else None)
            fix = issue.recommended_fix or (
                getattr(spec, "fix_template", None) if spec else None
            )
            res[issue.check_id] = {
                "id": issue.id,
                "check_id": issue.check_id,
                "title": spec.title if spec else issue.check_id,
                "domain": spec.domain if spec else "Other",
                "category": _category_for(issue.check_id),
                "severity": issue.severity,
                "tier": issue.tier,
                "status": issue.status,
                "affected_url_ids": list(issue.affected_url_ids)
                if issue.affected_url_ids
                else [],
                "why_it_matters": why or "No rationale provided.",
                "recommended_fix": fix or "",
                "evidence": issue.evidence or {},
            }
        elif issue.affected_url_ids:
            merged = set(res[issue.check_id]["affected_url_ids"]) | set(
                issue.affected_url_ids
            )
            res[issue.check_id]["affected_url_ids"] = list(merged)

    db.close()
    return list(res.values())

@app.get("/api/urls/{crawl_id}")
def get_urls(crawl_id: int) -> list[dict[str, Any]]:
    db = SessionLocal()
    urls = db.query(URL).filter(URL.crawl_id == crawl_id).all()
    res = []
    for u in urls:
        res.append({
            "id": u.id,
            "address": u.address,
            "status": u.status,
            "title": u.title,
            "meta_desc": u.meta_desc,
            "canonical": u.canonical,
            "indexable": u.indexable,
            "indexability_reason": u.indexability_reason,
            "pdf_properties": u.pdf_properties or None,
            "segment": u.segment or None,
            "ga4": u.ga4 or None,
            "spelling": u.spelling or None,
            "js_errors": u.js_errors or None,
            "word_count": u.word_count,
            "readability": u.readability,
            "text_to_code": u.text_to_code,
            "forms_count": u.forms_count,
            "microdata_types": u.microdata_types or [],
            "rdfa_types": u.rdfa_types or [],
            "last_modified": u.last_modified,
            "custom_data": u.custom_data or {},
            "prev_url": u.prev_url,
            "next_url": u.next_url,
            "amp_url": u.amp_url,
            "mobile_alternate": u.mobile_alternate,
            "cookies": u.cookies or [],
            "pagerank": u.pagerank,
            "depth": u.depth,
            "lcp_s": u.lcp_s,
            "cls": u.cls,
            "inp_ms": u.inp_ms,
            "gsc_impressions": u.gsc_impressions,
            "gsc_clicks": u.gsc_clicks,
            "redirect_chain": u.redirect_chain or [],
            "render_diff": u.render_diff or [],
            "inlink_count": u.inlink_count,
            "outlink_count": u.outlink_count,
            "meta_robots": u.meta_robots,
            "x_robots": u.x_robots,
            "h1": u.h1,
            "h2": u.h2,
            "images": u.images,
            "jsonld": u.jsonld,
            "internal_links": u.internal_links or [],
        })
    db.close()
    return res


@app.get("/api/screenshot")
async def screenshot(url: str, device: str = "desktop") -> Response:
    """Render a page on demand and return a PNG (desktop or mobile preset)."""
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="A valid http(s) URL is required.")
    if device not in ("desktop", "mobile"):
        device = "desktop"
    timeout_s = float(_load_settings().get("render_timeout_s", 15) or 15)
    try:
        from sentinelseo.crawl.screenshot import capture_screenshot

        png = await capture_screenshot(url, device, timeout_s=timeout_s)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Render failed: {str(e)[:200]}") from e
    return Response(
        content=png, media_type="image/png", headers={"Cache-Control": "no-store"}
    )


@app.get("/api/embeddings/status")
def embeddings_status() -> dict[str, Any]:
    """Is an embeddings provider configured? (Never returns the key.)"""
    from sentinelseo.ai.embeddings import embed_config, is_configured

    cfg = embed_config(_load_settings())
    return {
        "configured": is_configured(cfg),
        "base_url": cfg.get("base_url", ""),
        "model": cfg.get("model", ""),
        "api_key_set": bool(cfg.get("api_key")),
    }


@app.get("/api/agentic/{crawl_id}")
def agentic_report(crawl_id: int) -> dict[str, Any]:
    """Origin-level Agentic Web readiness report for a crawl.

    Returns the stored report as produced by the probe engine: overall score and
    readiness level, per-category scores, and every probe with its request/
    response audit trail plus a copy-pasteable agent fix prompt. Empty (but
    well-formed) when the crawl predates the agentic pass or it could not run.
    """
    db = SessionLocal()
    crawl = db.query(Crawl).filter(Crawl.id == crawl_id).first()
    db.close()
    rep = (crawl.agentic_report if crawl else None) or {}
    if not rep:
        return {
            "available": False, "origin": "", "score": 0, "level": "",
            "level_label": "", "passed": 0, "scored": 0, "is_commerce": False,
            "categories": [], "results": [],
        }
    return {"available": True, **rep}


@app.post("/api/agentic/{crawl_id}/rerun")
async def agentic_rerun(crawl_id: int) -> dict[str, Any]:
    """Re-probe the origin without re-crawling the whole site.

    The agentic surface is a handful of well-known paths, so once a user has
    acted on a prompt they should be able to re-verify in seconds rather than
    sitting through another full crawl.
    """
    db = SessionLocal()
    crawl = db.query(Crawl).filter(Crawl.id == crawl_id).first()
    if crawl is None:
        db.close()
        raise HTTPException(status_code=404, detail="Crawl not found")
    client = db.query(Client).filter(Client.id == crawl.client_id).first()
    target = crawl.target_url or (client.base_url if client else "") or ""
    # Crawls created before the stack was persisted fall back to the client's
    # detected stack, so re-running still yields platform-correct prompts.
    stack = str((crawl.config or {}).get("stack") or "")
    if not stack and client is not None:
        stack = str((client.detected_stack or {}).get("stack") or "")
    if not target:
        db.close()
        raise HTTPException(status_code=400, detail="Crawl has no target URL")

    from sentinelseo.agentic import run_agentic_audit
    _pw = None
    browser = None
    try:
        from playwright.async_api import async_playwright
        _pw = await async_playwright().start()
        from sentinelseo.crawl.browser import launch_chromium
        browser = await launch_chromium(_pw, headless=True)
    except Exception:
        browser = None
    try:
        rep = await run_agentic_audit(target, browser=browser, stack=stack)
        crawl.agentic_report = rep.to_dict()
        db.commit()
        out = crawl.agentic_report
    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        if _pw is not None:
            try:
                await _pw.stop()
            except Exception:
                pass
        db.close()
    return {"available": True, **out}


@app.get("/api/prompt/{crawl_id}/{issue_id}")
def issue_fix_prompt(crawl_id: int, issue_id: int) -> dict[str, Any]:
    """Copy-pasteable agent fix prompt for one audit finding.

    Rendered for the crawl's detected stack, so the prompt names the file the
    agent should actually edit on that platform.
    """
    from sentinelseo.checks import load_all_checks
    from sentinelseo.checks.registry import get_all_checks
    from sentinelseo.prompts import build_check_prompt

    db = SessionLocal()
    try:
        issue = db.query(Issue).filter(Issue.id == issue_id).first()
        if issue is None or issue.crawl_id != crawl_id:
            raise HTTPException(status_code=404, detail="Issue not found")
        crawl = db.query(Crawl).filter(Crawl.id == crawl_id).first()
        client = (
            db.query(Client).filter(Client.id == crawl.client_id).first()
            if crawl else None
        )
        stack = str((crawl.config or {}).get("stack") or "") if crawl else ""
        if not stack and client is not None:
            stack = str((client.detected_stack or {}).get("stack") or "")
        site = (crawl.target_url if crawl else "") or (
            client.base_url if client else "")
        # Resolve the affected URLs so the prompt tells the agent exactly which
        # pages to touch rather than describing the defect in the abstract.
        ids = list(issue.affected_url_ids or [])
        urls = [
            u.address for u in
            db.query(URL).filter(URL.id.in_(ids)).all()
        ] if ids else []

        load_all_checks()
        entry = get_all_checks().get(issue.check_id)
        spec = entry[0] if entry else None
        prompt = build_check_prompt(
            issue.check_id,
            title=(spec.title if spec else issue.check_id),
            domain=(spec.domain if spec else ""),
            why_it_matters=issue.why_it_matters or (spec.why_it_matters if spec else ""),
            recommended_fix=issue.recommended_fix or "",
            severity=issue.severity or "",
            site_url=site, stack=stack,
            evidence=dict(issue.evidence or {}),
            affected_urls=urls,
        )
        if prompt is None:
            raise HTTPException(status_code=404, detail="No prompt for this check")
        return {"ok": True, **prompt.to_dict(), "affected": len(urls)}
    finally:
        db.close()


@app.get("/api/kb")
def kb_list(limit: int = 200) -> dict[str, Any]:
    """Inspect the prompt knowledge base (generated + hand-authored guidance)."""
    from sentinelseo.prompts import kb

    return {"entries": kb.entries(limit), "stats": kb.stats()}


@app.post("/api/kb")
def kb_upsert(data: dict[str, Any]) -> dict[str, Any]:
    """Hand-author or correct guidance for a (check, stack) pair.

    Stored with source='manual', which always wins over generated rows — so a
    bad generation is one edit away from being permanently overridden.
    """
    from sentinelseo.prompts import kb

    check_id = str(data.get("check_id") or "").strip()
    stack = str(data.get("stack") or "").strip()
    guidance = str(data.get("guidance") or "").strip()
    if not (check_id and stack and guidance):
        raise HTTPException(status_code=400, detail="check_id, stack and guidance required")
    if not kb.store(check_id, stack, guidance, source="manual"):
        raise HTTPException(
            status_code=400,
            detail="Guidance rejected (too short/long, or contains an unsafe command)",
        )
    return {"ok": True}


@app.delete("/api/kb/{entry_id}")
def kb_delete(entry_id: int) -> dict[str, Any]:
    from sentinelseo.prompts import kb

    if not kb.delete(entry_id):
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"ok": True}


@app.get("/api/embeddings/report/{crawl_id}")
def embeddings_report(crawl_id: int) -> dict[str, Any]:
    """Semantically-similar pairs + low-relevance pages from a crawl's embeddings
    pass (Pattern J). Empty unless the crawl ran with embeddings enabled."""
    db = SessionLocal()
    crawl = db.query(Crawl).filter(Crawl.id == crawl_id).first()
    db.close()
    rep = (crawl.embeddings_report if crawl else None) or {}
    return {
        "similar": rep.get("similar", []),
        "low_relevance": rep.get("low_relevance", []),
        "summary": {
            "similar_pairs": len(rep.get("similar", [])),
            "low_relevance": len(rep.get("low_relevance", [])),
            "ran": bool(rep),
        },
    }


@app.post("/api/embeddings/test")
def embeddings_test() -> dict[str, Any]:
    """Live probe of the configured embeddings endpoint."""
    from sentinelseo.ai.embeddings import embed_config, test_connection

    return test_connection(embed_config(_load_settings()))


@app.get("/api/auth/form/status")
def form_auth_status() -> dict[str, Any]:
    """Whether web-form login credentials are present in the environment.
    Reports that they exist — never their values."""
    from sentinelseo.crawl.form_auth import status

    return status()


@app.get("/api/spelling/status")
def spelling_status(probe: bool = False) -> dict[str, Any]:
    """Which spelling backend is usable. `?probe=true` actually calls it, so the
    UI can show a rate-limited public API honestly instead of a dead toggle."""
    from sentinelseo.enrichment.spelling import backend_available

    return backend_available(probe=probe)


@app.get("/api/backlinks/status")
def backlinks_status() -> dict[str, Any]:
    """Backlink providers, and whether the operator has connected one.

    Scrawly ships no backlink credential: every provider (Majestic / Ahrefs /
    Moz) requires the user's own paid subscription. This reports what's wired so
    the UI can offer a bring-your-own connection instead of a dead toggle.
    """
    from sentinelseo.enrichment.backlinks import providers_status

    return providers_status(_load_settings())


@app.post("/api/backlinks/test")
def backlinks_test(data: dict[str, Any]) -> dict[str, Any]:
    """Verify a user-supplied backlink credential against the live provider."""
    from sentinelseo.enrichment.backlinks import test_provider

    provider = str(data.get("provider", "")).strip().lower()
    return test_provider(provider, _load_settings())


@app.get("/api/oauth/google/start")
def oauth_google_start() -> dict[str, Any]:
    """Return the Google consent URL (GSC + GA4 in one grant)."""
    from sentinelseo.enrichment import google_oauth

    if not google_oauth.client_configured():
        raise HTTPException(
            status_code=400,
            detail="No Google OAuth client configured. Place the Cloud Console client "
                   "JSON at secrets/google_oauth_client.json (or set "
                   "SCRAWLY_GOOGLE_OAUTH_CLIENT).",
        )
    try:
        return {"auth_url": google_oauth.auth_url(), "redirect_uri": google_oauth.redirect_uri()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"OAuth start failed: {str(e)[:200]}") from e


@app.get("/api/oauth/google/callback")
def oauth_google_callback(code: str = "", state: str = "", error: str = "") -> HTMLResponse:
    """Google redirects here. Exchange the code, then tell the user to go back."""
    from sentinelseo.enrichment import google_oauth

    def _page(title: str, msg: str, ok: bool) -> HTMLResponse:
        # `title` is always a static literal; `msg` may contain HTML we build, but
        # any value derived from query params is html.escape()d at the call site.
        # A strict CSP is the belt-and-braces guard: no scripts can run here.
        body = f"""<!doctype html><meta charset="utf-8"><title>{title}</title>
        <body style="font:15px system-ui;background:#0b1220;color:#e5e7eb;display:grid;
                     place-items:center;min-height:100vh;margin:0">
          <div style="max-width:560px;padding:28px;background:#111827;
                      border:1px solid #1f2937;border-radius:14px">
            <div style="font-size:40px;text-align:center">{'✅' if ok else '⚠️'}</div>
            <h2 style="margin:10px 0 6px;text-align:center">{title}</h2>
            <div style="color:#9ca3af;line-height:1.6">{msg}</div>
            <p style="color:#6b7280;font-size:13px;text-align:center;margin-top:18px">
              You can close this tab and return to Scrawly.</p>
          </div></body>"""
        return HTMLResponse(body, headers={
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
            "X-Content-Type-Options": "nosniff",
        })

    if error:
        # access_denied on an unverified app almost always means the consent
        # screen is in Testing mode and this Google account isn't a test user —
        # a Cloud Console setting, not a broken integration. Say so.
        if "access_denied" in error:
            return _page("Google blocked the connection", """
              <p><b>Error 403: access_denied</b> — your OAuth consent screen is in
              <b>Testing</b> mode and this Google account isn't an approved tester.
              Nothing is wrong with Scrawly; this is a Cloud Console setting.</p>
              <p style="margin-top:12px"><b>Fix it one of two ways:</b></p>
              <ol style="margin:8px 0 0 18px;padding:0">
                <li style="margin-bottom:10px"><b>Add yourself as a tester</b> —
                  APIs &amp; Services → OAuth consent screen → <b>Test users</b> →
                  <b>+ ADD USERS</b> → your email → Save.
                  <br><span style="color:#f59e0b">Note: in Testing mode Google expires
                  refresh tokens after 7 days, so you'll reconnect weekly.</span></li>
                <li><b>Publish the app</b> (recommended for self-hosting) —
                  OAuth consent screen → <b>Publishing status</b> → <b>PUBLISH APP</b>.
                  You'll see a one-time "Google hasn't verified this app" warning
                  (Advanced → Go to Scrawly); tokens then don't expire. These scopes
                  are read-only and don't require Google's verification review.</li>
              </ol>""", False)
        # error/code/state are attacker-controllable query params reflected into
        # HTML — escape every dynamic value to prevent reflected XSS.
        return _page("Connection cancelled", f"Google returned: <code>{html.escape(error)}</code>", False)
    if not code:
        return _page("Missing code", "Google didn't return an authorization code.", False)
    try:
        google_oauth.exchange_code(code, state)
        return _page("Google connected", "Search Console and Analytics are now available in Scrawly.", True)
    except Exception as e:  # noqa: BLE001
        return _page("Connection failed", html.escape(str(e)[:300]), False)


@app.get("/api/oauth/google/status")
def oauth_google_status() -> dict[str, Any]:
    from sentinelseo.enrichment import google_oauth

    return google_oauth.status()


@app.post("/api/oauth/google/disconnect")
def oauth_google_disconnect() -> dict[str, Any]:
    from sentinelseo.enrichment import google_oauth

    return google_oauth.disconnect()


@app.get("/api/google/properties")
def google_properties() -> dict[str, Any]:
    """GSC sites + GA4 properties the connected Google account can read."""
    from sentinelseo.enrichment import google_oauth

    return {
        "gsc_sites": google_oauth.list_gsc_sites(),
        "ga4_properties": google_oauth.list_ga4_properties(),
    }


@app.get("/api/resources/{crawl_id}")
def get_resources(crawl_id: int) -> dict[str, Any]:
    """CSS / JS / media sub-resources discovered + HEAD-checked during the crawl,
    with per-type + broken (4xx/5xx/0) summaries for the Resources view."""
    db = SessionLocal()
    rows = db.query(Resource).filter(Resource.crawl_id == crawl_id).all()
    db.close()
    items = [{
        "url": r.url, "type": r.type, "status": r.status,
        "content_type": r.content_type, "size": r.size, "ref_count": r.ref_count,
        "broken": (r.status is not None and (r.status == 0 or r.status >= 400)),
    } for r in rows]
    summary: dict[str, Any] = {"total": len(items), "broken": sum(1 for i in items if i["broken"])}
    for t in ("css", "js", "media"):
        tv = [i for i in items if i["type"] == t]
        summary[t] = {"count": len(tv), "broken": sum(1 for i in tv if i["broken"])}
    return {"resources": items, "summary": summary}


@app.get("/api/graph/{crawl_id}")
def get_graph(crawl_id: int) -> dict[str, list[dict[str, Any]]]:
    """Nodes + edges for the site-architecture visualization.

    Edges come from each URL's persisted `internal_links` (only edges whose
    target is another crawled page are kept). Nodes carry status/indexability/
    depth so the UI can colour them.
    """
    db = SessionLocal()
    urls = db.query(URL).filter(URL.crawl_id == crawl_id).all()
    issues = db.query(Issue).filter(Issue.crawl_id == crawl_id).all()
    db.close()

    # Per-URL issue rollup (count + worst severity) so the graph can flag pages.
    sev_rank = {"Info": 1, "Low": 2, "Medium": 3, "High": 4, "Critical": 5}
    id_to_addr = {u.id: u.address for u in urls}
    node_issue: dict[str, dict[str, Any]] = {}
    for iss in issues:
        for uid in (iss.affected_url_ids or []):
            addr = id_to_addr.get(uid)
            if not addr:
                continue
            ni = node_issue.setdefault(addr, {"count": 0, "sev": "", "checks": []})
            ni["count"] += 1
            ni["checks"].append(iss.check_id)
            if sev_rank.get(iss.severity, 0) > sev_rank.get(ni["sev"], 0):
                ni["sev"] = iss.severity

    def _n(u: str) -> str:
        return (u or "").split("#")[0].rstrip("/").lower()

    by_addr = {u.address: u for u in urls}
    nodes = []
    for u in urls:
        st = u.status or 0
        ni = node_issue.get(u.address, {})
        canon = bool(u.canonical and _n(u.canonical) != _n(u.address))
        nodes.append({
            "id": u.address,
            "status": u.status,
            "indexable": bool(u.indexable),
            "depth": u.depth,
            "inlinks": u.inlink_count,
            "outlinks": u.outlink_count,
            "pagerank": u.pagerank,
            "words": u.word_count,
            "title": u.title,
            "segment": u.segment or None,
            "canonicalized": canon,
            "broken": st >= 400,
            "redirect": 300 <= st < 400,
            "orphan": (u.inlink_count or 0) == 0 and (u.depth or 0) != 0,
            "issues": ni.get("count", 0),
            "severity": ni.get("sev", ""),
            "checks": ni.get("checks", [])[:8],
        })

    edges = []
    seen: set[tuple[str, str]] = set()
    for u in urls:
        for target in (u.internal_links or []):
            if target in by_addr and target != u.address:
                key = (u.address, target)
                if key not in seen:
                    seen.add(key)
                    tgt = by_addr[target]
                    edges.append({
                        "source": u.address,
                        "target": target,
                        "broken": (tgt.status or 0) >= 400,
                    })
    return {"nodes": nodes, "edges": edges}



def _report_unavailable_page() -> HTMLResponse:
    """A friendly page for a report whose crawl no longer exists (e.g. a public
    audit that retention has replaced with a newer one), opened in its own tab."""
    html = (
        "<!doctype html><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Report unavailable</title>"
        "<style>body{margin:0;min-height:100vh;display:grid;place-items:center;"
        "font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;"
        "background:#0b0d12;color:#e5e7eb}.box{max-width:420px;text-align:center;padding:32px}"
        "h1{font-size:20px;margin:0 0 8px}p{color:#9aa4b2;line-height:1.6;margin:0}"
        ".mk{width:44px;height:44px;border-radius:12px;margin:0 auto 16px;"
        "background:linear-gradient(135deg,#6366f1,#a855f7)}</style>"
        "<div class='box'><div class='mk'></div>"
        "<h1>This report is no longer available</h1>"
        "<p>The audit it was built from has been replaced by a newer one. "
        "Run the audit again to get a fresh report.</p></div>"
    )
    return HTMLResponse(content=html, status_code=404)


@app.get("/api/report/{crawl_id}", response_class=HTMLResponse)
def get_report(crawl_id: int) -> HTMLResponse:
    from sentinelseo.report.generator import ReportGenerator
    db = SessionLocal()
    exists = db.query(Crawl).filter(Crawl.id == crawl_id).first() is not None
    db.close()
    if not exists:
        return _report_unavailable_page()
    try:
        generator = ReportGenerator()
        return generator.generate_html(crawl_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/report/{crawl_id}/pdf")
async def get_report_pdf(crawl_id: int) -> Response:
    """The same audit report as a downloadable PDF. Rendered from the report HTML
    with the crawler's own Chromium (already installed), so it looks identical to
    the on-screen report. The desktop app saves this via a native file dialog; a
    browser downloads it directly."""
    from urllib.parse import urlparse

    from sentinelseo.report.generator import ReportGenerator
    db = SessionLocal()
    crawl = db.query(Crawl).filter(Crawl.id == crawl_id).first()
    host = ""
    if crawl:
        client = db.query(Client).filter(Client.id == crawl.client_id).first()
        target = crawl.target_url or (client.base_url if client else "") or ""
        try:
            host = (urlparse(target).hostname or "").replace("www.", "")
        except Exception:
            host = ""
    db.close()
    if not crawl:
        raise HTTPException(status_code=404, detail=f"Crawl {crawl_id} not found.")
    try:
        html = ReportGenerator().generate_html(crawl_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    try:
        from sentinelseo.report.pdf import html_to_pdf

        pdf = await html_to_pdf(html)
    except Exception as e:  # noqa: BLE001
        log.warning("report.pdf_failed", crawl_id=crawl_id, error=str(e)[:500])
        raise HTTPException(
            status_code=500,
            detail="Could not create the PDF right now. Check your internet connection "
                   "(the first PDF may need to download a component) and try again.") from e
    fname = f"scrawly-report-{host or crawl_id}.pdf"
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": _attachment_header(fname)})


def _get_wp_fixer(client_id: int | None = None) -> Any:
    """Instantiate the WordPress fixer.

    Prefers the **Scrawly Connector plugin** using the *client's own* connection
    (each client is set up via its own wizard), then falls back to a global
    connection in settings/env, then to Application Password / JWT.
    """
    from sentinelseo.wp.connector import ScrawlyConnectorClient
    from sentinelseo.wp.fixes import WPFixer

    # 1. Per-client connection (the primary, wizard-driven path).
    if client_id is not None:
        db = SessionLocal()
        client = db.query(Client).filter(Client.id == client_id).first()
        db.close()
        if client and client.wp_connection_key:
            base = client.wp_url or client.base_url
            return WPFixer(ScrawlyConnectorClient(base, client.wp_connection_key))

    # 2. Global connection (single-site fallback).
    settings = _load_settings()
    wp_url = settings.get("wp_url") or os.environ.get("SCRAWLY_WP_URL")
    conn_key = settings.get("wp_connection_key") or os.environ.get("SCRAWLY_WP_KEY")

    if wp_url and conn_key:
        return WPFixer(ScrawlyConnectorClient(wp_url, conn_key))

    # Fallback: core REST with Application Password / JWT.
    from sentinelseo.wp.client import WPClient
    user = os.environ.get("SCRAWLY_WP_USER")
    pw = os.environ.get("SCRAWLY_WP_APP_PASS")
    if not (wp_url and user and pw and os.environ.get("SCRAWLY_ENCRYPTION_KEY")):
        raise HTTPException(
            status_code=400,
            detail="WordPress not connected. Install the Scrawly Connector plugin and "
            "paste its Site URL + Connection Key in Settings (or configure an "
            "Application Password).",
        )
    return WPFixer(WPClient(wp_url, user, pw))


@app.get("/api/wp/status")
def wp_status() -> dict[str, Any]:
    """Handshake with the connected WordPress site (Connector plugin or REST)."""
    settings = _load_settings()
    wp_url = settings.get("wp_url") or os.environ.get("SCRAWLY_WP_URL")
    conn_key = settings.get("wp_connection_key") or os.environ.get("SCRAWLY_WP_KEY")
    if not (wp_url and conn_key):
        return {"connected": False, "detail": "No Connector site URL + key configured."}
    try:
        from sentinelseo.wp.connector import ScrawlyConnectorClient
        client = ScrawlyConnectorClient(wp_url, conn_key)
        status = client.status()
        client.close()
        return {"connected": True, **status}
    except Exception as e:  # noqa: BLE001
        return {"connected": False, "detail": str(e)[:200]}


_FIX_PROMPTS: dict[str, str] = {
    "title": "Write one SEO-optimized <title> (50-60 characters, include the primary keyword, no site name padding). Return ONLY the title text.",
    "meta_desc": "Write one detailed meta description (about 160 to 320 characters) that summarizes the page and names its key products, services, people and topics, so both search engines and AI assistants understand and can recommend it. Plain, factual sentences, no keyword stuffing. Return ONLY the description.",
    "canonical": "Return the correct canonical URL for this page (usually its own clean https URL). Return ONLY the URL.",
    "anchor": "Suggest concise, descriptive anchor text (2-6 words; never 'click here'/'read more') for a link on this page. Return ONLY the anchor text.",
    "alt": "Write concise descriptive alt text for the page's main image (<=125 chars, no 'image of'). Return ONLY the alt text.",
    "robots": "Recommend the correct robots meta directive (e.g. 'index, follow'). Return ONLY the value.",
    "h1": "Write one clear, keyword-relevant H1 heading for this page. Return ONLY the heading.",
}


@app.post("/api/fix/suggest")
def fix_suggest(data: dict[str, Any]) -> dict[str, Any]:
    """Use the configured AI to generate a fix value from page context."""
    from sentinelseo.ai.provider import ai_complete, is_configured

    cfg = _ai_config()
    if not is_configured(cfg):
        raise HTTPException(
            status_code=400,
            detail="Configure an AI provider in Settings before using AI suggestions.",
        )
    field = data.get("field") or "title"
    url = data.get("url") or ""
    db = SessionLocal()
    issue = db.query(Issue).filter(Issue.id == data.get("issue_id")).first()
    row = (
        db.query(URL).filter(URL.address == url).order_by(URL.id.desc()).first()
        if url else None
    )
    db.close()

    ctx: list[str] = []
    if url:
        ctx.append(f"URL: {url}")
    if row:
        if row.title:
            ctx.append(f"Current title: {row.title}")
        if row.h1:
            ctx.append(f"H1: {', '.join(row.h1) if isinstance(row.h1, list) else row.h1}")
        if row.meta_desc:
            ctx.append(f"Current meta description: {row.meta_desc}")
        if row.word_count:
            ctx.append(f"Word count: {row.word_count}")
    if issue:
        ctx.append(
            f"SEO issue to fix: {issue.check_id} — "
            f"{issue.recommended_fix or issue.why_it_matters or ''}"
        )

    instruction = _FIX_PROMPTS.get(
        field, "Suggest the best value to resolve this SEO issue. Return ONLY the value."
    )
    system = (
        "You are an expert technical-SEO editor. Return ONLY the requested value — "
        "no preamble, no explanation, no markdown, no surrounding quotes."
    )
    try:
        suggestion = ai_complete(
            cfg, system, f"{instruction}\n\nPage context:\n" + "\n".join(ctx)
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"AI request failed: {str(e)[:200]}") from e

    suggestion = suggestion.strip().strip('"').strip("'").strip()
    return {"suggestion": suggestion, "field": field}


# --------------------------------------------------------------------------
# Agentic fix — one click dispatches an autonomous agent that fixes every
# affected page for an issue. Writable SEO-meta fixes (title/meta/canonical/
# robots) are generated by AI and written to WordPress with a rollback snapshot;
# content-level issues are returned as suggestions. Clarifying decisions are
# surfaced to the operator via the chat assistant (see the /plan question).
# --------------------------------------------------------------------------

def _issue_spec_title(check_id: str) -> str:
    from sentinelseo.checks import load_all_checks
    load_all_checks()
    from sentinelseo.checks.registry import get_all_checks
    from sentinelseo.checks.site_level.registry import get_site_level_checks
    allc = get_all_checks()
    site = get_site_level_checks()
    if check_id in allc:
        return allc[check_id][0].title
    if check_id in site:
        return site[check_id][0].title
    return check_id


# What the fix agent may do for each check. Anything not listed is advice only
# ("guidance"): the agent never guesses which field to write from an issue's
# wording, so it can't rewrite the wrong thing on a live site. apply = the
# Connector writes SEO meta (rollback captured first); suggest = content edits the
# agent proposes; ai=False means the value is computed, no AI provider needed.
_GUIDANCE_PLAN: dict[str, Any] = {"field": "", "label": "recommended action",
                                  "mode": "guidance", "ai": False}
_AGENT_PLANS: dict[str, dict[str, Any]] = {}
for _ids, _plan in (
    (("D01", "D02", "D03", "D04"),
     {"field": "title", "label": "page title", "mode": "apply", "ai": True}),
    (("D07", "D08", "D09", "D10"),
     {"field": "meta_desc", "label": "meta description", "mode": "apply", "ai": True}),
    (("C01", "C09"),
     {"field": "canonical", "label": "canonical URL", "mode": "apply", "ai": False}),
    (("H01", "H03"),
     {"field": "alt", "label": "image alt text", "mode": "suggest", "ai": True}),
    (("D12", "D14"),
     {"field": "h1", "label": "H1 heading", "mode": "suggest", "ai": True}),
    (("F05", "F06"),
     {"field": "anchor", "label": "anchor text", "mode": "suggest", "ai": True}),
):
    for _cid in _ids:
        _AGENT_PLANS[_cid] = _plan


def _fix_field_plan(check_id: str) -> dict[str, Any]:
    """The fix agent's plan for an issue, looked up by its check id."""
    return dict(_AGENT_PLANS.get((check_id or "").upper(), _GUIDANCE_PLAN))


def _self_canonical(url: str) -> str:
    """A page's own clean canonical URL: force https, drop the fragment."""
    from urllib.parse import urlparse, urlunparse
    p = urlparse(url)
    return urlunparse(("https", p.netloc, p.path or "/", "", p.query, ""))


def _agent_fix_value(cfg: dict[str, Any], field: str, row: Any, issue: Any, title: str) -> str:
    # Deterministic fixes — no AI needed, so these work with just the connector.
    if field == "robots":
        return "index, follow"
    if field == "canonical":
        return _self_canonical(row.address)

    from sentinelseo.ai.provider import ai_complete
    ctx = [f"URL: {row.address}"]
    if row.title:
        ctx.append(f"Current title: {row.title}")
    if row.h1:
        ctx.append(f"H1: {', '.join(row.h1) if isinstance(row.h1, list) else row.h1}")
    if row.meta_desc:
        ctx.append(f"Current meta description: {row.meta_desc}")
    if row.word_count:
        ctx.append(f"Word count: {row.word_count}")
    ctx.append(f"SEO issue to fix: {title} — {issue.recommended_fix or issue.why_it_matters or ''}")
    instruction = _FIX_PROMPTS.get(
        field, "Suggest the best value to resolve this SEO issue. Return ONLY the value."
    )
    system = (
        "You are an expert technical-SEO editor. Return ONLY the requested value — "
        "no preamble, no explanation, no markdown, no surrounding quotes."
    )
    val = ai_complete(cfg, system, f"{instruction}\n\nPage context:\n" + "\n".join(ctx))
    return val.strip().strip('"').strip("'").strip()


def _apply_meta_fix(db: Any, fixer: Any, issue: Any, url: str, field: str, value: str) -> int:
    """Write one guarded meta fix to WordPress (I2: snapshot → Fix row → write)."""
    post_id = fixer.client.resolve_post_id(url)
    if post_id is None:
        raise ValueError("Could not resolve a WordPress post for that URL.")
    args = {"post_id": post_id, "field": field, "new_value": value, "tier": issue.tier, "url": url}
    before = fixer.snapshot("meta", args)
    fix = Fix(
        issue_id=issue.id, check_id=issue.check_id, tier=issue.tier,
        before_state=before, after_state={}, applied_by="agent",
    )
    db.add(fix)
    db.commit()
    db.refresh(fix)
    fix_id = int(fix.id)
    token = fixer.commit_write(before)  # may raise → caller records the failure
    fix.before_state = token
    fix.after_state = args
    db.commit()
    return fix_id


@app.post("/api/fix/agent/plan")
def fix_agent_plan(data: dict[str, Any]) -> dict[str, Any]:
    """Pre-flight for the fix agent: determine mode, affected pages, and whether
    a confirming decision should be asked (surfaced via the chat assistant)."""
    from sentinelseo.ai.provider import is_configured

    db = SessionLocal()
    try:
        issue = db.query(Issue).filter(Issue.id == data.get("issue_id")).first()
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
        title = _issue_spec_title(issue.check_id)
        if issue.tier == "FLAG":
            return {"ok": False, "reason": "flag",
                    "error": f"“{title}” is report-only and must be handled manually."}

        plan = _fix_field_plan(issue.check_id)
        # Deterministic fixes (canonical) need no AI; only content generation
        # (title / meta / alt / h1 / anchors) does.
        if plan["ai"] and not is_configured(_ai_config()):
            return {"ok": False, "reason": "no_ai",
                    "error": "This fix needs AI. Add an AI provider in Settings first."}

        crawl = db.query(Crawl).filter(Crawl.id == issue.crawl_id).first()
        client = db.query(Client).filter(Client.id == crawl.client_id).first() if crawl else None
        wp_connected = bool(client and client.wp_connection_key)

        ids = list(issue.affected_url_ids or [])
        rows = (
            db.query(URL).filter(URL.crawl_id == issue.crawl_id, URL.id.in_(ids)).all()
            if ids else []
        )
        count = len(rows)

        if plan["mode"] == "guidance":
            return {"ok": True, "mode": "guidance", "title": title, "count": count,
                    "recommendation": issue.recommended_fix or issue.why_it_matters
                    or "Follow the recommendation for this issue."}
        if plan["mode"] == "apply" and not wp_connected:
            return {"ok": False, "reason": "no_wp",
                    "error": "Connect this site’s WordPress (Connector plugin) to let the agent apply fixes."}
        if count == 0:
            return {"ok": False, "reason": "no_pages",
                    "error": f"“{title}” is a site-level issue with no specific pages to auto-fix."}

        if plan["mode"] == "apply":
            plural = "s" if count > 1 else ""
            options = [{"label": f"Fix all {count} page{plural}", "value": "all"}]
            if count > 1:
                options.append({"label": "Just the first page", "value": "first"})
            options.append({"label": "Cancel", "value": "cancel"})
            return {
                "ok": True, "mode": "apply", "field": plan["field"], "label": plan["label"],
                "title": title, "count": count, "needs_confirm": True,
                "question": (
                    f"I can auto-fix the **{plan['label']}** on **{count} page{plural}** and write "
                    f"the change straight to WordPress. A rollback snapshot is saved first. "
                    f"How should I proceed?"
                ),
                "options": options,
            }
        # suggest mode — no live write, so no confirmation is needed.
        return {"ok": True, "mode": "suggest", "field": plan["field"], "label": plan["label"],
                "title": title, "count": count, "needs_confirm": False}
    finally:
        db.close()


@app.post("/api/fix/agent/run")
def fix_agent_run(data: dict[str, Any]) -> StreamingResponse:
    """Run the fix agent, streaming per-page progress (SSE). Body:
    {issue_id, scope: "all"|"first"|[url_ids]}."""
    from sentinelseo.ai.provider import is_configured

    def _sse(payload: dict[str, Any]) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def _gen() -> Any:
        db = SessionLocal()
        try:
            issue = db.query(Issue).filter(Issue.id == data.get("issue_id")).first()
            if not issue:
                yield _sse({"stage": "error", "detail": "Issue not found."})
                return
            if issue.tier == "FLAG":
                yield _sse({"stage": "error", "detail": "FLAG-tier issues are manual only."})
                return

            title = _issue_spec_title(issue.check_id)
            plan = _fix_field_plan(issue.check_id)
            if plan["mode"] == "guidance":
                yield _sse({"stage": "error", "detail": "This issue needs a manual change."})
                return
            # Live writes need an explicit confirmation from the person (Invariant I3),
            # enforced here, not only in the UI.
            if plan["mode"] == "apply" and data.get("confirm") is not True:
                yield _sse({"stage": "error", "detail": "Please confirm before changing the live site."})
                return
            cfg = _ai_config()
            if plan["ai"] and not is_configured(cfg):
                yield _sse({"stage": "error", "detail": "This fix needs an AI provider (Settings)."})
                return
            crawl = db.query(Crawl).filter(Crawl.id == issue.crawl_id).first()
            client_id = crawl.client_id if crawl else None

            ids = list(issue.affected_url_ids or [])
            rows = db.query(URL).filter(URL.crawl_id == issue.crawl_id, URL.id.in_(ids)).all()
            by_id = {r.id: r for r in rows}
            scope = data.get("scope", "all")
            if scope == "first":
                targets = rows[:1]
            elif isinstance(scope, list):
                sel = set(scope)
                targets = [by_id[i] for i in sel if i in by_id]
            else:
                targets = rows
            if not targets:
                yield _sse({"stage": "error", "detail": "No pages to fix."})
                return

            fixer = None
            if plan["mode"] == "apply":
                try:
                    fixer = _get_wp_fixer(client_id)
                except HTTPException as e:
                    yield _sse({"stage": "error", "detail": str(e.detail)})
                    return

            total = len(targets)
            yield _sse({"stage": "start", "total": total, "mode": plan["mode"], "label": plan["label"]})
            applied = suggested = failed = 0
            results: list[dict[str, Any]] = []
            for i, row in enumerate(targets, 1):
                yield _sse({"stage": "progress", "i": i, "total": total, "url": row.address, "state": "working"})
                try:
                    value = _agent_fix_value(cfg, plan["field"], row, issue, title)
                    if plan["mode"] == "apply":
                        fix_id = _apply_meta_fix(db, fixer, issue, row.address, plan["field"], value)
                        applied += 1
                        results.append({"url": row.address, "value": value, "fix_id": fix_id})
                        yield _sse({"stage": "progress", "i": i, "total": total, "url": row.address,
                                    "state": "applied", "value": value})
                    else:
                        suggested += 1
                        results.append({"url": row.address, "value": value})
                        yield _sse({"stage": "progress", "i": i, "total": total, "url": row.address,
                                    "state": "suggested", "value": value})
                except Exception as e:  # noqa: BLE001
                    failed += 1
                    yield _sse({"stage": "progress", "i": i, "total": total, "url": row.address,
                                "state": "failed", "detail": str(e)[:140]})
            if applied:
                issue.status = "fixed"
                db.commit()
            yield _sse({"stage": "done", "mode": plan["mode"], "applied": applied,
                        "suggested": suggested, "failed": failed, "results": results[:50]})
        finally:
            db.close()

    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.get("/api/fixes/{crawl_id}")
def get_fixes(crawl_id: int) -> dict[str, Any]:
    """Every fix the agent has applied to this crawl's issues — surfaced on the
    Fix button (Fixed state), a dashboard widget and the report."""
    db = SessionLocal()
    try:
        issue_ids = [i.id for i in db.query(Issue.id).filter(Issue.crawl_id == crawl_id)]
        if not issue_ids:
            return {"fixes": [], "count": 0, "by_issue": {}}
        fixes = (
            db.query(Fix).filter(Fix.issue_id.in_(issue_ids)).order_by(Fix.id.desc()).all()
        )
        out: list[dict[str, Any]] = []
        by_issue: dict[int, int] = {}
        for f in fixes:
            after = f.after_state or {}
            if not f.reverted:
                by_issue[f.issue_id] = by_issue.get(f.issue_id, 0) + 1
            out.append({
                "id": f.id,
                "issue_id": f.issue_id,
                "check_id": f.check_id,
                "title": _issue_spec_title(f.check_id),
                "field": after.get("field"),
                "value": after.get("new_value"),
                "url": after.get("url"),
                "applied_at": f.applied_at.isoformat() if f.applied_at else None,
                "applied_by": f.applied_by,
                "reverted": bool(f.reverted),
            })
        return {"fixes": out, "count": sum(by_issue.values()), "by_issue": by_issue}
    finally:
        db.close()


@app.post("/api/fix/apply")
def apply_issue_fix(data: dict[str, Any]) -> dict[str, Any]:
    """Apply a guarded meta fix to a WordPress post (I2/I3 enforced)."""
    from sentinelseo.ai.provider import is_configured

    # Gate: fixes require the operator to have connected an AI provider.
    if not is_configured(_ai_config()):
        raise HTTPException(
            status_code=400,
            detail="Connect an AI provider in Settings before applying fixes.",
        )
    if not data.get("confirm"):
        raise HTTPException(status_code=400, detail="confirm=true is required.")
    db = SessionLocal()
    issue = db.query(Issue).filter(Issue.id == data.get("issue_id")).first()
    if not issue:
        db.close()
        raise HTTPException(status_code=404, detail="Issue not found")
    if issue.tier == "FLAG":  # I3 — report-only, never auto
        db.close()
        raise HTTPException(status_code=403, detail="FLAG-tier issues are manual only.")

    # Route the fix through the owning client's connection.
    crawl = db.query(Crawl).filter(Crawl.id == issue.crawl_id).first()
    client_id = crawl.client_id if crawl else None

    try:
        fixer = _get_wp_fixer(client_id)
    except HTTPException:
        db.close()
        raise

    post_id = (
        fixer.client.resolve_post_id(data["url"]) if data.get("url") else None
    )
    if post_id is None:
        db.close()
        raise HTTPException(
            status_code=400, detail="Could not resolve a WordPress post for that URL."
        )

    args = {
        "post_id": post_id,
        "field": data.get("field", "title"),
        "new_value": data.get("new_value", ""),
        "tier": issue.tier,
        "url": data.get("url"),   # shown in the fix history / Undo list
    }
    # I2 — persist the rollback record before the write.
    before = fixer.snapshot("meta", args)
    fix = Fix(
        issue_id=issue.id, check_id=issue.check_id, tier=issue.tier,
        before_state=before, after_state={}, applied_by="ui",
    )
    db.add(fix)
    db.commit()
    db.refresh(fix)
    fix_id = fix.id
    try:
        token = fixer.commit_write(before)
    except Exception as e:
        issue.status = "failed"
        db.commit()
        db.close()
        raise HTTPException(
            status_code=500,
            detail=f"Write failed; rollback record preserved (fix_id={fix_id}).",
        ) from e

    fix.before_state = token
    fix.after_state = args
    issue.status = "fixed"
    db.commit()
    db.close()
    return {"status": "success", "fix_id": fix_id, "rollback_token": token}


@app.post("/api/fix/revert")
def revert_issue_fix(data: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        fix = db.query(Fix).filter(Fix.id == data.get("fix_id")).first()
        if not fix:
            raise HTTPException(status_code=404, detail="Fix record not found")
        if fix.reverted:
            return {"status": "already_reverted"}
        # Revert on the same site the fix was written to: the issue's crawl knows
        # its client, whose own Connector made the write (Invariant I2).
        issue = db.query(Issue).filter(Issue.id == fix.issue_id).first()
        crawl = db.query(Crawl).filter(Crawl.id == issue.crawl_id).first() if issue else None
        fixer = _get_wp_fixer(crawl.client_id if crawl else None)
        fix_type = "redirect" if "redirect_id" in (fix.before_state or {}) else "meta"
        ok = fixer.revert_fix(fix_type, fix.before_state)
        if ok:
            fix.reverted = True
            if issue:
                issue.status = "open"
            db.commit()
        return {"status": "success", "reverted": ok}
    finally:
        db.close()


@app.get("/api/export/{crawl_id}")
def export_issues(crawl_id: int, format: str = "csv") -> Response:
    """Developer export (FR-R3): one row per (issue, affected URL) as CSV or JSON."""
    db = SessionLocal()
    issues = db.query(Issue).filter(Issue.crawl_id == crawl_id).all()
    url_map = {
        u.id: u.address
        for u in db.query(URL).filter(URL.crawl_id == crawl_id).all()
    }
    db.close()

    load_all_checks()
    from sentinelseo.checks.registry import get_all_checks
    all_checks = get_all_checks()
    site_checks = get_site_level_checks()

    fields = ["check_id", "title", "domain", "category", "severity", "tier",
              "url", "template", "why_it_matters", "recommended_fix"]
    rows = []
    for i in issues:
        spec = (all_checks.get(i.check_id) or site_checks.get(i.check_id) or (None,))[0]
        addrs = [url_map.get(x, "") for x in (i.affected_url_ids or [])] or [""]
        for addr in addrs:
            rows.append({
                "check_id": i.check_id,
                "title": spec.title if spec else i.check_id,
                "domain": spec.domain if spec else "",
                "category": _category_for(i.check_id),
                "severity": i.severity,
                "tier": i.tier,
                "url": addr,
                "template": _url_template(addr) if addr else "",
                "why_it_matters": i.why_it_matters or "",
                "recommended_fix": i.recommended_fix or "",
            })

    if format == "json":
        return JSONResponse(rows)

    import csv
    import io
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=scrawly_crawl_{crawl_id}.csv"},  # noqa: E501
    )


# Google's practical SERP render limits (px). Titles truncate ~580, descriptions
# ~990 on desktop; these mirror the thresholds the title/meta checks use.
SERP_TITLE_PX = 580
SERP_DESC_PX = 990


def _serp_row(url: str, title: str, description: str) -> dict[str, Any]:
    """Pixel and character measurements for one title/description, plus a simple
    'enough detail for AI' signal. Pure text measurement, no fetching."""
    from sentinelseo.checks._util import metadesc_pixel_width, pixel_width

    t, d = (title or "").strip(), (description or "").strip()
    t_px, d_px = pixel_width(t), metadesc_pixel_width(d)
    return {
        "url": url,
        "title": t,
        "description": d,
        "title_px": t_px,
        "title_chars": len(t),
        "title_truncated": t_px > SERP_TITLE_PX,
        "desc_px": d_px,
        "desc_chars": len(d),
        "desc_truncated": d_px > SERP_DESC_PX,
        "title_limit_px": SERP_TITLE_PX,
        "desc_limit_px": SERP_DESC_PX,
        # Enough context for AI assistants? A very short or empty description gives
        # an AI little to read or cite. About 120+ characters of real summary is a
        # healthy floor; empty is the worst case.
        "desc_ai_thin": len(d) < 120,
    }


@app.post("/api/serp/preview")
def serp_preview(data: dict[str, Any]) -> dict[str, Any]:
    """Measure title and description text for pixel width and truncation, and flag
    descriptions that are too thin for AI context. No crawl runs here. Accepts
    explicit rows, or a `crawl_id` to pull the snippets from a finished audit."""
    rows_in = data.get("rows")
    if not rows_in and data.get("crawl_id"):
        db = SessionLocal()
        urls = db.query(URL).filter(URL.crawl_id == int(data["crawl_id"])).all()
        db.close()
        rows_in = [
            {"url": u.address, "title": u.title or "", "description": u.meta_desc or ""}
            for u in urls
        ]
    rows = [
        _serp_row(str(r.get("url", "")), str(r.get("title", "")), str(r.get("description", "")))
        for r in (rows_in or [])
    ]
    return {
        "rows": rows,
        "summary": {
            "total": len(rows),
            "title_truncated": sum(1 for r in rows if r["title_truncated"]),
            "desc_truncated": sum(1 for r in rows if r["desc_truncated"]),
            "desc_ai_thin": sum(1 for r in rows if r["desc_ai_thin"]),
        },
    }


# --- AI title + description writer -----------------------------------------
_SERP_GEN_SYSTEM = (
    "You are an expert in SEO and AI-search optimization. You write page titles and "
    "meta descriptions that help a page rank on Google and get understood and cited "
    "by AI assistants such as ChatGPT, Perplexity and Google AI Overviews. You reply "
    "with a single JSON object and nothing else."
)


def _extract_page_text(html: str, max_chars: int = 3500) -> dict[str, str]:
    """Pull the title, meta description, main heading and readable body text from a
    page so the AI has real content to summarize."""
    from selectolax.lexbor import LexborHTMLParser

    tree = LexborHTMLParser(html or "")
    title_node = tree.css_first("title")
    h1_node = tree.css_first("h1")
    meta = ""
    for m in tree.css("meta"):
        if (m.attributes.get("name") or "").lower() == "description":
            meta = (m.attributes.get("content") or "").strip()
            break
    for tag in tree.css("script, style, noscript, nav, footer, header, template, svg"):
        tag.decompose()
    body = tree.body
    text = body.text(separator=" ", strip=True) if body else ""
    text = re.sub(r"\s+", " ", text or "")[:max_chars]
    return {
        "title": (title_node.text(strip=True) if title_node else "") or "",
        "h1": (h1_node.text(strip=True) if h1_node else "") or "",
        "meta": meta,
        "text": text,
    }


def _serp_gen_prompt(url: str, page: dict[str, str]) -> str:
    return (
        "Write a better title and meta description for this web page.\n\n"
        f"Web address: {url}\n"
        f"Current title: {page.get('title') or '(none)'}\n"
        f"Current description: {page.get('meta') or '(none)'}\n"
        f"Main heading: {page.get('h1') or '(none)'}\n"
        f"Page content:\n{page.get('text') or '(none)'}\n\n"
        "Rules:\n"
        "- title: clear and specific, ideally under 60 characters, with the main "
        "topic first. It should read well when an AI cites the page.\n"
        "- description: a detailed, factual summary of what the page offers. Name the "
        "key things on the page (products, services, people, places, topics) so an AI "
        "assistant has enough context to understand and recommend it. Write 2 to 4 "
        "plain sentences, roughly 160 to 320 characters. Do not repeat keywords.\n"
        'Reply with only this JSON: {"title": "...", "description": "..."}'
    )


def _parse_serp_json(raw: str) -> dict[str, str]:
    """Pull {title, description} out of the model's reply, tolerating code fences
    or surrounding prose."""
    s = (raw or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s).strip()
    match = re.search(r"\{.*\}", s, re.DOTALL)
    if match:
        s = match.group(0)
    try:
        obj = json.loads(s)
    except Exception:
        return {"title": "", "description": ""}
    return {
        "title": str(obj.get("title", "")).strip(),
        "description": str(obj.get("description", "")).strip(),
    }


@app.post("/api/serp/generate")
def serp_generate(data: dict[str, Any]) -> dict[str, Any]:
    """Read a page and write an SEO- and AI-friendly title + description for it.
    Fetches the URL, extracts its content, and asks the configured AI provider for
    an optimized title and an entity-rich description, then measures the result."""
    from sentinelseo.ai.provider import ai_complete, is_configured

    cfg = _ai_config()
    if not is_configured(cfg):
        raise HTTPException(status_code=400, detail={
            "code": "ai_unconfigured",
            "message": "Add your AI provider key in Settings to write titles and "
                       "descriptions with AI."})
    url = _normalize_target(str(data.get("url", "")))
    if not url:
        raise HTTPException(status_code=400, detail="A web address is required.")
    try:
        resp = httpx.get(url, timeout=20.0, follow_redirects=True,
                         headers={"User-Agent": "ScrawlyBot/1.0 (+https://scrawly.app)"})
        page = _extract_page_text(resp.text)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Could not open that page ({type(e).__name__}).") from e
    try:
        raw = ai_complete(cfg, _SERP_GEN_SYSTEM, _serp_gen_prompt(url, page), max_tokens=600)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"AI request failed: {str(e)[:200]}") from e
    parsed = _parse_serp_json(raw)
    if not parsed["title"] and not parsed["description"]:
        raise HTTPException(status_code=502,
                            detail="The AI reply could not be read. Please try again.")
    row = _serp_row(url, parsed["title"], parsed["description"])
    row["ai_generated"] = True
    return row


# Per-URL fields Compare mode diffs between two crawls, with a display label.
_COMPARE_FIELDS: list[tuple[str, str]] = [
    ("status", "Status"),
    ("title", "Title"),
    ("meta_desc", "Meta description"),
    ("canonical", "Canonical"),
    ("indexable", "Indexable"),
    ("word_count", "Word count"),
    ("segment", "Segment"),
]


def _url_diff(rows1: list[URL], rows2: list[URL]) -> dict[str, Any]:
    """SF Compare mode, URL side: what appeared, vanished, or changed between two
    crawls. `previous` = rows1, `latest` = rows2."""
    by1 = {u.address: u for u in rows1}
    by2 = {u.address: u for u in rows2}
    new = sorted(set(by2) - set(by1))
    missing = sorted(set(by1) - set(by2))

    changed: list[dict[str, Any]] = []
    for addr in sorted(set(by1) & set(by2)):
        a, b = by1[addr], by2[addr]
        deltas = []
        for field, label in _COMPARE_FIELDS:
            before, after = getattr(a, field, None), getattr(b, field, None)
            if before != after:
                deltas.append({"field": field, "label": label,
                               "before": before, "after": after})
        if deltas:
            changed.append({"address": addr, "changes": deltas})
    return {
        "new": [{"address": a, "status": by2[a].status} for a in new],
        "missing": [{"address": a, "status": by1[a].status} for a in missing],
        "changed": changed,
        "summary": {
            "previous_urls": len(rows1), "latest_urls": len(rows2),
            "new": len(new), "missing": len(missing), "changed": len(changed),
        },
    }


@app.get("/api/compare")
def compare_crawls(crawl1: int, crawl2: int) -> dict[str, Any]:
    db = SessionLocal()
    issues1 = db.query(Issue).filter(Issue.crawl_id == crawl1).all()
    issues2 = db.query(Issue).filter(Issue.crawl_id == crawl2).all()

    rows1 = db.query(URL).filter(URL.crawl_id == crawl1).all()
    rows2 = db.query(URL).filter(URL.crawl_id == crawl2).all()
    url_map1 = {u.id: u.address for u in rows1}
    url_map2 = {u.id: u.address for u in rows2}
    urls_diff = _url_diff(rows1, rows2)

    db.close()

    def make_issue_map(issues: list[Issue], url_map: dict[int, str]) -> dict[str, Issue]:
        issue_map: dict[str, Issue] = {}
        for issue in issues:
            for url_id in issue.affected_url_ids:
                addr = url_map.get(url_id, "unknown")
                key = f"{issue.check_id}:{addr}"
                issue_map[key] = issue
        return issue_map

    map1 = make_issue_map(issues1, url_map1)
    map2 = make_issue_map(issues2, url_map2)

    resolved = []
    for k in map1:
        if k not in map2:
            resolved.append(k)

    new_issues = []
    for k in map2:
        if k not in map1:
            new_issues.append(k)

    # Regressions = newly-introduced Critical/High issues (the ones worth alerting).
    regressions = [
        {"key": k, "check_id": map2[k].check_id, "severity": map2[k].severity}
        for k in new_issues
        if map2[k].severity in ("Critical", "High")
    ]

    return {
        "resolved": resolved,
        "new": new_issues,
        "regressions": regressions,
        "summary": {
            "resolved": len(resolved),
            "new": len(new_issues),
            "regressions": len(regressions),
            **urls_diff["summary"],
        },
        # URL-level diff (SF Compare mode): what appeared / vanished / changed.
        "urls": urls_diff,
    }


# --- Edition + feedback -----------------------------------------------------
def _app_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("sentinelseo")
    except PackageNotFoundError:
        return "dev"


def _attachment_header(filename: str) -> str:
    """Content-Disposition for a download. HTTP headers are latin-1, so a Unicode
    name (an IDN host like bücher.de) gets an ASCII fallback plus RFC 5987
    ``filename*`` instead of crashing the response."""
    from urllib.parse import quote

    ascii_name = filename.encode("ascii", "ignore").decode("ascii").replace('"', "") or "download"
    if ascii_name == filename:
        return f'attachment; filename="{filename}"'
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


@app.get("/api/edition")
def get_edition() -> dict[str, Any]:
    """Which edition this app runs as, plus the version for the About screen."""
    return {"edition": edition.current(), "version": _app_version()}


@app.post("/api/feedback")
async def send_feedback(data: dict[str, Any]) -> dict[str, Any]:
    """Forward an in-app improvement note to the maintainer. Relayed server-side so
    the UI never needs cross-origin access, and nothing is sent unless the user
    clicks Send."""
    message = str(data.get("message", "")).strip()[:4000]
    email = str(data.get("email", "")).strip()[:200]
    if not message:
        raise HTTPException(status_code=400, detail={
            "code": "empty", "message": "Please write a note first."})
    payload = {"message": message, "email": email,
               "edition": edition.current(), "version": _app_version()}
    unreachable = HTTPException(status_code=503, detail={
        "code": "unreachable",
        "message": "Could not reach the feedback service. You can email your note instead."})
    try:
        # Generous timeout: the receiving service may need to wake from idle.
        async with httpx.AsyncClient(timeout=httpx.Timeout(75.0, connect=20.0)) as client:
            resp = await client.post(edition.feedback_url(), json=payload)
    except httpx.HTTPError:
        log.warning("feedback.unreachable", url=edition.feedback_url())
        raise unreachable from None
    if resp.status_code == 429:
        raise HTTPException(status_code=429, detail={
            "code": "rate", "message": "Thanks! Please wait a little before sending more."})
    if resp.status_code >= 400:
        log.warning("feedback.rejected", status=resp.status_code)
        raise unreachable
    return {"ok": True, "message": "Thanks, your note was sent. We read every one."}


# --- Static UI (packaged / single-origin serving) --------------------------
# In development the Vite dev server serves the UI and proxies /api here. In a
# packaged desktop build there is no Vite: this app serves the pre-built UI from
# ui/dist so the whole product runs from one origin (uvicorn sentinelseo.web.api:app).
# Mounted LAST so every /api/* route above still wins; only unmatched paths fall
# through to the static files. A no-op when dist hasn't been built.
def _boot_script() -> str:
    """Globals the UI reads before it starts (which edition is running)."""
    script = f"window.SCRAWLY_EDITION={json.dumps(edition.current())};"
    return script


def _mount_static_ui() -> None:
    from pathlib import Path

    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles

    dist = Path(__file__).resolve().parents[3] / "ui" / "dist"
    index = dist / "index.html"
    if not (dist.is_dir() and index.exists()):
        return

    # No Vite in a packaged build, so the boot script is injected into index.html.
    boot = _boot_script()

    def _served_index() -> str:
        return index.read_text(encoding="utf-8").replace(
            "</head>", f"<script>{boot}</script></head>", 1)

    @app.get("/", response_class=HTMLResponse)
    def _index() -> str:
        return _served_index()


    app.mount("/", StaticFiles(directory=str(dist), html=True), name="ui")


_mount_static_ui()
