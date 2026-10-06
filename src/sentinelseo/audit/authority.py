"""Internal link authority — PageRank over the site's own link graph.

Traditional crawlers report raw inlink counts; PageRank captures *transitive*
authority (a link from a highly-linked hub is worth more than one from an
orphan), which is far closer to how search engines value internal links.
"""
from __future__ import annotations

from typing import Dict, List


def compute_pagerank(
    nodes: List[str],
    edges: Dict[str, List[str]],
    damping: float = 0.85,
    iterations: int = 40,
) -> Dict[str, float]:
    """Iterative PageRank. `edges[src]` = list of internal target addresses.

    Returns each node's rank normalized to 0-100 (relative internal authority).
    """
    n = len(nodes)
    if n == 0:
        return {}
    node_set = set(nodes)
    out: Dict[str, List[str]] = {
        src: [t for t in edges.get(src, []) if t in node_set] for src in nodes
    }
    pr: Dict[str, float] = dict.fromkeys(nodes, 1.0 / n)

    for _ in range(iterations):
        dangling = sum(pr[node] for node in nodes if not out[node])
        base = (1.0 - damping) / n + damping * dangling / n
        new: Dict[str, float] = dict.fromkeys(nodes, base)
        for src in nodes:
            targets = out[src]
            if not targets:
                continue
            share = damping * pr[src] / len(targets)
            for tgt in targets:
                new[tgt] += share
        pr = new

    top = max(pr.values()) if pr else 0.0
    if top <= 0:
        return dict.fromkeys(nodes, 0.0)
    return {node: round(100.0 * pr[node] / top, 1) for node in nodes}
