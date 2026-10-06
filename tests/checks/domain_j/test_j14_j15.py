"""J14 (incomplete schema) + J15 (microdata/RDFa without JSON-LD)."""
from types import SimpleNamespace

from sentinelseo.checks.domain_j.checks import (
    check_J14,
    check_J15,
    schema_recommended_gaps,
)
from sentinelseo.checks.registry import CrawlContext


def test_validator_flags_missing_props() -> None:
    gaps = schema_recommended_gaps([{"@type": "Product", "name": "Widget"}])
    assert gaps and gaps[0][0] == "Product"
    assert "image" in gaps[0][1] and "offers" in gaps[0][1]


def test_validator_complete_no_gaps() -> None:
    complete = [{"@type": "Product", "name": "W", "image": "x.jpg",
                 "offers": {"price": 1, "priceCurrency": "USD"}}]
    assert schema_recommended_gaps(complete) == []


def test_validator_ignores_unknown_type() -> None:
    assert schema_recommended_gaps([{"@type": "SomethingWeird"}]) == []


def test_validator_flattens_graph() -> None:
    # WordPress/Yoast wrap everything under @graph.
    blocks = [{"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "name": "S"},
        {"@type": "Product", "name": "X"},  # missing image + offers
    ]}]
    gaps = schema_recommended_gaps(blocks)
    assert any(t == "Product" and "image" in m for t, m in gaps)


def test_J14_positive() -> None:
    ctx = CrawlContext(
        url="http://t.com", raw_html="",
        structured_data=[{"@type": "Article", "headline": "Hi"}],
    )
    f = check_J14(ctx)
    assert f is not None and f.check_id == "J14"


def test_J14_negative() -> None:
    ctx = CrawlContext(
        url="http://t.com", raw_html="",
        structured_data=[{"@type": "Organization", "name": "A", "url": "u", "logo": "l"}],
    )
    assert check_J14(ctx) is None


def test_J15_positive() -> None:
    ctx = CrawlContext(
        url="http://t.com", raw_html="",
        structured_data=[],
        url_row=SimpleNamespace(microdata_types=["Product"], rdfa_types=[], jsonld=[]),
    )
    f = check_J15(ctx)
    assert f is not None and f.check_id == "J15"


def test_J15_negative_has_jsonld() -> None:
    ctx = CrawlContext(
        url="http://t.com", raw_html="",
        structured_data=[{"@type": "Product"}],
        url_row=SimpleNamespace(microdata_types=["Product"], rdfa_types=[],
                                jsonld=[{"@type": "Product"}]),
    )
    assert check_J15(ctx) is None
