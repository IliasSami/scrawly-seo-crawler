"""TLS certificate probe for M04 (offline: fake connections, generated cert)."""
import asyncio
import ssl
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

import sentinelseo.crawl.tls as tls
from sentinelseo.audit.context import SiteContext
from sentinelseo.checks.site_level.checks import check_L05, check_M04


def _der(days_left: int) -> bytes:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "example.test")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(1)
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=days_left, hours=1))
            .sign(key, hashes.SHA256()))
    # Typed as Any: some mypy/cryptography combinations mistype these enum members.
    der_format: Any = serialization.Encoding.DER
    der: bytes = cert.public_bytes(der_format)
    return der


class _SSLObj:
    def __init__(self, der: bytes) -> None:
        self.der = der

    def getpeercert(self, binary_form: bool = False) -> bytes:
        return self.der


class _Writer:
    def __init__(self, der: bytes) -> None:
        self.ssl_obj = _SSLObj(der)
        self.closed = False

    def get_extra_info(self, name: str) -> Any:
        return self.ssl_obj if name == "ssl_object" else None

    def close(self) -> None:
        self.closed = True


def _patch(monkeypatch: pytest.MonkeyPatch, result: Any) -> None:
    async def _open(*a: Any, **k: Any) -> Any:
        if isinstance(result, BaseException):
            raise result
        return None, result
    monkeypatch.setattr("asyncio.open_connection", _open)


def test_days_until_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = _Writer(_der(45))
    _patch(monkeypatch, writer)
    assert asyncio.run(tls.tls_cert_days("example.test")) == 45
    assert writer.closed


def test_rejected_certificate_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, ssl.SSLCertVerificationError("certificate has expired"))
    assert asyncio.run(tls.tls_cert_days("example.test")) == tls.INVALID


def test_unreachable_host_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, OSError("no route"))
    assert asyncio.run(tls.tls_cert_days("example.test")) is None
    assert asyncio.run(tls.tls_cert_days("")) is None


def _site(**kw: Any) -> SiteContext:
    return SiteContext(base_url="https://example.test/", pages={}, **kw)


def test_m04_flags_invalid_and_soon_expiring() -> None:
    assert [f.severity for f in check_M04(_site(cert_days_valid=tls.INVALID))] == ["Critical"]
    assert [f.severity for f in check_M04(_site(cert_days_valid=12))] == ["High"]
    assert list(check_M04(_site(cert_days_valid=200))) == []
    assert list(check_M04(_site(cert_days_valid=None))) == []


def test_l05_flags_robots_served_with_wrong_type() -> None:
    assert list(check_L05(_site(robots_txt_status=200, robots_txt_content_type="text/html")))
    assert not list(check_L05(_site(robots_txt_status=200,
                                     robots_txt_content_type="text/plain; charset=utf-8")))
    assert not list(check_L05(_site(robots_txt_status=404, robots_txt_content_type="text/html")))
