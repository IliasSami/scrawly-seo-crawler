"""Deleting one audit must remove everything it produced — and nothing else.

Orphaned rows are worse than a failed delete: they silently inflate counts,
keep showing up in fix history, and are invisible to the user.
"""
from fastapi.testclient import TestClient

from sentinelseo.db.models import URL, Crawl, Fix, Issue, Resource
from sentinelseo.db.session import SessionLocal
from sentinelseo.web.api import app

client = TestClient(app)


def _seed(client_id: int = 1) -> tuple[int, int]:
    db = SessionLocal()
    crawl = Crawl(client_id=client_id, target_url="https://del.example/",
                  config={}, url_count=2)
    db.add(crawl)
    db.commit()
    db.refresh(crawl)
    cid = int(crawl.id)
    db.add_all([
        URL(crawl_id=cid, address="https://del.example/a", status=200, depth=0),
        URL(crawl_id=cid, address="https://del.example/b", status=404, depth=1),
    ])
    db.add(Resource(crawl_id=cid, url="https://del.example/s.css", type="css"))
    db.commit()
    issue = Issue(crawl_id=cid, check_id="B01", severity="High", tier="REVIEW",
                  affected_url_ids=[], evidence={}, why_it_matters="w",
                  recommended_fix="r")
    db.add(issue)
    db.commit()
    db.refresh(issue)
    iid = int(issue.id)
    db.add(Fix(issue_id=iid, check_id="B01", tier="REVIEW", before_state={},
               after_state={}, applied_by="test"))
    db.commit()
    db.close()
    return cid, iid


def _counts(cid: int, iid: int) -> dict[str, int]:
    db = SessionLocal()
    out = {
        "crawl": db.query(Crawl).filter(Crawl.id == cid).count(),
        "urls": db.query(URL).filter(URL.crawl_id == cid).count(),
        "issues": db.query(Issue).filter(Issue.crawl_id == cid).count(),
        "resources": db.query(Resource).filter(Resource.crawl_id == cid).count(),
        "fixes": db.query(Fix).filter(Fix.issue_id == iid).count(),
    }
    db.close()
    return out


def test_delete_removes_the_crawl_and_all_children() -> None:
    cid, iid = _seed()
    assert all(v > 0 for v in _counts(cid, iid).values())
    res = client.delete(f"/api/crawls/{cid}")
    assert res.status_code == 200
    assert res.json()["deleted"] == cid
    assert _counts(cid, iid) == {
        "crawl": 0, "urls": 0, "issues": 0, "resources": 0, "fixes": 0}


def test_delete_reports_what_it_removed() -> None:
    cid, _ = _seed()
    removed = client.delete(f"/api/crawls/{cid}").json()["removed"]
    assert removed["urls"] == 2
    assert removed["issues"] == 1
    assert removed["resources"] == 1
    assert removed["fixes"] == 1


def test_deleting_a_missing_crawl_is_404() -> None:
    assert client.delete("/api/crawls/99999999").status_code == 404


def test_delete_is_not_idempotent_silently() -> None:
    """A second delete must 404, not pretend it worked."""
    cid, _ = _seed()
    assert client.delete(f"/api/crawls/{cid}").status_code == 200
    assert client.delete(f"/api/crawls/{cid}").status_code == 404


def test_sibling_crawls_are_untouched() -> None:
    """Deleting one audit must not disturb another on the same client."""
    keep_cid, keep_iid = _seed(client_id=1)
    drop_cid, _ = _seed(client_id=1)
    client.delete(f"/api/crawls/{drop_cid}")
    kept = _counts(keep_cid, keep_iid)
    assert kept["crawl"] == 1 and kept["urls"] == 2
    assert kept["issues"] == 1 and kept["fixes"] == 1
