"""Shared health-score model — page-coverage based, bounded, logical."""
from types import SimpleNamespace

from sentinelseo.audit.health import compute_health


def _i(sev: str, ids: list[int]) -> SimpleNamespace:
    return SimpleNamespace(severity=sev, affected_url_ids=ids)


def test_clean_site_is_100() -> None:
    assert compute_health(100, 100, 0, []) == 100


def test_empty_crawl_is_100() -> None:
    assert compute_health(0, 0, 0, []) == 100


def test_all_pages_serious_and_noindex_is_low_not_zero() -> None:
    # 6 pages, all non-indexable, every page carries Critical + High findings.
    issues = [_i("Critical", [1, 2, 3, 4, 5, 6])] + [_i("High", [1, 2, 3, 4, 5, 6]) for _ in range(30)]
    score = compute_health(6, 0, 0, issues)
    assert 0 < score <= 20  # catastrophic but responding — not a hard 0


def test_scales_with_coverage_not_raw_count() -> None:
    # One High issue affecting 20% of an otherwise-healthy site scores well.
    high = compute_health(100, 100, 0, [_i("High", list(range(20)))])
    assert high >= 80
    # The same one issue affecting every page scores much lower.
    low = compute_health(100, 100, 0, [_i("High", list(range(100)))])
    assert low < high


def test_low_medium_info_do_not_tank_score() -> None:
    issues = [_i("Medium", list(range(100)))] + [_i("Low", list(range(100)))]
    assert compute_health(100, 100, 0, issues) >= 90  # only serious issues cut clean-ratio


def test_bounded_0_100() -> None:
    issues = [_i("Critical", []) for _ in range(50)]  # many serious site-level issues
    assert 0 <= compute_health(10, 0, 10, issues) <= 100
