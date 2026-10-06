from dataclasses import dataclass, field
from typing import Any, Optional

from sentinelseo.checks.registry import CrawlContext


@dataclass
class Thresholds:
    coverage_high: float = 0.20
    coverage_critical: float = 0.40
    # Minimum distinct affected URLs before breadth escalation applies, so tiny
    # sites don't jump severity off a single finding.
    min_affected_for_escalation: int = 5


@dataclass
class SiteContext:
    base_url: str
    pages: dict[str, CrawlContext]
    thresholds: Thresholds = field(default_factory=Thresholds)
    sitemap_files: dict[str, tuple[int, int]] = field(default_factory=dict)
    probe: dict[str, Any] = field(default_factory=dict)
    robots_txt: str = ""
    robots_txt_status: int = 200
    robots_txt_content_type: str = "text/plain"
    cert_days_valid: Optional[int] = None
    llms_txt_status: int = 404
    llms_txt_content: str = ""
    llms_txt_links: list[str] = field(default_factory=list)
    has_h1_in_llms_txt: bool = False
    # External URL -> HTTP status (from the crawler's HEAD probe of outbound links).
    external_status: dict[str, int] = field(default_factory=dict)
    # The crawl profile's config dict, so site-level checks can honor tunables
    # like near-duplicate threshold and paginated-dupe handling (SF Pattern H).
    config: dict[str, Any] = field(default_factory=dict)
