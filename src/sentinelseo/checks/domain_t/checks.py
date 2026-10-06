import re
from typing import Any, Optional
from urllib.parse import unquote, urlparse

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


def _basic_finding(
    ctx: CrawlContext,
    check_id: str,
    severity: str,
    why: str,
    rec: str,
    evidence: dict[str, Any],
) -> Finding:
    return Finding(
        check_id=check_id,
        severity=severity,
        tier="REVIEW",
        affected_urls=[ctx.url],
        wp_object_map={},
        evidence=evidence,
        why_it_matters=why,
        recommended_fix=rec,
    )


@register(
    CheckSpec(
        check_id="T01",
        domain="URL structure & hygiene",
        title="Uppercase characters in URL",
        description="Detects: Uppercase characters in URL",
        why_it_matters="Case-duplication risk",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_T01(ctx: CrawlContext) -> Optional[Finding]:
    parsed = urlparse(ctx.url)
    if any(c.isupper() for c in parsed.path):
        return _basic_finding(
            ctx,
            "T01",
            "Low",
            "Case-duplication risk",
            "Use lowercase URLs.",
            {"path": parsed.path},
        )
    return None


@register(
    CheckSpec(
        check_id="T02",
        domain="URL structure & hygiene",
        title="Whitespace / unsafe / non-ASCII chars",
        description="Detects: Whitespace / unsafe / non-ASCII chars",
        why_it_matters="Encoding issues",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_T02(ctx: CrawlContext) -> Optional[Finding]:
    parsed = urlparse(ctx.url)
    decoded = unquote(parsed.path)
    if re.search(r"[^a-zA-Z0-9\-._~/]", decoded):
        return _basic_finding(
            ctx,
            "T02",
            "Low",
            "Encoding issues",
            "Remove unsafe characters.",
            {"path": parsed.path},
        )
    return None


@register(
    CheckSpec(
        check_id="T03",
        domain="URL structure & hygiene",
        title="Double slashes / repetitive path segments",
        description="Detects: Double slashes / repetitive path segments",
        why_it_matters="Duplication, messy",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_T03(ctx: CrawlContext) -> Optional[Finding]:
    parsed = urlparse(ctx.url)
    if "//" in parsed.path:
        return _basic_finding(
            ctx,
            "T03",
            "Low",
            "Duplication, messy",
            "Remove double slashes.",
            {"path": parsed.path},
        )
    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) != len(set(segments)):
        return _basic_finding(
            ctx,
            "T03",
            "Low",
            "Duplication, messy",
            "Remove repetitive segments.",
            {"path": parsed.path},
        )
    return None


@register(
    CheckSpec(
        check_id="T04",
        domain="URL structure & hygiene",
        title="Excessive URL length (>~115 chars)",
        description="Detects: Excessive URL length (>~115 chars)",
        why_it_matters="Truncation, usability",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_T04(ctx: CrawlContext) -> Optional[Finding]:
    if len(ctx.url) > 115:
        return _basic_finding(
            ctx,
            "T04",
            "Low",
            "Truncation, usability",
            "Shorten URL.",
            {"length": len(ctx.url)},
        )
    return None


@register(
    CheckSpec(
        check_id="T05",
        domain="URL structure & hygiene",
        title="Session IDs / tracking params in indexable URLs",
        description="Detects: Session IDs / tracking params in indexable URLs",
        why_it_matters="Duplication",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_T05(ctx: CrawlContext) -> Optional[Finding]:
    parsed = urlparse(ctx.url)
    if any(x in parsed.query.lower() for x in ["sessionid", "sid=", "utm_", "gclid"]):
        return _basic_finding(
            ctx,
            "T05",
            "Medium",
            "Duplication",
            "Remove tracking params from indexable URLs.",
            {"query": parsed.query},
        )
    return None


@register(
    CheckSpec(
        check_id="T06",
        domain="URL structure & hygiene",
        title="Deep/over-nested path structure",
        description="Detects: Deep/over-nested path structure",
        why_it_matters="Architecture signal",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_T06(ctx: CrawlContext) -> Optional[Finding]:
    parsed = urlparse(ctx.url)
    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) > 4:
        return _basic_finding(
            ctx,
            "T06",
            "Low",
            "Architecture signal",
            "Flatten architecture.",
            {"depth": len(segments)},
        )
    return None


@register(
    CheckSpec(
        check_id="T07",
        domain="URL structure & hygiene",
        title="Non-descriptive URLs (`?p=123`)",
        description="Detects: Non-descriptive URLs (`?p=123`)",
        why_it_matters="Weak topical + AI signal",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_T07(ctx: CrawlContext) -> Optional[Finding]:
    parsed = urlparse(ctx.url)
    if "p=" in parsed.query or "page_id=" in parsed.query:
        return _basic_finding(
            ctx,
            "T07",
            "Low",
            "Weak topical + AI signal",
            "Use descriptive slugs.",
            {"query": parsed.query},
        )
    return None


@register(
    CheckSpec(
        check_id="T08",
        domain="URL structure & hygiene",
        title="Trailing-slash inconsistency (both resolve 200)",
        description="Detects: Trailing-slash inconsistency (both resolve 200)",
        why_it_matters="Duplication",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_T08(ctx: CrawlContext) -> Optional[Finding]:
    return None


@register(
    CheckSpec(
        check_id="T09",
        domain="URL structure & hygiene",
        title="Underscores instead of hyphens as word separators",
        description="Detects: Underscores instead of hyphens as word separators",
        why_it_matters="Legacy convention",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_T09(ctx: CrawlContext) -> Optional[Finding]:
    parsed = urlparse(ctx.url)
    if "_" in parsed.path:
        return _basic_finding(
            ctx,
            "T09",
            "Low",
            "Legacy convention",
            "Use hyphens.",
            {"path": parsed.path},
        )
    return None
