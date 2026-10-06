"""OAuth / GA4 / embeddings / spelling / form-auth / backlinks integrations."""
from typing import Any

import pytest

from sentinelseo.ai import embeddings as emb
from sentinelseo.crawl import form_auth
from sentinelseo.enrichment import backlinks, spelling
from sentinelseo.enrichment.ga4 import match_to_urls

# ---- GA4 URL matching (Pattern M) ----


def test_ga4_matches_page_path_to_absolute_url() -> None:
    metrics = {"/blog/post": {"sessions": 10}, "/": {"sessions": 99}}
    out = match_to_urls(metrics, ["https://ex.com/blog/post", "https://ex.com/"])
    assert out["https://ex.com/blog/post"]["sessions"] == 10
    assert out["https://ex.com/"]["sessions"] == 99


def test_ga4_fuzzy_matches_trailing_slash_and_case() -> None:
    # GA4 reports "/Blog/" but the crawl found "/blog" — the classic mismatch.
    metrics = {"/blog/": {"sessions": 5}}
    assert match_to_urls(metrics, ["https://ex.com/blog"], fuzzy=True)
    assert not match_to_urls(metrics, ["https://ex.com/blog"], fuzzy=False)


def test_ga4_unmatched_url_absent_and_errors_safe() -> None:
    assert match_to_urls({"/a": {"sessions": 1}}, ["https://ex.com/zzz"]) == {}
    assert match_to_urls({"_error": "boom"}, ["https://ex.com/"]) == {}
    assert match_to_urls({}, ["https://ex.com/"]) == {}


# ---- Embeddings (Pattern J) ----


def test_embeddings_unconfigured_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("SCRAWLY_EMBED_BASE_URL", "SCRAWLY_EMBED_MODEL", "SCRAWLY_EMBED_KEY"):
        monkeypatch.delenv(k, raising=False)
    cfg = emb.embed_config({})
    assert emb.is_configured(cfg) is False
    assert emb.embed_texts(["x"], cfg) == []          # never raises into a crawl
    assert emb.test_connection(cfg)["ok"] is False


def test_embeddings_local_ollama_needs_no_key() -> None:
    cfg = {"base_url": "http://localhost:11434/v1", "model": "nomic-embed-text", "api_key": ""}
    assert emb.is_configured(cfg) is True             # key optional for local


def test_cosine_and_similarity_pairs() -> None:
    assert emb.cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert emb.cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert emb.cosine([], [1]) == 0.0
    pairs = emb.find_similar({"a": [1, 0], "b": [1, 0], "c": [0, 1]}, threshold=0.9)
    assert len(pairs) == 1 and {pairs[0]["a"], pairs[0]["b"]} == {"a", "b"}


def test_low_relevance_flags_the_topical_orphan() -> None:
    out = emb.find_low_relevance({"a": [1, 0], "b": [1, 0], "c": [0, 1]}, threshold=0.5)
    assert [o["url"] for o in out] == ["c"]


# ---- Spelling (Pattern I) ----


def test_language_normalization() -> None:
    assert spelling.normalize_language("en") == "en-US"
    assert spelling.normalize_language("en-GB") == "en-GB"
    assert spelling.normalize_language("de") == "de-DE"
    assert spelling.normalize_language(None) == "en-US"
    assert spelling.normalize_language("en", override="en-GB") == "en-GB"  # override wins


def test_spelling_backend_reported() -> None:
    b = spelling.backend_available()
    assert "installed" in b and "local_available" in b
    # local requires a REAL JRE; the public API is the fallback either way.
    assert b["local_available"] == (b["installed"] and spelling.java_available())
    assert b["mode"] in ("local", "public", "none")
    if not spelling.java_available():
        assert "rate-limited" in b["note"]      # the constraint must be stated


