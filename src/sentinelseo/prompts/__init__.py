"""Copy-pasteable fix prompts for the user's coding agent.

Deterministic templates rendered against a detected tech-stack profile, so the
prompt names the file the agent should actually edit on THAT platform. AI is
used only to enrich a (check, stack) pair we have no specific guidance for, and
the result is cached in the knowledge base — see `kb.py`.
"""
from dataclasses import replace
from typing import Any, Dict, List, Optional

from . import kb
from .agentic_specs import AGENTIC_SPECS
from .check_specs import FAMILIES, family_for, spec_for_check, spec_from_registry
from .engine import (
    SAFETY_CONSTRAINTS,
    FixPrompt,
    PromptContext,
    PromptSpec,
    render_prompt,
)
from .stacks import PROFILES, StackProfile, resolve_stack

__all__ = [
    "AGENTIC_SPECS",
    "FAMILIES",
    "PROFILES",
    "SAFETY_CONSTRAINTS",
    "FixPrompt",
    "PromptContext",
    "PromptSpec",
    "StackProfile",
    "build_agentic_prompt",
    "build_check_prompt",
    "family_for",
    "kb",
    "render_prompt",
    "resolve_stack",
    "spec_for_check",
    "spec_from_registry",
]


def build_agentic_prompt(
    probe_id: str,
    *,
    site_url: str = "",
    stack: str = "",
    evidence: Optional[Dict[str, Any]] = None,
    affected_urls: Optional[List[str]] = None,
) -> Optional[FixPrompt]:
    """Render the fix prompt for one agentic probe, or None if it has no spec."""
    spec = AGENTIC_SPECS.get(probe_id)
    if spec is None:
        return None
    ctx = PromptContext(
        site_url=site_url,
        stack=stack,
        evidence=evidence or {},
        affected_urls=affected_urls or [],
    )
    return render_prompt(spec, ctx)


def build_check_prompt(
    check_id: str,
    *,
    title: str = "",
    domain: str = "",
    why_it_matters: str = "",
    recommended_fix: str = "",
    severity: str = "",
    site_url: str = "",
    stack: str = "",
    evidence: Optional[Dict[str, Any]] = None,
    affected_urls: Optional[List[str]] = None,
    use_kb: bool = True,
) -> Optional[FixPrompt]:
    """Build a copy-pasteable agent prompt for any page-level check finding.

    Resolution order, most specific first:
      1. a hand-written agentic spec (the 22 origin probes), else
      2. the check's domain family, enriched by the caller-supplied finding, and
      3. any KB guidance stored for this (check, stack) pair, layered on top.

    Falls back through every layer, so a finding always gets *some* prompt —
    coverage can never silently regress to none.
    """
    spec = AGENTIC_SPECS.get(check_id)
    if spec is None:
        if title or domain:
            spec = spec_for_check(
                check_id=check_id, title=title or check_id, domain=domain,
                why_it_matters=why_it_matters, recommended_fix=recommended_fix,
                severity=severity,
            )
        else:
            spec = spec_from_registry(
                check_id, recommended_fix=recommended_fix, severity=severity)
        if spec is None:
            return None

    profile = resolve_stack(stack)
    if use_kb:
        extra = kb.lookup(check_id, profile.key)
        if extra:
            # KB guidance is platform-specific, so it leads; the family text
            # stays underneath as the general explanation.
            spec = replace(spec, body=f"{extra}\n\n{spec.body}".strip())

    return render_prompt(spec, PromptContext(
        site_url=site_url, stack=stack,
        evidence=evidence or {}, affected_urls=affected_urls or [],
    ))
