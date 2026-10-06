"""Embeddings provider (SF Pattern J) — bring your own, on demand.

Deliberately a *separate* provider from the chat AI: chat routers frequently
don't proxy an embeddings endpoint (the configured Nara router, for instance,
serves 32 chat models and returns 404 on /v1/embeddings), so reusing the chat
credential would silently fail. Configure an OpenAI-compatible embeddings
endpoint (OpenAI, Ollama, Mistral, ...) and everything downstream lights up.

    SCRAWLY_EMBED_BASE_URL=https://api.openai.com/v1
    SCRAWLY_EMBED_MODEL=text-embedding-3-small
    SCRAWLY_EMBED_KEY=...            # omit for a local Ollama endpoint

Nothing here requires a key to ship: with no provider configured, is_configured()
is False and the semantic filters simply stay empty (SF's own behaviour).
"""
from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional


def embed_config(settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Resolve the embeddings provider.

    The credential-bearing fields (base_url + key) come from the ENVIRONMENT ONLY,
    never the persisted settings dict. Otherwise an attacker who can reach the
    unauthenticated PUT /api/settings could point base_url at their own host and
    have the server forward the real env key to them (SSRF + secret exfiltration),
    and the key would also be echoed back in cleartext by GET /api/settings. The
    non-secret model name may still come from settings for convenience.
    """
    s = settings or {}
    return {
        "base_url": (os.environ.get("SCRAWLY_EMBED_BASE_URL") or "").strip(),
        "model": (s.get("embed_model") or os.environ.get("SCRAWLY_EMBED_MODEL") or "").strip(),
        "api_key": (os.environ.get("SCRAWLY_EMBED_KEY") or "").strip(),
    }


def is_configured(cfg: Optional[Dict[str, Any]] = None) -> bool:
    """A local Ollama endpoint needs no key — only base_url + model are required."""
    c = cfg or embed_config()
    return bool(c.get("base_url") and c.get("model"))


def embed_texts(
    texts: List[str], cfg: Optional[Dict[str, Any]] = None, batch_size: int = 96
) -> List[List[float]]:
    """Embed texts via an OpenAI-compatible /embeddings endpoint, in batches.

    Returns a list aligned 1:1 with `texts` (empty on any failure — never raises
    into a crawl). If the provider ever returns a mismatched count for a batch,
    the whole call fails closed (returns []) rather than silently mis-aligning
    vectors to the wrong URLs.
    """
    c = cfg or embed_config()
    if not is_configured(c) or not texts:
        return []
    import httpx

    headers = {"Content-Type": "application/json"}
    if c.get("api_key"):
        headers["Authorization"] = f"Bearer {c['api_key']}"
    url = f"{c['base_url'].rstrip('/')}/embeddings"
    out: List[List[float]] = []
    try:
        for i in range(0, len(texts), max(1, batch_size)):
            chunk = texts[i:i + max(1, batch_size)]
            r = httpx.post(url, headers=headers, timeout=60,
                           json={"model": c["model"], "input": chunk})
            if r.status_code != 200:
                return []
            data = r.json().get("data") or []
            data = sorted(data, key=lambda d: d.get("index", 0))  # stable order
            vecs = [list(d.get("embedding") or []) for d in data]
            if len(vecs) != len(chunk):
                return []      # count mismatch → fail closed, don't mis-align
            out.extend(vecs)
        return out
    except Exception:  # noqa: BLE001
        return []


def test_connection(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One-shot probe for the Settings UI."""
    c = cfg or embed_config()
    if not is_configured(c):
        return {"ok": False, "detail": "No embeddings provider configured (base URL + model)."}
    vecs = embed_texts(["scrawly connection test"], c)
    if not vecs or not vecs[0]:
        return {"ok": False, "detail": f"'{c['model']}' returned no embedding from {c['base_url']}."}
    return {"ok": True, "model": c["model"], "dimensions": len(vecs[0])}


def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return 0.0 if not na or not nb else dot / (na * nb)


def find_similar(
    vectors: Dict[str, List[float]], threshold: float = 0.92
) -> List[Dict[str, Any]]:
    """Semantically-similar page pairs above `threshold` (Pattern J).
    O(n²) over the crawl — fine at audit scale, and only runs when opted in."""
    urls = [u for u, v in vectors.items() if v]
    out: List[Dict[str, Any]] = []
    for i, a in enumerate(urls):
        for b in urls[i + 1:]:
            sim = cosine(vectors[a], vectors[b])
            if sim >= threshold:
                out.append({"a": a, "b": b, "similarity": round(sim, 4)})
    return sorted(out, key=lambda d: -float(d["similarity"]))


def find_low_relevance(
    vectors: Dict[str, List[float]], threshold: float = 0.6
) -> List[Dict[str, Any]]:
    """Pages whose closest sibling is still distant — orphaned topically, i.e.
    content that doesn't belong to any cluster on the site."""
    urls = [u for u, v in vectors.items() if v]
    out: List[Dict[str, Any]] = []
    for a in urls:
        best = max((cosine(vectors[a], vectors[b]) for b in urls if b != a), default=0.0)
        if best < threshold:
            out.append({"url": a, "max_similarity": round(best, 4)})
    return sorted(out, key=lambda d: float(d["max_similarity"]))
