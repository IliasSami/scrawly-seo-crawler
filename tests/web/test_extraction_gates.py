"""SF Pattern A/B — resource + extraction gates."""
from types import SimpleNamespace

from sentinelseo.crawl.fetcher import Crawler
from sentinelseo.web.api import _apply_extraction_gates


def _row() -> SimpleNamespace:
    return SimpleNamespace(
        content_hash="abc123", jsonld=[{"@type": "Article"}],
        microdata_types=["Product"], rdfa_types=["Person"],
    )


def test_store_hash_off_clears_hash() -> None:
    rows = [_row()]
    _apply_extraction_gates(rows, {"store_hash": False, "extract_structured_data": True})
    assert rows[0].content_hash == ""          # exact-dup detection disabled
    assert rows[0].jsonld                       # structured data untouched


def test_structured_data_off_clears_markup() -> None:
    rows = [_row()]
    _apply_extraction_gates(rows, {"store_hash": True, "extract_structured_data": False})
    assert rows[0].jsonld == [] and rows[0].microdata_types == [] and rows[0].rdfa_types == []
    assert rows[0].content_hash == "abc123"     # hash untouched


def test_defaults_keep_everything() -> None:
    rows = [_row()]
    _apply_extraction_gates(rows, {})           # both default on
    assert rows[0].content_hash == "abc123" and rows[0].jsonld


def test_resource_gates_stored_on_crawler() -> None:
    c = Crawler(render=False, crawl_images=False, crawl_external=False)
    assert c.crawl_images is False and c.crawl_external is False
    d = Crawler(render=False)
    assert d.crawl_images is True and d.crawl_external is True
