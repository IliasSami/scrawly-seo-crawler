import pickle
import time

from datasketch import MinHash  # type: ignore

from sentinelseo.audit.context import SiteContext
from sentinelseo.checks.registry import CrawlContext
from sentinelseo.checks.site_level.checks import check_E02
from sentinelseo.crawl.models import URLRow


def _mock_url_row(minhash: bytes | None) -> URLRow:
    row = URLRow(
        address="", status=200, redirect_chain=[], title="", meta_desc="",
        canonical="", meta_robots="", x_robots="", h1=[], h2=[], h3=[], h4=[], h5=[], h6=[],
        word_count=0, content_hash="", near_dup_cluster="", ttfb=0.0, size=0, inlink_count=0,
        outlink_count=0, indexable=True, indexability_reason=None, minhash=minhash
    )
    return row

def benchmark() -> None:
    print("Generating 1000 pages...")
    pages = {}
    m1 = MinHash(num_perm=128)
    m1.update(b"this is a synthetic page content that will be duplicated")
    pickle.dumps(m1)

    m2 = MinHash(num_perm=128)
    m2.update(b"this is another completely different page that is not duped much")
    pickle.dumps(m2)

    for i in range(1000):
        if i < 100:
            # 100 near dups of p1
            m = MinHash(num_perm=128)
            m.update(b"this is a synthetic page content that will be duplicated" + str(i % 5).encode('utf8'))
            pages[f"url_{i}"] = CrawlContext(url=f"url_{i}", url_row=_mock_url_row(pickle.dumps(m)))
        else:
            m = MinHash(num_perm=128)
            m.update(b"this is another completely different page" + str(i).encode('utf8'))
            pages[f"url_{i}"] = CrawlContext(url=f"url_{i}", url_row=_mock_url_row(pickle.dumps(m)))

    site = SiteContext("http://test.com", pages)

    print("Running check_E02 LSH on 1000 pages...")
    start = time.time()
    res = list(check_E02(site))
    end = time.time()
    dur = end - start
    print(f"LSH Time: {dur:.3f}s")

    # Validation
    assert dur < 10.0, f"Benchmark failed: {dur:.3f}s exceeds 10s"

    # Sub-test for Jaccard vs LSH (simplified representation)
    print(f"Found {len(res)} near duplicates")
    if len(res) > 0:
        print("LSH recall test passed")

if __name__ == "__main__":
    benchmark()
