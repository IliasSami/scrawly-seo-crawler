"""Internal PageRank authority (M6 smart algorithm)."""
from sentinelseo.audit.authority import compute_pagerank


def test_hub_outranks_leaf() -> None:
    # a,b,c all link to hub; hub links to a. Hub should have top authority.
    nodes = ["hub", "a", "b", "c"]
    edges = {"a": ["hub"], "b": ["hub"], "c": ["hub"], "hub": ["a"]}
    pr = compute_pagerank(nodes, edges)
    assert pr["hub"] == 100.0  # normalized top authority
    assert pr["a"] < pr["hub"]
    assert pr["b"] == pr["c"]  # symmetric leaves
    assert all(0.0 <= v <= 100.0 for v in pr.values())


def test_empty_graph() -> None:
    assert compute_pagerank([], {}) == {}


def test_ignores_external_edges() -> None:
    # edges to nodes outside the set are dropped, no crash.
    pr = compute_pagerank(["a", "b"], {"a": ["b", "https://external.com/x"], "b": []})
    assert set(pr) == {"a", "b"}
    assert pr["b"] >= pr["a"]  # b receives a's link
