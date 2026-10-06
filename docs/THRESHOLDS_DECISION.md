# Thresholds Decision

To maintain maintainability and allow per-client tunability, Scrawly will adopt a centralized `Thresholds` configuration to replace magic numbers embedded directly within check implementations. 

## Single Source of Truth
We propose creating `config/thresholds.py` to house the `Thresholds` dataclass specified in the detection logic. This object will be loaded during crawl initialization and attached to the `SiteContext` as `site.thresholds`.

```python
from dataclasses import dataclass

@dataclass
class Thresholds:
    title_px_max: int = 561
    title_px_min: int = 200
    title_char_max: int = 60
    title_char_min: int = 30
    metadesc_px_max: int = 985
    metadesc_px_min: int = 400
    heading_char_max: int = 70            
    low_content_words: int = 200
    thin_content_words: int = 100         
    near_dup_similarity: float = 0.90     
    url_char_max: int = 115
    max_links_on_page: int = 150
    max_crawl_depth: int = 4
    image_kb_max: int = 100
    alt_char_max: int = 100
    ttfb_ms_warn: float = 800.0
    dom_node_warn: int = 1500
    page_weight_mb_warn: float = 3.0
    lcp_good_s: float = 2.5
    lcp_poor_s: float = 4.0
    inp_good_ms: float = 200.0
    inp_poor_ms: float = 500.0
    cls_good: float = 0.10
    cls_poor: float = 0.25
    text_html_ratio_min: float = 0.10
    coverage_high: float = 0.20           
    coverage_critical: float = 0.40
```

## Migration Target List
Every check currently implemented in the MVP that relies on hardcoded constants must be migrated to reference `site.thresholds.<property>`. Known magic numbers to purge include:

*   **URL Length Limitations**: Hardcoded `115` (e.g. `len(ctx.url) > 115` in `T04`) -> `thresholds.url_char_max`
*   **Directory Depth Limitations**: Hardcoded `4` (e.g. `len(segments) > 4` in `T06`) -> `thresholds.max_crawl_depth`
*   **Title/Meta pixel widths**: Any hardcoded `561` or `985` -> `thresholds.title_px_max` / `thresholds.metadesc_px_max`
*   **Word counts**: Any hardcoded `100` or `200` for thin content -> `thresholds.thin_content_words` / `thresholds.low_content_words`
*   **CWV metrics**: Hardcoded LCP/INP/CLS metrics -> `thresholds.lcp_poor_s`, etc.
*   **Coverage Escalation rules**: Hardcoded `20%` or `40%` -> `thresholds.coverage_high` / `thresholds.coverage_critical`

By enforcing this migration, we ensure that as Google's SERP widths or CWV definitions evolve, Scrawly can be updated via a single config file change rather than a massive codebase refactor.
