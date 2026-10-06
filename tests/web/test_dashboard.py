"""Dashboard aggregation endpoint (Milestone B) — /api/dashboard/{crawl_id}."""
from fastapi.testclient import TestClient

from sentinelseo.db.models import URL, Crawl, Issue
from sentinelseo.db.session import SessionLocal
from sentinelseo.web.api import app

client = TestClient(app)


def _seed() -> int:
    db = SessionLocal()
    crawl = Crawl(client_id=1, target_url="https://ex.com/", config={}, url_count=4)
    db.add(crawl)
    db.commit()
    db.refresh(crawl)
    cid = int(crawl.id)
    db.add_all([
        URL(crawl_id=cid, address="https://ex.com/", status=200, indexable=True, depth=0, segment="Home"),
        URL(crawl_id=cid, address="https://ex.com/a", status=200, indexable=True, depth=1, segment="Blog"),
        URL(crawl_id=cid, address="https://ex.com/b", status=404, indexable=False, depth=1, segment="Blog"),
        URL(crawl_id=cid, address="https://ex.com/c", status=301, indexable=True, depth=2, segment=None),
    ])
    db.add_all([
        Issue(crawl_id=cid, check_id="B01", severity="Critical", tier="REVIEW", affected_url_ids=[], evidence={}),
        Issue(crawl_id=cid, check_id="D02", severity="High", tier="REVIEW", affected_url_ids=[], evidence={}),
        Issue(crawl_id=cid, check_id="D08", severity="Medium", tier="REVIEW", affected_url_ids=[], evidence={}),
    ])
    db.commit()
    db.close()
    return cid


def test_totals_and_status_classes() -> None:
    cid = _seed()
    d = client.get(f"/api/dashboard/{cid}").json()
    assert d["totals"]["urls"] == 4
    assert d["totals"]["indexable"] == 3
    assert d["totals"]["broken"] == 1  # only the 404
    assert d["status_classes"] == {"2xx": 2, "3xx": 1, "4xx": 1, "5xx": 0, "other": 0}
    assert d["indexable_pct"] == 75


def test_fixability_tiers_content_and_reasons() -> None:
    cid = _seed()
    d = client.get(f"/api/dashboard/{cid}").json()
    # All three seeded issues are REVIEW tier.
    assert d["tiers"] == {"AUTO": 0, "REVIEW": 3, "FLAG": 0}
    # The one 404 is non-indexable → a reason bucket appears.
    assert d["totals"]["redirects"] == 1  # the 301
    assert isinstance(d["content"]["avg_words"], int)
    assert "avg_lcp_s" in d["cwv"]
    reasons = {r["reason"]: r["count"] for r in d["indexability_reasons"]}
    assert sum(reasons.values()) == d["totals"]["non_indexable"]


def test_severity_tally_and_sorted_categories() -> None:
    cid = _seed()
    d = client.get(f"/api/dashboard/{cid}").json()
    assert d["severity"]["Critical"] == 1
    assert d["severity"]["High"] == 1
    assert d["severity"]["Medium"] == 1
    assert d["totals"]["issues"] == 3
    counts = [c["count"] for c in d["issue_categories"]]
    assert counts == sorted(counts, reverse=True)  # ranked most-common first


def test_depth_histogram_and_segments() -> None:
    cid = _seed()
    d = client.get(f"/api/dashboard/{cid}").json()
    assert {h["depth"]: h["count"] for h in d["depth_histogram"]} == {0: 1, 1: 2, 2: 1}
    assert {s["name"]: s["count"] for s in d["segments"]} == {"Blog": 2, "Home": 1}


def test_health_score_within_bounds() -> None:
    cid = _seed()
    d = client.get(f"/api/dashboard/{cid}").json()
    assert 0 <= d["health_score"] <= 100


def test_empty_crawl_is_safe_and_not_penalized() -> None:
    db = SessionLocal()
    crawl = Crawl(client_id=1, target_url="https://empty.com/", config={}, url_count=0)
    db.add(crawl)
    db.commit()
    db.refresh(crawl)
    cid = int(crawl.id)
    db.close()
    d = client.get(f"/api/dashboard/{cid}").json()
    assert d["totals"]["urls"] == 0
    assert d["health_score"] == 100  # nothing crawled → no penalties
    assert d["status_classes"]["2xx"] == 0
