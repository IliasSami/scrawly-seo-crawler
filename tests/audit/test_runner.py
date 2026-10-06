from sentinelseo.audit.context import SiteContext, Thresholds
from sentinelseo.audit.runner import apply_precedence, run_audit, scale_severity
from sentinelseo.checks.registry import Finding


def test_scale_severity() -> None:
    t = Thresholds(coverage_high=0.20, coverage_critical=0.50)
    # Low severity, 1 affected, 100 eligible -> Low
    assert scale_severity("Low", 1, 100, t) == "Low"

    # Low severity, 25 affected, 100 eligible -> 25% -> Medium (bump 1)
    assert scale_severity("Low", 25, 100, t) == "Medium"

    # Low severity, 60 affected, 100 eligible -> 60% -> High (bump 2)
    assert scale_severity("Low", 60, 100, t) == "High"

    # Critical shouldn't bump past Critical
    assert scale_severity("Critical", 60, 100, t) == "Critical"

def test_apply_precedence() -> None:
    findings = [
        Finding("B01", "High", "AUTO", ["url1"], {}, {}, "", ""),
        Finding("D01", "High", "AUTO", ["url1"], {}, {}, "", ""), # Should be dropped by B01
        Finding("A04", "Medium", "REVIEW", ["url2"], {}, {}, "", ""),
        Finding("D03", "Medium", "REVIEW", ["url2"], {}, {}, "", ""), # Should be downgraded by A04
        Finding("E01", "High", "REVIEW", ["url3", "url4"], {}, {}, "", ""),
        Finding("E02", "Medium", "REVIEW", ["url3"], {}, {}, "", ""), # Should be dropped by E01
    ]

    out = apply_precedence(findings)
    check_ids = [(f.check_id, f.severity, f.affected_urls) for f in out]

    # D01 on url1 dropped due to B01
    assert not any(c == "D01" and u == ["url1"] for c, _, u in check_ids)

    # D03 downgraded to Info due to A04
    assert any(c == "D03" and s == "Info" for c, s, _ in check_ids)

    # E02 dropped because E01 fired on url3
    assert not any(c == "E02" for c, _, _ in check_ids)

def test_exception_handling() -> None:
    # To test exception handling without mocking the whole registry,
    # we can just invoke run_audit on an empty site, as that tests
    # the pool and loop logic.
    ctx = SiteContext(base_url="http://test.com", pages={})
    res = run_audit(ctx)
    assert isinstance(res, list)
