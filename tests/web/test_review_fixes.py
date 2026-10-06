"""Regression tests for issues found by the review subagents."""
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sentinelseo.ai import embeddings as emb
from sentinelseo.crawl import form_auth
from sentinelseo.enrichment import backlinks, google_oauth, spelling
from sentinelseo.enrichment.ga4 import match_to_urls
from sentinelseo.web.api import app

client = TestClient(app)


# ---- SECURITY ----

def test_oauth_callback_escapes_reflected_error() -> None:
    """F1 — the attacker-controlled `error` param must not be reflected as raw HTML."""
    r = client.get("/api/oauth/google/callback",
                   params={"error": "<script>alert(1)</script>"})
    assert r.status_code == 200
    assert "<script>alert(1)</script>" not in r.text     # escaped
    assert "&lt;script&gt;" in r.text
    assert "Content-Security-Policy" in r.headers        # defence-in-depth


def test_oauth_state_csrf(monkeypatch: pytest.MonkeyPatch) -> None:
    """F6 — a callback whose state doesn't match the one we issued is rejected."""
    google_oauth.new_state()                              # a flow is pending
    assert google_oauth._state_ok("attacker-forged") is False
    assert google_oauth._state_ok(google_oauth._pending_state or "") is True
    # No pending state (server restarted) → accept, so the user isn't locked out.
    google_oauth._pending_state = None
    assert google_oauth._state_ok("anything") is True


def test_embeddings_key_is_env_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """F2 — base_url + key must NOT come from user-editable settings (SSRF/exfil)."""
    monkeypatch.setenv("SCRAWLY_EMBED_BASE_URL", "https://real.example/v1")
    monkeypatch.setenv("SCRAWLY_EMBED_KEY", "env-secret")
    cfg = emb.embed_config({"embed_base_url": "http://evil.example",
                            "embed_api_key": "attacker-injected"})
    assert cfg["base_url"] == "https://real.example/v1"   # settings ignored
    assert cfg["api_key"] == "env-secret"                 # never from settings


def test_backlinks_creds_env_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """F3 — backlink secrets come from env only, never persisted settings."""
    monkeypatch.setenv("SCRAWLY_MOZ_ACCESS_ID", "env-id")
    monkeypatch.setenv("SCRAWLY_MOZ_SECRET_KEY", "env-key")
    c = backlinks._creds("moz", {"scrawly_moz_access_id": "injected",
                                 "scrawly_moz_secret_key": "injected"})
    assert c["SCRAWLY_MOZ_ACCESS_ID"] == "env-id"        # settings ignored


def test_dangerous_patterns_case_insensitive() -> None:
    """F4 — denylist must catch mixed-case + non-WordPress destructive links."""
    import re
    rx = [re.compile(p, re.I) for p in form_auth.DANGEROUS_PATTERNS]

    def blocked(u: str) -> bool:
        return any(r.search(u) for r in rx)

    assert blocked("https://x/wp-login.php?action=Logout")     # mixed case
    assert blocked("https://x/user/logout")                    # Drupal
    assert blocked("https://x/node/42/delete")                 # Drupal delete
    assert blocked("https://x/signout")
    assert blocked("https://x/?do=logout")
    assert blocked("https://x/administrator/index.php")        # Joomla admin
    assert not blocked("https://x/blog/logout-tips")           # not a logout action


# ---- CORRECTNESS ----

def test_ga4_case_insensitive_both_directions() -> None:
    """C1 — matching must survive either side differing in case."""
    # GA4 preserves caps, crawl is lowercase:
    assert match_to_urls({"/About-Us": {"sessions": 7}},
                         ["https://ex.com/about-us"], fuzzy=True)
    # crawl preserves caps, GA4 lowercase:
    assert match_to_urls({"/about-us": {"sessions": 7}},
                         ["https://ex.com/About-Us"], fuzzy=True)


def test_ga4_index_html_matches_root() -> None:
    """C6 — GA4 reporting /index.html should match a crawled /."""
    out = match_to_urls({"/": {"sessions": 9}},
                        ["https://ex.com/index.html"], fuzzy=True)
    assert out.get("https://ex.com/index.html", {}).get("sessions") == 9


def test_spelling_override_is_normalized() -> None:
    """C4 — an override like 'en_gb' / 'en-gb' must normalize, not 404-silently."""
    assert spelling.normalize_language(None, "en-gb") == "en-GB"
    assert spelling.normalize_language(None, "en_GB") == "en-GB"
    assert spelling.normalize_language("zh-Hans") == "zh-CN"    # script → locale


def test_embeddings_count_mismatch_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """C5 — a provider returning the wrong vector count must not mis-align URLs."""
    cfg = {"base_url": "http://x/v1", "model": "m", "api_key": "k"}

    class _Resp:
        status_code = 200
        def json(self) -> dict[str, Any]:
            return {"data": [{"index": 0, "embedding": [1.0, 0.0]}]}   # 1 vec for 2 inputs

    monkeypatch.setattr(emb, "embed_config", lambda *a, **k: cfg)
    import httpx
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp())
    assert emb.embed_texts(["a", "b"], cfg) == []       # fail closed, not [[1,0]] mis-paired
