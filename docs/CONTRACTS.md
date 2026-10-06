# Scrawly Contracts

This document defines the frozen interfaces and boundaries for the Scrawly project. Every downstream module MUST treat these contracts as immutable unless explicitly approved for change.

## 1. Data Models (SQLAlchemy)

The core tables are represented as SQLAlchemy models. They are outlined conceptually here.

- `Client`: `id`, `name`, `base_url`, `canonical_nap`, `service_cities`, `plugin_stack` (Yoast/RankMath/Redirection), `auth_ref`.
- `Crawl`: `id`, `client_id`, `started_at`, `config` (UA, depth, JS on/off), `url_count`.
- `URL`: `crawl_id`, `address`, `status`, `redirect_chain`, `title`, `meta_desc`, `canonical`, `meta_robots`, `x_robots`, `h1` through `h6`, `word_count`, `content_hash`, `near_dup_cluster`, `ttfb`, `size`, `inlink_count`, `outlink_count`, `indexable` (bool), `indexability_reason`.
- `UrlRenderDiff`: `url_id`, `element` (meta_robots|canonical|title|meta_desc|internal_links|external_links), `state` (unchanged|created|modified|duplicated|deleted).
- `Image`: `url_id`, `src`, `alt`, `size_kb`, `has_dimensions`.
- `StructuredData`: `url_id`, `type`, `format` (jsonld|microdata|rdfa), `valid`, `missing_required` (list), `missing_recommended` (list).
- `Issue`: `crawl_id`, `check_id`, `severity`, `tier`, `affected_url_ids` (list), `wp_object_id`, `evidence` (json), `status` (open|fixed|ignored).
- `Fix`: `issue_id`, `check_id`, `tier`, `applied_at`, `before_state` (json), `after_state` (json), `applied_by`, `reverted` (bool).
- `Enrichment`: `url_id`, `gsc_impressions`, `gsc_clicks`, `lcp`, `inp`, `cls`, `lighthouse_scores` (json), `agentic_pass_ratio`.

## 2. Audit Rule Engine Contracts

### Finding
The `Finding` dataclass returned by every check.

```python
from dataclasses import dataclass
from typing import Any

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
```

### CheckSpec
The `CheckSpec` dataclass declaratively holds check metadata.

```python
from dataclasses import dataclass
from typing import Optional

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
```

### Registry Protocol
Every check is a pure function that reads a `CrawlContext` and returns a `Finding` or `None`. They are registered via a `@register(CheckSpec(...))` decorator. Checks must be side-effect free and independently testable.

```python
from typing import Optional
from scrawly.checks.registry import CrawlContext, Finding, CheckSpec, register

@register(CheckSpec(
    check_id="D01",
    domain="On-page",
    title="Missing page title",
    description="Detects pages with no <title> element.",
    why_it_matters="No primary relevance/CTR signal.",
    default_severity="High",
    fix_tier="AUTO",
    data_source="crawl"
))
def check_D01(ctx: CrawlContext) -> Optional[Finding]:
    ...
```

## 3. MCP Tool Signatures (FastMCP)

The orchestration layer interfaces with the system via these exact MCP tool signatures.

| Tool | Arguments | Returns | Mutating |
|---|---|---|---|
| `crawl_site` | `url: str`, `depth: int`, `render: bool`, `ua: str` | `tuple[str, dict]` (crawl_id, summary) | no |
| `get_issues` | `crawl_id: str`, `severity: Optional[str]`, `tier: Optional[str]`, `domain: Optional[str]` | `list[dict]` (issues) | no |
| `get_page_detail` | `url: str` | `dict` (full url record + render diff) | no |
| `run_lighthouse` | `url: str`, `categories: list[str]` | `dict` (scores + agentic pass ratio) | no |
| `check_ai_access` | `url: str` | `dict` (per-UA allow/block matrix) | no |
| `propose_fix` | `issue_id: str` | `dict` (proposed change + tier + before-state preview) | no |
| `apply_fix` | `fix_id: str`, **`confirm: bool`** | `dict` (result + rollback token) | **yes** |
| `create_redirect` | `from_url: str`, `to_url: str`, `type: int = 301` | `dict` (result) | **yes** |
| `revert` | `fix_id: str` | `dict` (restored state) | **yes** |
| `generate_report` | `crawl_id: str`, `format: str`, `branding: dict` | `str` (file path) | no |
| `diff_crawls` | `crawl_id_a: str`, `crawl_id_b: str` | `dict` (resolved/new/changed issues) | no |

*Note: `apply_fix` server-side rejects if `issue.tier == 'FLAG'`, requires `confirm=True`, snapshots before-state, and stores rollback data.*