def test_java_detection_rejects_a_stub() -> None:
    # macOS ships a /usr/bin/java stub that exists but can't run — `which` alone
    # would wrongly select local mode and silently return zero issues.
    spelling.java_available.cache_clear()
    assert spelling.java_available() is (
        __import__("subprocess").run(["java", "-version"], capture_output=True,
                                     check=False).returncode == 0
        if __import__("shutil").which("java") else False
    )


def test_spelling_empty_text_is_noop() -> None:
    assert spelling.check_text("") == []
    assert spelling.summarize([]) == {"total": 0, "spelling": 0, "grammar": 0}


def test_backend_failure_raises_not_silently_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dead/rate-limited backend must NOT look like 'no mistakes found'."""
    class _Boom:
        def check(self, _t: str) -> list[Any]:
            raise RuntimeError("You have exceeded the rate limit")

    monkeypatch.setattr(spelling, "_tool", lambda *a, **k: _Boom())
    with pytest.raises(spelling.SpellingBackendError, match="rate limit"):
        spelling.check_text("some real text", mode="public")


# ---- Web-form auth (§12) ----


def test_form_auth_requires_all_three(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRAWLY_FORM_LOGIN_URL", "https://x/login")
    monkeypatch.setenv("SCRAWLY_FORM_USER", "u")
    monkeypatch.delenv("SCRAWLY_FORM_PASS", raising=False)
    assert form_auth.is_configured(form_auth.form_config()) is False
    monkeypatch.setenv("SCRAWLY_FORM_PASS", "p")
    assert form_auth.is_configured(form_auth.form_config()) is True


def test_form_auth_status_never_leaks_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRAWLY_FORM_LOGIN_URL", "https://x/login")
    monkeypatch.setenv("SCRAWLY_FORM_USER", "u")
    monkeypatch.setenv("SCRAWLY_FORM_PASS", "supersecret")
    st = form_auth.status()
    assert st["password_set"] is True
    assert "supersecret" not in str(st)          # I5: the value never leaves .env


def test_authenticated_crawl_avoids_destructive_links() -> None:
    import re
    joined = " ".join(form_auth.DANGEROUS_PATTERNS)
    assert "logout" in joined and "wp-admin" in joined
    # The logout URL an authed crawler would otherwise click must match.
    assert any(re.search(p, "https://x/wp-login.php?action=logout&_wpnonce=abc")
               for p in form_auth.DANGEROUS_PATTERNS)


def test_cookie_header_and_auth_detection() -> None:
    cookies: list[dict[str, Any]] = [
        {"name": "wordpress_logged_in_abc", "value": "1"}, {"name": "other", "value": "2"},
    ]
    assert form_auth.looks_authenticated(cookies) is True
    assert form_auth.cookies_to_header(cookies) == "wordpress_logged_in_abc=1; other=2"
    assert form_auth.looks_authenticated([{"name": "nope", "value": "x"}]) is False


# ---- Backlinks (Pattern L) ----


def test_backlinks_ship_unconnected(monkeypatch: pytest.MonkeyPatch) -> None:
    for p in backlinks.PROVIDERS.values():
        for k in p["env"]:
            monkeypatch.delenv(k, raising=False)
    st = backlinks.providers_status({})
    assert st["any_connected"] is False
    assert {p["id"] for p in st["providers"]} == {"moz", "ahrefs", "majestic"}
    # Each unconnected provider tells the user where to get a credential.
    assert all(p["signup"].startswith("http") for p in st["providers"])


def test_backlinks_connect_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRAWLY_MOZ_ACCESS_ID", "id")
    monkeypatch.setenv("SCRAWLY_MOZ_SECRET_KEY", "sec")
    assert backlinks.is_connected("moz", {}) is True
    assert backlinks.test_provider("nonsense", {})["ok"] is False


def test_backlinks_status_never_returns_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRAWLY_MOZ_ACCESS_ID", "SECRET_ID")
    monkeypatch.setenv("SCRAWLY_MOZ_SECRET_KEY", "SECRET_KEY")
    assert "SECRET_ID" not in str(backlinks.providers_status({}))
