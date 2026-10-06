"""Shared site-health scoring so the dashboard and the exported report agree.

Rationale — the old model summed severity-weighted *issue counts*
(Critical×7 + High×3.5 + …). That doesn't scale with site size: a small site
with ~15 distinct High findings hit 100 penalty and scored 0, indistinguishable
from a catastrophically broken site. That is illogical.

This model instead scores on the SHARE OF PAGES that carry a serious problem,
plus indexability and non-broken share — the things that actually describe how
healthy a site is. 100 = clean; it degrades smoothly and is bounded 0-100.

  health = 100 × ( 0.70 · clean_page_ratio      # pages free of Critical/High issues
                 + 0.20 · indexable_ratio        # share Google can index
                 + 0.10 · (1 − broken_ratio) )   # share returning 2xx/3xx
          − min(15, 3 × serious_site_level_issues)
"""
from __future__ import annotations

from typing import Any, Iterable

_SERIOUS = {"Critical", "High"}


def compute_health(total_urls: int, indexable: int, broken: int, issues: Iterable[Any]) -> int:
    """Return a 0-100 health score. `issues` yields objects with `.severity` and
    `.affected_url_ids` (one row per distinct finding)."""
    if total_urls <= 0:
        return 100

    serious_pages: set[int] = set()
    serious_site_level = 0
    for i in issues:
        if getattr(i, "severity", "") in _SERIOUS:
            ids = list(getattr(i, "affected_url_ids", None) or [])
            if ids:
                serious_pages.update(ids)
            else:
                serious_site_level += 1

    clean_ratio = 1.0 - min(1.0, len(serious_pages) / total_urls)
    indexable_ratio = indexable / total_urls
    broken_ratio = broken / total_urls

    base = 0.70 * clean_ratio + 0.20 * indexable_ratio + 0.10 * (1.0 - broken_ratio)
    score = round(100.0 * base) - min(15, serious_site_level * 3)
    return max(0, min(100, score))
