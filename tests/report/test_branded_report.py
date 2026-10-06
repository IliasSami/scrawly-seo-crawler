"""Branded HTML report generator — renders and honors white-label branding."""
from sentinelseo.db.models import URL, AppSettings, Crawl, Issue
from sentinelseo.db.session import SessionLocal
from sentinelseo.report.generator import ReportGenerator


def _seed() -> int:
    db = SessionLocal()
    crawl = Crawl(client_id=1, target_url="https://report.example/", config={}, url_count=2)
    db.add(crawl)
    db.commit()
    db.refresh(crawl)
    cid = int(crawl.id)
    db.add_all([
        URL(crawl_id=cid, address="https://report.example/", status=200, indexable=True, depth=0, word_count=800),
        URL(crawl_id=cid, address="https://report.example/x", status=404, indexable=False, depth=1),
    ])
    db.add(Issue(
        crawl_id=cid, check_id="B01", severity="Critical", tier="REVIEW",
        affected_url_ids=[], evidence={}, why_it_matters="Broken page",
        recommended_fix="Restore the page or 301 it.",
    ))
    db.commit()
    db.close()
    return cid


def _set_brand(**kw: str) -> None:
    db = SessionLocal()
    row = db.query(AppSettings).filter(AppSettings.id == 1).first()
    data = dict(row.data) if row and row.data else {}
    data.update(kw)
    if row is None:
        db.add(AppSettings(id=1, data=data))
    else:
        row.data = data
    db.commit()
    db.close()


def test_report_renders_self_contained_html() -> None:
    cid = _seed()
    html = ReportGenerator().generate_html(cid)
    assert html.lstrip().startswith("<!doctype html>")
    assert "Technical SEO Audit" in html
    assert f"Crawl #{cid}" in html
    assert "<svg" in html  # inline charts
    # Complete + detailed: a full page inventory of every crawled URL.
    assert "Page inventory" in html
    assert "800" in html   # the seeded page's word count appears in the inventory
    assert "/x" in html    # both crawled URL paths are listed
    # Self-contained: no external stylesheet/script/font references.
    assert '<link rel="stylesheet"' not in html
    assert "<script" not in html


def test_report_applies_white_label_branding() -> None:
    cid = _seed()
    _set_brand(
        report_brand_name="Northlight SEO",
        report_brand_color="#0ea5e9",
        report_brand_contact="hello@northlight.co",
    )
    html = ReportGenerator().generate_html(cid)
    assert "Northlight SEO" in html
    assert "#0ea5e9" in html
    assert "hello@northlight.co" in html
    assert "powered by Scrawly" in html  # attribution shown for non-Scrawly brands
    # reset
    _set_brand(report_brand_name="", report_brand_color="#6366f1", report_brand_contact="")


def test_report_missing_crawl_raises() -> None:
    import pytest
    with pytest.raises(ValueError):
        ReportGenerator().generate_html(987654)


def _seed_with_agentic() -> int:
    """A crawl carrying an origin-level agentic report."""
    cid = _seed()
    db = SessionLocal()
    crawl = db.query(Crawl).filter(Crawl.id == cid).first()
    assert crawl is not None
    crawl.agentic_report = {
        "origin": "https://report.example", "score": 40,
        "level": "Level 2", "level_label": "Agent-discoverable",
        "passed": 2, "scored": 5, "is_commerce": False,
        "categories": [
            {"category": "discoverability", "label": "Discoverability",
             "passed": 2, "total": 3, "score": 67},
            {"category": "commerce", "label": "Agentic Commerce",
             "passed": 0, "total": 0, "score": None},
        ],
        "results": [
            {"probe_id": "AGT.ROBOTS", "title": "robots.txt",
             "category": "discoverability", "category_label": "Discoverability",
             "goal": "Publish robots.txt", "status": "pass",
             "conclusion": "robots.txt exists", "steps": [], "evidence": {},
             "remediation": "", "spec_urls": [], "duration_ms": 5, "fix_prompt": ""},
            {"probe_id": "AGT.LLMS_TXT", "title": "llms.txt",
             "category": "content", "category_label": "Content Accessibility",
             "goal": "Publish /llms.txt", "status": "fail",
             "conclusion": "No llms.txt found", "steps": [], "evidence": {},
             "remediation": "Add /llms.txt with curated links.",
             "spec_urls": [], "duration_ms": 8,
             "fix_prompt": "You are working on https://report.example (detected stack: WordPress)."},
        ],
    }
    db.commit()
    db.close()
    return cid


def test_report_includes_agentic_section() -> None:
    cid = _seed_with_agentic()
    html = ReportGenerator().generate_html(cid)
    assert 'id="sec-agentic"' in html
    assert 'href="#sec-agentic"' in html, "agentic section must be linked from the TOC"
    assert "Agent-discoverable" in html
    assert "40" in html


def test_agentic_section_lists_actionable_items_with_prompts() -> None:
    html = ReportGenerator().generate_html(_seed_with_agentic())
    assert "No llms.txt found" in html
    assert "Add /llms.txt with curated links." in html
    assert "detected stack: WordPress" in html, "the agent prompt must be embedded"


def test_agentic_section_shows_not_checked_categories_without_a_score() -> None:
    """A blog must not read as failing agentic commerce."""
    html = ReportGenerator().generate_html(_seed_with_agentic())
    assert "Agentic Commerce" in html
    assert "0/0" in html


def test_report_without_agentic_data_omits_the_section() -> None:
    html = ReportGenerator().generate_html(_seed())
    assert 'id="sec-agentic"' not in html
    assert 'href="#sec-agentic"' not in html


def test_agentic_section_keeps_the_report_self_contained() -> None:
    """Invariant: the exported report must never load anything external."""
    html = ReportGenerator().generate_html(_seed_with_agentic())
    assert "<script" not in html
    assert "<link" not in html
