"""SQLite checkpoints for an unfinished crawl, independent of its report rows."""

from dataclasses import asdict
from typing import Any, Callable

from sqlalchemy.orm import Session

from sentinelseo.crawl.models import (
    AgenticContext,
    ImageRef,
    LinkRef,
    MobileContext,
    ResourceRef,
    StructuredDataRow,
    UrlRenderDiffRow,
    URLRow,
)
from sentinelseo.db.models import Crawl, CrawlCheckpoint
from sentinelseo.db.session import SessionLocal

PageResult = tuple[URLRow, list[UrlRenderDiffRow], list[ImageRef], list[StructuredDataRow]]
PartialSave = Callable[[Session, URLRow, list[UrlRenderDiffRow]], bool]


def _encode(page: PageResult) -> dict[str, Any]:
    row, diffs, images, structured = page
    data = asdict(row)
    if row.minhash is not None:
        data["minhash"] = row.minhash.hex()
    if row.mobile_context is not None:
        data["mobile_context"]["blocked_resources"] = sorted(row.mobile_context.blocked_resources)
    return {
        "version": 1,
        "row": data,
        "diffs": [asdict(item) for item in diffs],
        "images": [asdict(item) for item in images],
        "structured": [asdict(item) for item in structured],
    }


def _decode(result: dict[str, Any]) -> PageResult:
    if result["version"] != 1:
        raise ValueError("Unsupported crawl checkpoint version")
    data = dict(result["row"])
    data["links"] = [LinkRef(**{**link, "rel": tuple(link["rel"])}) for link in data["links"]]
    data["images"] = [ImageRef(**image) for image in data["images"]]
    data["resources"] = [ResourceRef(**resource) for resource in data["resources"]]
    data["hreflang"] = [tuple(item) for item in data["hreflang"]]
    if data["minhash"] is not None:
        data["minhash"] = bytes.fromhex(data["minhash"])
    if (mobile := data["mobile_context"]) is not None:
        data["mobile_context"] = MobileContext(
            **{**mobile, "blocked_resources": set(mobile["blocked_resources"])}
        )
    if (agentic := data["agentic_context"]) is not None:
        data["agentic_context"] = AgenticContext(**agentic)
    return (
        URLRow(**data),
        [UrlRenderDiffRow(**item) for item in result["diffs"]],
        [ImageRef(**item) for item in result["images"]],
        [StructuredDataRow(**item) for item in result["structured"]],
    )


class CheckpointStore:
    def __init__(self, crawl_id: int, save_partial: PartialSave) -> None:
        self.crawl_id = crawl_id
        self.save_partial = save_partial

    def restore(self) -> tuple[
        str | None, dict[str, Any] | None, dict[str, int], list[tuple[str, int]], list[PageResult],
    ]:
        with SessionLocal() as db:
            crawl = db.get(Crawl, self.crawl_id)
            rows = db.query(CrawlCheckpoint).filter_by(crawl_id=self.crawl_id).order_by(
                CrawlCheckpoint.depth, CrawlCheckpoint.address,
            ).all()
            return (
                crawl.resolved_target if crawl else None,
                crawl.checkpoint_ai_access if crawl else None,
                {row.address: row.depth for row in rows},
                [(row.address, row.depth) for row in rows if not row.processed],
                [_decode(row.result) for row in rows if row.result is not None],
            )

    def record(
        self,
        requested: str | None,
        result: PageResult | None,
        discovered: list[tuple[str, int]],
        resolved_target: str,
        ai_access: dict[str, Any] | None = None,
    ) -> None:
        """Commit the result, its newly accepted links and progress together."""
        with SessionLocal() as db:
            crawl = db.get(Crawl, self.crawl_id)
            if crawl is None:
                raise ValueError("Crawl no longer exists")
            queue = dict(discovered)
            addresses = list(queue)
            added = 0
            # SQLite versions differ in their bound-parameter limit. The sitemap
            # can seed many more URLs than a page, so query it in fixed batches.
            for offset in range(0, len(addresses), 500):
                batch = addresses[offset:offset + 500]
                existing = {
                    address for (address,) in db.query(CrawlCheckpoint.address).filter(
                        CrawlCheckpoint.crawl_id == self.crawl_id,
                        CrawlCheckpoint.address.in_(batch),
                    )
                }
                new_entries = [
                    CrawlCheckpoint(crawl_id=self.crawl_id, address=url, depth=queue[url])
                    for url in batch if url not in existing
                ]
                db.add_all(new_entries)
                added += len(new_entries)
            crawl.discovered_count = (crawl.discovered_count or 0) + added
            if requested is None:
                crawl.resolved_target = resolved_target
                crawl.checkpoint_ai_access = ai_access
            else:
                entry = db.get(CrawlCheckpoint, (self.crawl_id, requested))
                if entry is None:
                    raise ValueError("Processed URL was not in the crawl frontier")
                if not entry.processed:
                    entry.processed = True
                    crawl.processed_count = (crawl.processed_count or 0) + 1
                    if result is not None:
                        entry.result = _encode(result)
                        crawl.completed_count = (crawl.completed_count or 0) + 1
                        if self.save_partial(db, result[0], result[1]):
                            crawl.url_count = (crawl.url_count or 0) + 1
            db.commit()
