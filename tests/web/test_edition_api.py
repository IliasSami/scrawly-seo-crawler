"""/api/edition and the /api/feedback relay (no real network: respx mocks the
receiving service)."""
import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

import sentinelseo.web.api as api
from sentinelseo import edition
from sentinelseo.web.api import app

client = TestClient(app)
FB = "https://feedback.test/notes"
# The Free-edition export pins the edition: managed-only behaviour is skipped there.
managed_only = pytest.mark.skipif(not hasattr(edition, "DEFAULT_CP_URL"),
                                  reason="managed edition only")


@pytest.fixture()
def fb_url(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("SCRAWLY_FEEDBACK_URL", FB)
    return FB


class TestEditionEndpoint:
    def test_reports_edition_and_version(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SCRAWLY_EDITION", "free")
        r = client.get("/api/edition")
        assert r.status_code == 200
        body = r.json()
        assert body["edition"] == "free"
        assert isinstance(body["version"], str) and body["version"]

    def test_boot_script_names_the_running_edition(self) -> None:
        script = api._boot_script()
        assert f"window.SCRAWLY_EDITION={json.dumps(edition.current())};" in script

class TestFeedbackRelay:
    def test_empty_note_is_rejected(self, fb_url: str) -> None:
        r = client.post("/api/feedback", json={"message": "   "})
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "empty"

    @respx.mock
    def test_note_is_forwarded(self, fb_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SCRAWLY_EDITION", "free")
        route = respx.post(fb_url).mock(return_value=httpx.Response(200, json={"ok": True}))
        r = client.post("/api/feedback", json={"message": "Love it", "email": "a@b.co"})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        sent = json.loads(route.calls.last.request.content)
        assert sent["message"] == "Love it"
        assert sent["email"] == "a@b.co"
        assert sent["edition"] == "free"
        assert "version" in sent

    @respx.mock
    def test_long_note_is_truncated(self, fb_url: str) -> None:
        route = respx.post(fb_url).mock(return_value=httpx.Response(200, json={"ok": True}))
        client.post("/api/feedback", json={"message": "x" * 10_000})
        assert len(json.loads(route.calls.last.request.content)["message"]) == 4000

    @respx.mock
    def test_rate_limit_is_passed_through(self, fb_url: str) -> None:
        respx.post(fb_url).mock(return_value=httpx.Response(429))
        r = client.post("/api/feedback", json={"message": "hi"})
        assert r.status_code == 429

    @respx.mock
    def test_unreachable_service_offers_fallback(self, fb_url: str) -> None:
        respx.post(fb_url).mock(side_effect=httpx.ConnectError("down"))
        r = client.post("/api/feedback", json={"message": "hi"})
        assert r.status_code == 503
        assert r.json()["detail"]["code"] == "unreachable"

    @respx.mock
    def test_upstream_error_maps_to_unreachable(self, fb_url: str) -> None:
        respx.post(fb_url).mock(return_value=httpx.Response(500))
        r = client.post("/api/feedback", json={"message": "hi"})
        assert r.status_code == 503
