"""Scrawly Free edition.

No accounts, no sign-in, no approvals, no usage limits and no control plane:
everything runs on this machine, and every feature is available to everyone.
"""
from __future__ import annotations

import os
from typing import Literal

Edition = Literal["free", "managed"]

# Where in-app improvement notes are delivered. Public and unauthenticated;
# rate-limited on the receiving side. Override with SCRAWLY_FEEDBACK_URL.
DEFAULT_FEEDBACK_URL = "https://scrawly-control-plane.onrender.com/feedback"


def current() -> Edition:
    return "free"


def is_free() -> bool:
    return True


def feedback_url() -> str:
    """Endpoint that receives in-app feedback notes."""
    return os.getenv("SCRAWLY_FEEDBACK_URL", "").strip() or DEFAULT_FEEDBACK_URL


def apply_desktop_defaults() -> None:
    """Environment the desktop launcher needs: nothing extra in the Free edition."""
