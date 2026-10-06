"""Builds copy-pasteable fix prompts for the user's coding agent.

The output is aimed at an agent that already has write access to the site
(via MCP, CLI, SSH or a repo checkout). A prompt is only useful if the agent can
act on it without coming back to ask questions, so every prompt carries the same
six sections:

  1. Role + stack context      — what it is working on
  2. Problem                   — the defect, with the evidence we observed
  3. Where to change it        — the concrete file/route for THIS stack
  4. Acceptance criteria       — the exact end state, testable
  5. Verification              — the command that proves it worked
  6. Constraints               — what it must not do

Prompts are generated deterministically from templates. That matters more than
it might seem: these prompts get run against production sites, so the output has
to be reproducible and reviewable, and must never contain a destructive command
an LLM improvised. AI is used only to *enrich* a template for a stack we have no
specific guidance for, and the result is cached in the knowledge base and
reviewed like any other content.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .stacks import StackProfile, resolve_stack

# Never emit a prompt that instructs an agent to do something irreversible or
# credential-touching. These are appended to every prompt.
SAFETY_CONSTRAINTS: List[str] = [
    "Make the smallest change that satisfies the acceptance criteria.",
    "Do not delete or rewrite unrelated files, routes, or configuration.",
    "Do not modify DNS, billing, user accounts, or access control unless this "
    "task explicitly requires it.",
    "Never commit secrets, API keys, or credentials.",
    "If the required change conflicts with an existing plugin, framework route, "
    "or CDN setting, stop and report the conflict instead of forcing it.",
]


@dataclass
class PromptContext:
    """Everything a prompt needs to be specific to one site."""

    site_url: str = ""
    stack: str = ""
    cms_label: str = ""
    affected_urls: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)

    @property
    def domain(self) -> str:
        m = re.match(r"https?://([^/]+)", self.site_url or "")
        return m.group(1) if m else (self.site_url or "<domain>")


@dataclass
class FixPrompt:
    """A ready-to-paste prompt plus the metadata the UI needs around it."""

    check_id: str
    title: str
    stack: str
    stack_label: str
    text: str
    acceptance: List[str] = field(default_factory=list)
    source: str = "template"      # "template" | "ai" | "kb"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "title": self.title,
            "stack": self.stack,
            "stack_label": self.stack_label,
            "text": self.text,
            "acceptance": self.acceptance,
            "source": self.source,
        }


@dataclass
class PromptSpec:
    """The stack-independent core of a fix, before it is rendered for a stack."""

    check_id: str
    title: str
    problem: str
    artefact: str                       # which stack location this touches
    acceptance: List[str]
    verify: List[str] = field(default_factory=list)
    body: str = ""                      # spec detail: the exact content to produce
    constraints: List[str] = field(default_factory=list)


def _bullets(items: List[str], marker: str = "-") -> str:
    return "\n".join(f"{marker} {i}" for i in items if i)


def _evidence_block(ctx: PromptContext, limit: int = 15) -> str:
    lines: List[str] = []
    if ctx.evidence:
        for k, v in list(ctx.evidence.items())[:8]:
            text = str(v)
            lines.append(f"- {k}: {text[:220]}")
    if ctx.affected_urls:
        shown = ctx.affected_urls[:limit]
        lines.append(f"- Affected URLs ({len(ctx.affected_urls)} total):")
        lines += [f"    {u}" for u in shown]
        if len(ctx.affected_urls) > limit:
            lines.append(f"    …and {len(ctx.affected_urls) - limit} more")
    return "\n".join(lines) or "- (no additional evidence captured)"


def render_prompt(spec: PromptSpec, ctx: PromptContext) -> FixPrompt:
    """Render one spec into a stack-specific, copy-pasteable prompt."""
    profile: StackProfile = resolve_stack(ctx.stack or ctx.cms_label)
    where = profile.location(spec.artefact)
    verify = spec.verify or profile.verify
    verify = [v.replace("<domain>", ctx.domain) for v in verify]
    constraints = spec.constraints + SAFETY_CONSTRAINTS

    parts = [
        f"You are working on {ctx.site_url or 'this website'} "
        f"(detected stack: {profile.label}).",
        "",
        f"## Task\n{spec.title}",
        "",
        f"## Problem\n{spec.problem}",
        "",
        f"## What we observed\n{_evidence_block(ctx)}",
        "",
        f"## Where to make the change ({profile.label})\n{where}",
    ]
    notes = profile.notes_for(spec.artefact)
    if notes:
        parts += ["", f"### Platform notes\n{_bullets(notes)}"]
    if spec.body:
        parts += ["", f"## Required result\n{spec.body}"]
    parts += [
        "",
        f"## Acceptance criteria\n{_bullets(spec.acceptance)}",
        "",
        "## Verify\n```bash\n" + "\n".join(verify) + "\n```",
        "",
        f"## Constraints\n{_bullets(constraints)}",
        "",
        "Report exactly which files you changed and paste the verification output.",
    ]
    return FixPrompt(
        check_id=spec.check_id,
        title=spec.title,
        stack=profile.key,
        stack_label=profile.label,
        text="\n".join(parts).strip(),
        acceptance=spec.acceptance,
        source="template",
    )
