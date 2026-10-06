"""Crawl diff compares findings by check and page address, not by per-crawl row id."""
from typing import Any

from sentinelseo.db.models import URL, Client, Crawl, Issue
from sentinelseo.db.session import SessionLocal
from sentinelseo.report.differ import diff_crawls


def _crawl(db: Any, client_id: int, findings: dict[str, list[str]]) -> int:
    crawl = Crawl(client_id=client_id, target_url="https://d.test/", config={}, url_count=0)
    db.add(crawl)
    db.commit()
    pages = sorted({p for ps in findings.values() for p in ps})
    rows = {p: URL(crawl_id=crawl.id, address=p, status=200, indexable=True) for p in pages}
    db.add_all(rows.values())
    db.commit()
    for check_id, ps in findings.items():
        db.add(Issue(crawl_id=crawl.id, check_id=check_id, severity="High", tier="REVIEW",
                     affected_url_ids=[rows[p].id for p in ps], evidence={}))
    db.commit()
    return int(crawl.id)


def test_same_findings_in_two_crawls_persist() -> None:
    db = SessionLocal()
    c = Client(name="Diff", base_url="https://d.test/")
    db.add(c)
    db.commit()
    a = _crawl(db, c.id, {"D01": ["https://d.test/x"], "L01": [], "B01": ["https://d.test/gone"]})
    b = _crawl(db, c.id, {"D01": ["https://d.test/x"], "L01": [], "D07": ["https://d.test/y"]})
    db.close()
    out = diff_crawls(a, b)
    assert out["counts"] == {"resolved": 1, "new": 1, "persisting": 2}
    assert out["resolved"][0]["check_id"] == "B01"
    assert out["new"][0] == {"check_id": "D07", "url": "https://d.test/y", "tier": "REVIEW"}
