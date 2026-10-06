from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class Finding:
    check_id: str
    severity: str
    tier: str
    affected_urls: list[str]
    wp_object_map: dict[str, str]
    evidence: dict[str, Any]
    why_it_matters: str
    recommended_fix: str


@dataclass
class CheckSpec:
    check_id: str
    domain: str
    title: str
    description: str
    why_it_matters: str
    default_severity: str
    fix_tier: str
    data_source: str
    fix_template: Optional[str] = None


@dataclass
class CrawlContext:
    """Provides the context needed for checks to evaluate rules."""

    url: str
    title: Optional[str] = None
    url_row: Any = None
    render_diffs: list[Any] = field(default_factory=list)
    images: list[Any] = field(default_factory=list)
    structured_data: list[Any] = field(default_factory=list)
    raw_html: str = ""
    rendered_html: Optional[str] = None
    # Lazily-parsed, cached selectolax trees so DOM-level checks parse the page
    # once each (single-parse contract D07) instead of re-parsing per check.
    _dom_cache: dict[str, Any] = field(
        default_factory=dict, repr=False, compare=False
    )

    def dom(self, use_rendered: bool = False) -> Any:
        """Return a cached selectolax tree for this page.

        `dom()` parses the raw response HTML (what non-JS crawlers see);
        `dom(use_rendered=True)` parses the rendered DOM. Each is parsed once and
        cached, so multiple checks on the same page reuse one parse (D07).
        """
        from selectolax.lexbor import LexborHTMLParser

        key = "rendered" if use_rendered else "raw"
        if key not in self._dom_cache:
            html = (self.rendered_html if use_rendered else self.raw_html) or ""
            self._dom_cache[key] = LexborHTMLParser(html)
        return self._dom_cache[key]


CHECK_REGISTRY: Dict[
    str, tuple[CheckSpec, Callable[[CrawlContext], Optional[Finding]]]
] = {}


def register(
    spec: CheckSpec,
) -> Callable[
    [Callable[[CrawlContext], Optional[Finding]]],
    Callable[[CrawlContext], Optional[Finding]],
]:
    """Decorator to register a check function with its metadata."""

    def decorator(
        func: Callable[[CrawlContext], Optional[Finding]],
    ) -> Callable[[CrawlContext], Optional[Finding]]:
        CHECK_REGISTRY[spec.check_id] = (spec, func)
        return func

    return decorator


def get_all_checks() -> Dict[
    str, tuple[CheckSpec, Callable[[CrawlContext], Optional[Finding]]]
]:
    return CHECK_REGISTRY


@register(
    CheckSpec(
        check_id="D01",
        domain="On-page",
        title="Missing page title",
        description="Detects pages with no <title> element.",
        why_it_matters="No primary relevance/CTR signal.",
        default_severity="High",
        fix_tier="AUTO",
        data_source="crawl",
    )
)
def check_D01(ctx: CrawlContext) -> Optional[Finding]:
    """Check for missing page title (D01)."""
    if not ctx.title or not ctx.title.strip():
        return Finding(
            check_id="D01",
            severity="High",
            tier="AUTO",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"found_title": ctx.title},
            why_it_matters="No primary relevance/CTR signal.",
            recommended_fix="Add a descriptive <title> tag.",
        )
    return None
