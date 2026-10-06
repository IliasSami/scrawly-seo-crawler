from sentinelseo.checks.registry import CrawlContext, check_D01


def test_check_D01_missing_title() -> None:
    """Positive test: URL is missing a title, check should return a Finding."""
    ctx = CrawlContext(url="https://example.com/no-title", title="")
    finding = check_D01(ctx)

    assert finding is not None
    assert finding.check_id == "D01"
    assert finding.severity == "High"
    assert finding.tier == "AUTO"
    assert finding.affected_urls == ["https://example.com/no-title"]
    assert finding.evidence["found_title"] == ""


def test_check_D01_has_title() -> None:
    """Negative test: URL has a valid title, check should return None."""
    ctx = CrawlContext(url="https://example.com/valid", title="My valid title")
    finding = check_D01(ctx)

    assert finding is None
