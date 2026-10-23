"""R10/R12 against JSON-LD as the parser actually stores it.

`structured_data` holds each <script type="application/ld+json"> parsed as-is:
real keys are `@type`, WordPress SEO plugins wrap entities in `@graph`, and a
script may hold a top-level array. The original checks read `"type"` and called
`.get` on every block, so on real sites they either crashed on array blocks or
never saw Organization/Product and flagged every page.
"""
from types import SimpleNamespace
from typing import Any

from sentinelseo.checks.domain_f.checks import check_F11
from sentinelseo.checks.domain_r.checks import check_R10, check_R12
from sentinelseo.checks.registry import CrawlContext

RANK_MATH_GRAPH = [{
    "@context": "https://schema.org",
    "@graph": [
        {"@type": "Organization", "name": "Demte"},
        {"@type": "WebSite", "url": "https://demte.com.tr/"},
        {"@type": "BreadcrumbList", "itemListElement": []},
        {"@type": ["Product", "Thing"], "name": "DIN rail"},
    ],
}]

ARRAY_BLOCK = [[
    {"@context": "https://schema.org", "@type": "Organization", "name": "Demte"},
    {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": []},
]]


def _ctx(sd: list[Any]) -> CrawlContext:
    return CrawlContext(url="https://demte.com.tr/p/", raw_html="", structured_data=sd)


def test_r10_sees_organization_inside_graph() -> None:
    assert check_R10(_ctx(RANK_MATH_GRAPH)) is None


def test_r10_does_not_crash_on_array_block() -> None:
    assert check_R10(_ctx(ARRAY_BLOCK)) is None


def test_r10_still_fires_without_entity_schema() -> None:
    finding = check_R10(_ctx([{"@type": "Article"}]))
    assert finding is not None
    assert finding.evidence["found_schemas"] == ["article"]


def test_r12_sees_product_type_list_inside_graph() -> None:
    assert check_R12(_ctx(RANK_MATH_GRAPH)) is None


def test_r12_sees_faqpage_inside_array_block() -> None:
    assert check_R12(_ctx(ARRAY_BLOCK)) is None


def test_r12_still_fires_without_fact_schema() -> None:
    assert check_R12(_ctx([{"@type": "WebPage"}])) is not None


def test_f11_sees_breadcrumb_inside_graph() -> None:
    ctx = CrawlContext(url="https://demte.com.tr/a/b/c/", raw_html="",
                       structured_data=RANK_MATH_GRAPH,
                       url_row=SimpleNamespace(depth=3))
    assert check_F11(ctx) is None
