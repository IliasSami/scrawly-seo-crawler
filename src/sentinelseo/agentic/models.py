"""Data model for the origin-level Agentic Web audit.

Unlike the page-level check engine (which runs across every crawled URL), these
probes run ONCE per origin against well-known paths, response headers and DNS.
That keeps the whole section cheap — a full agentic audit is ~25 requests total
regardless of whether the site has 10 pages or 100,000.

Every probe records an ordered audit trail of the exact requests it made and
what it concluded from each, so a finding is always defensible: the user can see
the literal request/response that produced it rather than a bare verdict.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ProbeStatus(str, Enum):
    """Outcome of a single probe.

    PASS / FAIL score. INFO and NOT_APPLICABLE never penalise: a content site
    should not be marked down for lacking an agentic-commerce payment protocol.
    """

    PASS = "pass"
    FAIL = "fail"
    INFO = "info"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"          # probe itself could not complete (network/timeout)

    @property
    def scores(self) -> bool:
        return self in (ProbeStatus.PASS, ProbeStatus.FAIL)


class Category(str, Enum):
    DISCOVERABILITY = "discoverability"
    CONTENT = "content"
    BOT_CONTROL = "bot_control"
    API_AUTH_MCP = "api_auth_mcp"
    AGENT_RUNTIME = "agent_runtime"
    COMMERCE = "commerce"


CATEGORY_LABELS: Dict[Category, str] = {
    Category.DISCOVERABILITY: "Discoverability",
    Category.CONTENT: "Content Accessibility",
    Category.BOT_CONTROL: "Bot Access Control",
    Category.API_AUTH_MCP: "API, Auth, MCP & Skill Discovery",
    Category.AGENT_RUNTIME: "Agent Runtime & Interaction",
    Category.COMMERCE: "Agentic Commerce",
}


@dataclass
class Step:
    """One observable action inside a probe — usually an HTTP or DNS request.

    `detail` is the human-readable conclusion drawn from this step, which is what
    makes the audit trail readable rather than a raw HAR dump.
    """

    action: str                                  # "GET /robots.txt", "DoH SVCB _mcp._agents…"
    detail: str = ""                             # what this step established
    status: Optional[int] = None                 # HTTP status, when applicable
    request_headers: Dict[str, str] = field(default_factory=dict)
    response_headers: Dict[str, str] = field(default_factory=dict)
    body_excerpt: str = ""                       # truncated, never the full page
    ok: Optional[bool] = None                    # did this step find what it wanted

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "detail": self.detail,
            "status": self.status,
            "request_headers": self.request_headers,
            "response_headers": self.response_headers,
            "body_excerpt": self.body_excerpt,
            "ok": self.ok,
        }


@dataclass
class ProbeResult:
    """The verdict for one agentic capability, plus the evidence behind it."""

    probe_id: str
    title: str
    category: Category
    goal: str                                    # what good looks like
    status: ProbeStatus
    conclusion: str                              # one-line verdict
    steps: List[Step] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    remediation: str = ""                        # prose "how to implement"
    spec_urls: List[str] = field(default_factory=list)
    duration_ms: int = 0
    # Populated later by the prompt engine (kept out of the probe itself so the
    # probes stay pure and offline-testable).
    fix_prompt: str = ""

    @property
    def passed(self) -> bool:
        return self.status is ProbeStatus.PASS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "title": self.title,
            "category": self.category.value,
            "category_label": CATEGORY_LABELS[self.category],
            "goal": self.goal,
            "status": self.status.value,
            "conclusion": self.conclusion,
            "steps": [s.to_dict() for s in self.steps],
            "evidence": self.evidence,
            "remediation": self.remediation,
            "spec_urls": self.spec_urls,
            "duration_ms": self.duration_ms,
            "fix_prompt": self.fix_prompt,
        }


@dataclass
class CategoryScore:
    category: Category
    label: str
    passed: int
    total: int                                   # scoring probes only

    @property
    def score(self) -> Optional[int]:
        """0-100, or None when nothing in this category was scored."""
        if not self.total:
            return None
        return round(100 * self.passed / self.total)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "label": self.label,
            "passed": self.passed,
            "total": self.total,
            "score": self.score,
        }


# Readiness bands. A site that only answers robots.txt/sitemap is "basic web
# presence"; one exposing MCP/A2A/skills is genuinely agent-operable.
LEVELS: List[tuple[int, str, str]] = [
    (0, "Level 0", "Not agent-ready"),
    (20, "Level 1", "Basic web presence"),
    (40, "Level 2", "Agent-discoverable"),
    (60, "Level 3", "Agent-readable"),
    (80, "Level 4", "Agent-operable"),
    (95, "Level 5", "Agent-native"),
]


def level_for(score: int) -> tuple[str, str]:
    name, label = LEVELS[0][1], LEVELS[0][2]
    for threshold, n, lb in LEVELS:
        if score >= threshold:
            name, label = n, lb
    return name, label


@dataclass
class AgenticReport:
    """Whole-origin agentic readiness result."""

    origin: str
    results: List[ProbeResult] = field(default_factory=list)
    stack: str = ""                              # detected tech stack, for prompts
    is_commerce: bool = False
    duration_ms: int = 0

    @property
    def scoring_results(self) -> List[ProbeResult]:
        return [r for r in self.results if r.status.scores]

    @property
    def score(self) -> int:
        scored = self.scoring_results
        if not scored:
            return 0
        return round(100 * sum(1 for r in scored if r.passed) / len(scored))

    @property
    def category_scores(self) -> List[CategoryScore]:
        out: List[CategoryScore] = []
        for cat in Category:
            rs = [r for r in self.results if r.category is cat and r.status.scores]
            out.append(
                CategoryScore(
                    category=cat,
                    label=CATEGORY_LABELS[cat],
                    passed=sum(1 for r in rs if r.passed),
                    total=len(rs),
                )
            )
        return out

    @property
    def failures(self) -> List[ProbeResult]:
        return [r for r in self.results if r.status is ProbeStatus.FAIL]

    def to_dict(self) -> Dict[str, Any]:
        level_name, level_label = level_for(self.score)
        return {
            "origin": self.origin,
            "stack": self.stack,
            "is_commerce": self.is_commerce,
            "score": self.score,
            "level": level_name,
            "level_label": level_label,
            "passed": sum(1 for r in self.scoring_results if r.passed),
            "scored": len(self.scoring_results),
            "duration_ms": self.duration_ms,
            "categories": [c.to_dict() for c in self.category_scores],
            "results": [r.to_dict() for r in self.results],
        }
