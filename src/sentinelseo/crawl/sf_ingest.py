import csv
from typing import List

from .models import ImageRow, URLRow


def ingest_screaming_frog_csv(file_path: str) -> tuple[List[URLRow], List[ImageRow]]:
    urls: List[URLRow] = []
    images: List[ImageRow] = []

    with open(file_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            address = row.get("Address", "")
            if not address:
                continue

            status_code = row.get("Status Code", "200")
            try:
                status = int(status_code)
            except ValueError:
                status = 200

            title = row.get("Title 1")
            meta_desc = row.get("Meta Description 1")
            canonical = row.get("Canonical Link Element 1")
            meta_robots = row.get("Meta Robots 1")
            x_robots = row.get("X-Robots-Tag 1")

            h1 = [h for h in [row.get("H1-1")] if h]
            h2 = [h for h in [row.get("H2-1")] if h]

            try:
                word_count = int(row.get("Word Count", "0"))
            except ValueError:
                word_count = 0

            try:
                ttfb = float(row.get("Response Time", "0.0"))
            except ValueError:
                ttfb = 0.0

            try:
                size = int(row.get("Size (Bytes)", "0"))
            except ValueError:
                size = 0

            try:
                inlink_count = int(row.get("Inlinks", "0"))
            except ValueError:
                inlink_count = 0

            try:
                outlink_count = int(row.get("Outlinks", "0"))
            except ValueError:
                outlink_count = 0

            indexability = row.get("Indexability", "Indexable")
            indexable = indexability.lower() == "indexable"

            urls.append(
                URLRow(
                    address=address,
                    status=status,
                    redirect_chain=[],
                    title=title,
                    meta_desc=meta_desc,
                    canonical=canonical,
                    meta_robots=meta_robots,
                    x_robots=x_robots,
                    h1=h1,
                    h2=h2,
                    h3=[],
                    h4=[],
                    h5=[],
                    h6=[],
                    word_count=word_count,
                    content_hash=row.get("Hash", ""),
                    near_dup_cluster="",
                    ttfb=ttfb,
                    size=size,
                    inlink_count=inlink_count,
                    outlink_count=outlink_count,
                    indexable=indexable,
                    indexability_reason=row.get("Indexability Status", ""),
                    internal_links=[],
                    external_links=[],
                )
            )

    return urls, images
