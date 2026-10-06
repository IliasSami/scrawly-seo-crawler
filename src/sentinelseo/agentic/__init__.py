"""Origin-level Agentic Web readiness audit.

Answers one question: can an AI agent discover, read, authenticate against and
transact with this site? Runs against the site ROOT only (well-known paths,
response headers, DNS), so it costs a fixed ~25 requests regardless of site size.
"""
from .engine import run_agentic_audit
from .models import (
    AgenticReport,
    Category,
    CategoryScore,
    ProbeResult,
    ProbeStatus,
    Step,
    level_for,
)

__all__ = [
    "AgenticReport",
    "Category",
    "CategoryScore",
    "ProbeResult",
    "ProbeStatus",
    "Step",
    "level_for",
    "run_agentic_audit",
]
