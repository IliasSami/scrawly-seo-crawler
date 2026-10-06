"""TLS certificate health for the site-level security check (M04).

Collected during site enrichment (not inside a check: checks stay pure, I6). The
crawler itself fetches with verification off so it can audit sites with broken
certificates, which is exactly why the certificate needs its own probe.
"""
from __future__ import annotations

import asyncio
import ssl
from datetime import datetime, timezone
from typing import Optional

import structlog
from cryptography import x509

log = structlog.get_logger(__name__)

# Returned when the certificate fails verification (expired, self-signed, wrong
# host name, incomplete chain): visitors' browsers would show a warning.
INVALID = -1


async def tls_cert_days(host: str, port: int = 443, timeout: float = 6.0) -> Optional[int]:
    """Days until the site's certificate expires; ``INVALID`` (-1) when browsers
    would reject it; None when it couldn't be checked (no host, unreachable)."""
    if not host:
        return None
    ctx = ssl.create_default_context()
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=ctx, server_hostname=host), timeout)
    except ssl.SSLCertVerificationError:
        return INVALID
    except (OSError, asyncio.TimeoutError, ssl.SSLError) as exc:
        log.info("tls.unchecked", host=host, error=type(exc).__name__)
        return None
    try:
        ssl_obj = writer.get_extra_info("ssl_object")
        der = ssl_obj.getpeercert(binary_form=True) if ssl_obj is not None else None
    finally:
        writer.close()
    if not der:
        return None
    cert = x509.load_der_x509_certificate(der)
    # not_valid_after_utc on cryptography >= 42; older releases only have the naive one.
    expires: datetime = (getattr(cert, "not_valid_after_utc", None)
                         or cert.not_valid_after.replace(tzinfo=timezone.utc))
    days: int = (expires - datetime.now(timezone.utc)).days
    return days
