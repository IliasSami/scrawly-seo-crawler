from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import Any, Callable

import structlog

from sentinelseo.audit.context import SiteContext, Thresholds
from sentinelseo.checks.registry import CrawlContext, Finding, get_all_checks
from sentinelseo.checks.site_level.registry import get_site_level_checks

log = structlog.get_logger(__name__)

ORDER = ["Info", "Low", "Medium", "High", "Critical"]
_HIGH_IDX = ORDER.index("High")


def scale_severity(base: str, affected: int, eligible: int, t: Thresholds) -> str:
    """Rescale a finding's severity by how widely the defect covers the site.

    Design goals (previous impl flooded uniform sites with Critical):
      * Breadth can *raise* severity but NEVER manufacture Critical — Critical must
        be earned by the check's own baseline, so the label stays meaningful.
      * INFO/opportunity findings never escalate on breadth.
      * A minimum absolute affected count is required, so a 2-page site doesn't
        jump to High off a single finding.
    """
    if base not in ORDER:
        return base
    idx = ORDER.index(base)
    if base == "Info" or eligible <= 0 or affected < t.min_affected_for_escalation:
        return base

    coverage = affected / eligible
    if coverage >= t.coverage_critical:
        bump = 2
    elif coverage >= t.coverage_high:
        bump = 1
    else:
        bump = 0
    if bump == 0:
        return base

    # Cap breadth-escalation at High; never downgrade a Critical baseline.
    new_idx = max(min(idx + bump, _HIGH_IDX), idx)
    return ORDER[new_idx]

def rescale(findings: list[Finding], site: SiteContext) -> list[Finding]:
    eligible = sum(1 for p in site.pages.values() if p.url_row and p.url_row.status == 200)
    # Affected = distinct URLs a check fired on (not raw finding count).
    affected_by_check: dict[str, set[str]] = {}
    for f in findings:
        affected_by_check.setdefault(f.check_id, set()).update(f.affected_urls)
    out = []
    for f in findings:
        n = len(affected_by_check.get(f.check_id, ()))
        new_sev = scale_severity(f.severity, n, eligible, site.thresholds)
        out.append(replace(f, severity=new_sev))
    return out

def apply_precedence(findings: list[Finding]) -> list[Finding]:
    """Applies precedence rules to prevent double-reporting."""
    # Build indexes
    url_to_checks: dict[str, set[str]] = {}
    for f in findings:
        for u in f.affected_urls:
            url_to_checks.setdefault(u, set()).add(f.check_id)

    out = []
    for f in findings:
        drop = False
        downgrade = False

        for u in f.affected_urls:
            checks_on_url = url_to_checks.get(u, set())

            # 1. 4xx/5xx suppress on-page checks
            if f.check_id[0] in ('D', 'E', 'H', 'J'):
                if 'B01' in checks_on_url or 'B02' in checks_on_url:
                    drop = True

            # 2. noindex downgrades opportunities to Info
            if f.check_id in ('D03', 'D04', 'D09', 'D10'):
                if 'A04' in checks_on_url or 'A05' in checks_on_url:
                    downgrade = True

            # 3. E01 suppresses E02 for same URL
            if f.check_id == 'E02' and 'E01' in checks_on_url:
                # Wait, rule says same URL pair. E02 and E01 report on the same URL. So we suppress.
                drop = True

            # 4. B10 suppresses C04
            if f.check_id == 'C04' and 'B10' in checks_on_url:
                drop = True

            # 5. A02 and L03 flag the same underlying defect. Emit once under A02.
            if f.check_id == 'L03' and 'A02' in checks_on_url:
                drop = True

        if drop:
            continue

        if downgrade:
            from dataclasses import replace
            out.append(replace(f, severity="Info"))
        else:
            out.append(f)

    return out

def _run_single_url(args: tuple[str, CrawlContext, list[tuple[str, Any, Callable[..., Any]]]]) -> list[Finding]:  # noqa: E501
    url, page, checks = args
    results = []
    for check_id, _spec, fn in checks:
        try:
            f = fn(page)
            if f:
                results.append(f)
        except Exception as e:
            log.warning("check_failed", check_id=check_id, url=url, error=str(e))
    return results

def run_audit(site: SiteContext) -> list[Finding]:
    # Ensure every check is registered regardless of entry point. Idempotent.
    from sentinelseo.checks import load_all_checks

    load_all_checks()

    findings: list[Finding] = []

    # Filter out deferred checks from URL level
    url_checks = []
    for check_id, (spec, fn) in get_all_checks().items():
        if getattr(spec, "status", None) != "deferred":
            url_checks.append((check_id, spec, fn))

    # PASS 1 - per-URL pure checks
    tasks = []
    for url, page in site.pages.items():
        tasks.append((url, page, url_checks))

    with ThreadPoolExecutor() as executor:
        for results in executor.map(_run_single_url, tasks):
            findings.extend(results)

    # PASS 2 - site-level checks
    for site_check_id, (_site_spec, site_fn) in get_site_level_checks().items():
        try:
            for f_site in site_fn(site):
                findings.append(f_site)
        except Exception as e:
            log.warning("site_check_failed", check_id=site_check_id, error=str(e))

    # PASS 3 - rescale
    rescaled = rescale(findings, site)

    # PASS 4 - precedence
    return apply_precedence(rescaled)
