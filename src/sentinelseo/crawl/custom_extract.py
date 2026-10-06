"""Custom extraction + search — Scrawly's site-wide scraper (SF parity).

Runs user-defined CSS selectors / regexes against each crawled page and records
the results per URL. Opt-in (only runs when a profile defines extractors), so the
default crawl stays lean.

Extractor: {"name": str, "source": "css"|"xpath"|"regex", "expr": str, "attr"?: str}
  - css   → text of matched nodes (or a named attribute when "attr" is set)
  - xpath → text/attr of matched nodes (lxml; supports @attr and text() exprs)
  - regex → capture group 1 (or the whole match) for every match in the raw HTML
Search:    {"name": str, "regex": str}  → count of matches in the raw HTML
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from selectolax.lexbor import LexborHTMLParser


def run_custom_extraction(
    html: str,
    extractors: Optional[List[Dict[str, Any]]] = None,
    searches: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Return {name: [values]} for extractors and {"search:name": count} for searches."""
    result: Dict[str, Any] = {}
    tree: Optional[LexborHTMLParser] = None
    lxml_doc: Any = None

    for ex in extractors or []:
        name = (ex.get("name") or "").strip()
        expr = (ex.get("expr") or "").strip()
        source = ex.get("source") or "css"
        if not name or not expr:
            continue
        if source == "css":
            if tree is None:
                tree = LexborHTMLParser(html)
            attr = ex.get("attr")
            vals: List[str] = []
            for node in tree.css(expr):
                v = node.attributes.get(attr) if attr else node.text(strip=True)
                if v:
                    vals.append(str(v))
            result[name] = vals
        elif source == "xpath":
            from lxml import html as _lh  # type: ignore[import-untyped]

            if lxml_doc is None:
                try:
                    lxml_doc = _lh.fromstring(html)
                except Exception:
                    result[name] = []
                    continue
            try:
                matches = lxml_doc.xpath(expr)
            except Exception:
                result[name] = []
                continue
            xvals: List[str] = []
            for m in matches:
                if isinstance(m, str):
                    t = m.strip()
                elif hasattr(m, "text_content"):
                    t = m.text_content().strip()
                else:
                    t = str(m).strip()
                if t:
                    xvals.append(t)
            result[name] = xvals
        elif source == "regex":
            try:
                rx = re.compile(expr)
            except re.error:
                result[name] = []
                continue
            result[name] = [
                (m.group(1) if m.groups() else m.group(0)) for m in rx.finditer(html)
            ]

    for s in searches or []:
        name = (s.get("name") or "").strip()
        pattern = (s.get("regex") or "").strip()
        if not name or not pattern:
            continue
        try:
            count = len(re.findall(pattern, html))
        except re.error:
            count = 0
        result[f"search:{name}"] = count

    return result
