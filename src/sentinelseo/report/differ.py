from typing import Any, Dict, Set, Tuple

from sentinelseo.db.models import URL, Issue
from sentinelseo.db.session import SessionLocal

# One finding = a check on a page (site-wide findings use the empty page "").
_Key = Tuple[str, str]


def _findings(db: Any, crawl_id: int) -> Dict[_Key, str]:
    """(check_id, page address) -> tier for every finding in a crawl. URL row ids
    are per crawl, so pages are compared by address, never by id."""
    address = {u.id: u.address for u in db.query(URL).filter(URL.crawl_id == crawl_id).all()}
    out: Dict[_Key, str] = {}
    for issue in db.query(Issue).filter(Issue.crawl_id == crawl_id).all():
        pages: Set[str] = {address[i] for i in (issue.affected_url_ids or []) if i in address}
        for page in pages or {""}:
            out[(issue.check_id, page)] = issue.tier
    return out


def diff_crawls(crawl_id_old: int, crawl_id_new: int) -> Dict[str, Any]:
    """Compares two crawls of a site: which findings were resolved, which are new,
    and which persist (per check and page)."""
    db = SessionLocal()
    try:
        old = _findings(db, crawl_id_old)
        new = _findings(db, crawl_id_new)
    finally:
        db.close()

    def rows(keys: Set[_Key], tiers: Dict[_Key, str]) -> list[Dict[str, str]]:
        return [{"check_id": c, "url": u, "tier": tiers[(c, u)]} for c, u in sorted(keys)]

    resolved = rows(set(old) - set(new), old)
    new_found = rows(set(new) - set(old), new)
    persisting = rows(set(old) & set(new), new)
    return {
        "resolved": resolved,
        "new": new_found,
        "persisting": persisting,
        "counts": {
            "resolved": len(resolved),
            "new": len(new_found),
            "persisting": len(persisting),
        },
    }
