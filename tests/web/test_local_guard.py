"""The local engine only answers this machine's own app window: other websites
can't drive it (no CORS, Host check against DNS rebinding, Origin check on
state-changing calls)."""
import pytest
from fastapi.testclient import TestClient

import sentinelseo.web.api as api
from sentinelseo.web.api import app

client = TestClient(app)


def test_app_requests_are_served() -> None:
    assert client.get("/api/edition").status_code == 200


@pytest.mark.parametrize("host", ["127.0.0.1:53480", "localhost:3000", "[::1]:8000"])
def test_loopback_hosts_allowed(host: str) -> None:
    assert client.get("/api/edition", headers={"Host": host}).status_code == 200


def test_foreign_host_is_refused() -> None:
    """DNS rebinding: attacker.example resolving to 127.0.0.1."""
    r = client.get("/api/settings", headers={"Host": "attacker-rebind.example:53480"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "forbidden_origin"


def test_cross_site_write_is_refused() -> None:
    r = client.post("/api/feedback", json={"message": "x"},
                    headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


@pytest.mark.parametrize("origin", ["null", "file://"])
def test_opaque_origin_write_is_refused(origin: str) -> None:
    r = client.put("/api/settings", json={}, headers={"Origin": origin})
    assert r.status_code == 403


def test_same_origin_write_is_allowed() -> None:
    r = client.post("/api/feedback", json={"message": "  "},
                    headers={"Origin": "http://127.0.0.1:53480", "Host": "127.0.0.1:53480"})
    assert r.status_code == 400   # reached the handler (empty note), not blocked


def test_no_cors_headers_for_other_sites() -> None:
    r = client.options("/api/settings", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "PUT"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_extra_hosts_can_be_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRAWLY_ALLOWED_HOSTS", "scrawly.lan")
    assert client.get("/api/edition", headers={"Host": "scrawly.lan:8000"}).status_code == 200


def test_host_parsing() -> None:
    assert api._host_of("127.0.0.1:8000") == "127.0.0.1"
    assert api._host_of("[::1]:8000") == "[::1]"
    assert api._host_of("LocalHost") == "localhost"
