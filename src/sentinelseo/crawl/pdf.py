"""PDF handling (SF Extraction ▸ PDF).

A PDF reached by a crawl is a real indexable document — Google converts it and
maps its Title/Keywords onto the title/meta-keywords it indexes. Running the HTML
parser over PDF bytes produces garbage, so PDFs get their own row builder here.

`extract_pdf` (config) gates the *properties* extraction: with it off the PDF is
still crawled and status-checked, it just carries no Author/PageCount/etc.
"""
from __future__ import annotations

import io
import re
from typing import Any, Dict, Optional

from sentinelseo.crawl.models import URLRow

PDF_CONTENT_TYPE = "application/pdf"


def is_pdf(content_type: Optional[str], url: str = "") -> bool:
    """PDF by declared content-type, or by extension when the server is vague."""
    ct = (content_type or "").lower()
    if PDF_CONTENT_TYPE in ct:
        return True
    if ct and not ct.startswith(("application/octet-stream", "binary/")):
        return False  # server was explicit about something else
    return url.lower().split("?")[0].endswith(".pdf")


def extract_pdf_properties(content: bytes) -> Dict[str, Any]:
    """Title/Author/Subject/dates/page-count/word-count from PDF bytes.
    Best-effort: a malformed or encrypted PDF yields whatever could be read."""
    props: Dict[str, Any] = {}
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        try:
            props["page_count"] = len(reader.pages)
        except Exception:  # noqa: BLE001
            pass
        meta = getattr(reader, "metadata", None)
        if meta:
            for key, attr in (
                ("title", "title"), ("author", "author"), ("subject", "subject"),
                ("creator", "creator"), ("producer", "producer"),
            ):
                try:
                    val = getattr(meta, attr, None)
                    if val:
                        props[key] = str(val).strip()
                except Exception:  # noqa: BLE001
                    continue
            for key, attr in (("created", "creation_date"), ("modified", "modification_date")):
                try:
                    val = getattr(meta, attr, None)
                    if val:
                        props[key] = val.isoformat() if hasattr(val, "isoformat") else str(val)
                except Exception:  # noqa: BLE001
                    continue
        # Word count over the first pages only — full text extraction is slow and
        # a crawl-level word count doesn't need page 400 of a manual.
        words = 0
        try:
            for page in reader.pages[:25]:
                text = page.extract_text() or ""
                words += len(re.findall(r"\b\w+\b", text))
            props["word_count"] = words
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001 - never let a bad PDF break the crawl
        props.setdefault("error", "unreadable")
    return props


def build_pdf_row(
    url: str,
    status: int,
    headers: Dict[str, str],
    content: bytes,
    extract_properties: bool = True,
) -> URLRow:
    """A URLRow for a PDF: real status/size/indexability, PDF props instead of
    HTML fields. Title falls back to the PDF's own Title (what Google indexes)."""
    props = extract_pdf_properties(content) if extract_properties else {}
    x_robots = headers.get("x-robots-tag") or headers.get("X-Robots-Tag")
    indexable = not (x_robots and "noindex" in str(x_robots).lower()) and status == 200
    reason = None
    if status != 200:
        reason = f"HTTP {status}"
    elif x_robots and "noindex" in str(x_robots).lower():
        reason = "X-Robots-Tag: noindex"

    return URLRow(
        address=url,
        status=status,
        redirect_chain=[],
        title=props.get("title") or None,
        meta_desc=props.get("subject") or None,   # Google maps Subject-ish metadata
        canonical=None,
        meta_robots=None,
        x_robots=str(x_robots) if x_robots else None,
        h1=[], h2=[], h3=[], h4=[], h5=[], h6=[],
        word_count=int(props.get("word_count") or 0),
        content_hash="",
        near_dup_cluster="",
        ttfb=0.0,
        size=len(content),
        inlink_count=0,
        outlink_count=0,
        indexable=indexable,
        indexability_reason=reason,
        content_type=PDF_CONTENT_TYPE,
        headers=dict(headers),
        pdf_properties=props,
    )
