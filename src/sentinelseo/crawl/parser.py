import hashlib
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from datasketch import MinHash  # type: ignore
from selectolax.lexbor import LexborHTMLParser

from .models import (
    ImageRef,
    LinkRef,
    ResourceRef,
    StructuredDataRow,
    UrlRenderDiffRow,
    URLRow,
)


def get_md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


_VOWEL_RUN = re.compile(r"[aeiouy]+", re.I)


def _count_syllables(word: str) -> int:
    w = word.lower().strip(".,!?;:\"'()")
    if not w:
        return 0
    n = len(_VOWEL_RUN.findall(w))
    if w.endswith("e") and n > 1:  # drop a common silent 'e'
        n -= 1
    return max(1, n)


def flesch_reading_ease(text: str) -> Optional[float]:
    """Flesch Reading Ease (0-100+, higher = easier). None for empty text."""
    words = text.split()
    if not words:
        return None
    sentences = max(1, len(re.findall(r"[.!?]+", text)))
    syllables = sum(_count_syllables(w) for w in words)
    score = (
        206.835
        - 1.015 * (len(words) / sentences)
        - 84.6 * (syllables / len(words))
    )
    return round(score, 1)


def get_minhash(text: str) -> MinHash:
    m = MinHash(num_perm=128)
    words = text.split()
    # 5-word shingles
    for i in range(len(words) - 4):
        shingle = " ".join(words[i:i+5])
        m.update(shingle.encode("utf-8"))
    # If text is too short, just hash the whole text
    if len(words) < 5 and words:
        m.update(text.encode("utf-8"))
    return m


def _content_area_text(
    html_str: str, include: str = "", exclude: str = ""
) -> Optional[str]:
    """Extract the SF-style "Content Area" text: the text used for word count,
    duplicate detection, readability, spelling and embeddings. `exclude` (a CSS
    selector, comma-separated allowed) drops boilerplate like nav/footer;
    `include` restricts to specific regions. Parses a throwaway tree so the
    caller's tree — used for metadata extraction — is never mutated. Returns
    None when the selectors are empty (caller keeps the default body text) or
    when a selector is invalid / matches nothing."""
    include = (include or "").strip()
    exclude = (exclude or "").strip()
    if not include and not exclude:
        return None
    ct = LexborHTMLParser(html_str)
    for tag in ct.css("script, style"):
        tag.decompose()
    if exclude:
        try:
            for node in ct.css(exclude):
                node.decompose()
        except Exception:
            pass
    if include:
        try:
            nodes = ct.css(include)
        except Exception:
            nodes = []
        text = " ".join(n.text(separator=" ", strip=True) for n in nodes).strip()
        return text or None
    body = ct.css_first("body")
    return (body.text(separator=" ", strip=True) if body else "") or None


def _extract_meta(tree: LexborHTMLParser, name: str) -> Optional[str]:
    node = tree.css_first(f'meta[name="{name}"]')
    if node and node.attributes.get("content"):
        return str(node.attributes["content"])
    return None

def _extract_meta_property(tree: LexborHTMLParser, name: str) -> Optional[str]:
    node = tree.css_first(f'meta[property="{name}"]')
    if node and node.attributes.get("content"):
        return str(node.attributes["content"])
    return None

def _extract_canon(tree: LexborHTMLParser) -> Optional[str]:
    node = tree.css_first('link[rel="canonical"]')
    if node and node.attributes.get("href"):
        return str(node.attributes["href"])
    return None


def _extract_headings(tree: LexborHTMLParser, level: int) -> List[str]:
    nodes = tree.css(f"h{level}")
    return [
        n.text(strip=True) for n in nodes if n.text(strip=True)
    ]


def _extract_links(tree: LexborHTMLParser, base_url: str) -> tuple[List[str], List[str], List[LinkRef]]:  # noqa: E501
    internal = []
    external = []
    link_refs = []
    from urllib.parse import urlparse
    base_domain = urlparse(base_url).netloc

    for a in tree.css("a[href]"):
        href = a.attributes.get("href")
        if not href or not isinstance(href, str):
            continue
        href = href.strip()
        # Only web links are crawlable: skip mailto:, tel:, javascript:, sms:,
        # whatsapp:, data: ... in any letter case (JavaScript:, " mailto:").
        scheme = urlparse(href).scheme.lower()
        if not href or (scheme and scheme not in ("http", "https")):
            continue
        full_url = urljoin(base_url, href)

        is_internal = urlparse(full_url).netloc == base_domain
        if is_internal:
            internal.append(full_url)
        else:
            external.append(full_url)

        anchor = a.text(strip=True)
        rel_str = a.attributes.get("rel", "")
        rel = tuple(rel_str.split()) if rel_str else ()

        link_refs.append(LinkRef(
            href=full_url,
            anchor=anchor,
            rel=rel,
            is_internal=is_internal,
            source_in="response" # will be modified if needed by render diff later
        ))

    return internal, external, link_refs


def _extract_resources(tree: LexborHTMLParser, base_url: str) -> List[ResourceRef]:
    """Non-page sub-resources a page pulls in (SF Pattern A): CSS, JS, media.
    Status/type/size are resolved later by the crawler's resource sweep."""
    out: List[ResourceRef] = []
    seen: set[str] = set()

    def add(raw: Optional[str], kind: str) -> None:
        if not raw or not isinstance(raw, str):
            return
        if raw.startswith(("data:", "javascript:", "blob:", "mailto:", "about:")):
            return
        full = urljoin(base_url, raw)
        key = f"{kind}|{full}"
        if key in seen:
            return
        seen.add(key)
        out.append(ResourceRef(url=full, type=kind, from_page=base_url))

    # CSS — <link rel=stylesheet> (rel may carry multiple tokens e.g. "preload stylesheet")
    for link in tree.css("link[href]"):
        rel = str(link.attributes.get("rel", "")).lower()
        as_ = str(link.attributes.get("as", "")).lower()
        if "stylesheet" in rel or (rel == "preload" and as_ == "style"):
            add(link.attributes.get("href"), "css")
    # JS — <script src>
    for s in tree.css("script[src]"):
        add(s.attributes.get("src"), "js")
    # Media — <video>/<audio>/<source>/<track>
    for m in tree.css("video[src], audio[src]"):
        add(m.attributes.get("src"), "media")
    for src in tree.css("video source[src], audio source[src], picture source[srcset]"):
        add(src.attributes.get("src") or src.attributes.get("srcset"), "media")
    return out


def _extract_images(tree: LexborHTMLParser, base_url: str) -> List[ImageRef]:
    imgs = []
    for img in tree.css("img"):
        src = img.attributes.get("src")
        if not src or not isinstance(src, str):
            continue
        full_url = urljoin(base_url, src)

        alt = img.attributes.get("alt")

        width = img.attributes.get("width")
        height = img.attributes.get("height")

        w_int = int(width) if width and width.isdigit() else None
        h_int = int(height) if height and height.isdigit() else None

        loading = img.attributes.get("loading")
        srcset = img.attributes.get("srcset")

        imgs.append(
            ImageRef(
                src=full_url,
                alt=alt,
                bytes=None,
                natural_w=None,
                natural_h=None,
                rendered_w=w_int,
                rendered_h=h_int,
                loading=loading,
                is_background=False,
                srcset=str(srcset) if srcset else None,
            )
        )
    return imgs


def _extract_structured_data(
    tree: LexborHTMLParser, base_url: str
) -> tuple[List[StructuredDataRow], List[dict[str, Any]], List[str]]:
    sd_list = []
    jsonld_list = []
    parse_errors = []

    for script in tree.css('script[type="application/ld+json"]'):
        content = script.text()
        if not content:
            continue
        try:
            data = json.loads(content)
            jsonld_list.append(data)

            # handle case where data is a list of jsonld objects
            if isinstance(data, list):
                types = [item.get("@type", "Unknown") for item in data if isinstance(item, dict)]  # noqa: E501
                types_str = ", ".join(str(t) for t in types)
            else:
                types_str = str(data.get("@type", "Unknown"))

            sd_list.append(
                StructuredDataRow(
                    url=base_url,
                    type=types_str,
                    format="jsonld",
                    valid=True,
                    missing_required=[],
                    missing_recommended=[],
                    jsonld_parse_errors=[]
                )
            )
        except Exception as e:
            parse_errors.append(str(e))
            sd_list.append(
                StructuredDataRow(
                    url=base_url,
                    type="Unknown",
                    format="jsonld",
                    valid=False,
                    missing_required=[],
                    missing_recommended=[],
                    jsonld_parse_errors=[str(e)]
                )
            )
    return sd_list, jsonld_list, parse_errors


def parse_html(
    url: str, html: str, status: int = 200, headers: Optional[Dict[str, str]] = None,
    content_include: str = "", content_exclude: str = "",
) -> tuple[URLRow, List[ImageRef], List[StructuredDataRow]]:
    tree = LexborHTMLParser(html)

    title_tags = tree.css("title")
    title_count = len(title_tags)
    title = title_tags[0].text(strip=True) if title_count > 0 else None

    meta_desc_tags = tree.css('meta[name="description"]')
    meta_desc_count = len(meta_desc_tags)
    meta_desc = meta_desc_tags[0].attributes.get("content") if meta_desc_count > 0 else None  # noqa: E501
    if isinstance(meta_desc, str):
        meta_desc = str(meta_desc)

    meta_robots = _extract_meta(tree, "robots")

    canon_tags = tree.css('link[rel="canonical"]')
    canonical_count = len(canon_tags)

    canonical_raw = None
    canonical_in_head = False
    canonical = None

    if canonical_count > 0:
        canon_node = canon_tags[0]
        canonical_raw = canon_node.attributes.get("href")
        if canonical_raw:
            canonical_raw = str(canonical_raw)
            canonical = urljoin(url, canonical_raw)

        parent = canon_node.parent
        while parent:
            if parent.tag == "head":
                canonical_in_head = True
                break
            parent = parent.parent

    h1 = _extract_headings(tree, 1)
    h2 = _extract_headings(tree, 2)
    h3 = _extract_headings(tree, 3)
    h4 = _extract_headings(tree, 4)
    h5 = _extract_headings(tree, 5)
    h6 = _extract_headings(tree, 6)

    internal_links, external_links, link_refs = _extract_links(tree, url)
    images = _extract_images(tree, url)
    resources = _extract_resources(tree, url)
    sd, jsonld, parse_errors = _extract_structured_data(tree, url)

    # Microdata (itemtype) + RDFa (typeof) type names — Google prefers JSON-LD,
    # so surfacing these lets a check flag markup that isn't JSON-LD.
    microdata_types: List[str] = []
    for node in tree.css("[itemtype]"):
        it = node.attributes.get("itemtype")
        if it:
            microdata_types.append(str(it).rstrip("/").split("/")[-1])
    rdfa_types: List[str] = []
    for node in tree.css("[typeof]"):
        tf = node.attributes.get("typeof")
        if tf:
            rdfa_types.extend(str(tf).split())
    microdata_types = list(dict.fromkeys(microdata_types))
    rdfa_types = list(dict.fromkeys(rdfa_types))

    dom_node_count = len(tree.css("*"))

    # Clean text (strip scripts and styles)
    for tag in tree.css("script, style"):
        tag.decompose()

    body = tree.css_first("body")
    text_content = body.text(separator=" ", strip=True) if body else ""
    full_text = tree.text(separator=" ", strip=True)

    # SF "Content Area": when include/exclude selectors are configured, the text
    # that drives word count / duplicates / readability / spelling / embeddings
    # is taken from that restricted region instead of the whole body.
    _area = _content_area_text(html, content_include, content_exclude)
    if _area is not None:
        text_content = _area

    word_count = len(text_content.split())
    content_hash = get_md5(text_content)

    mh = get_minhash(text_content)
    near_dup_cluster = "".join([hex(x)[2:].zfill(8) for x in mh.hashvalues[:4]])

    x_robots = headers.get("x-robots-tag") if headers else None

    og = {}
    for node in tree.css('meta[property^="og:"]'):
        prop = node.attributes.get("property")
        content = node.attributes.get("content")
        if prop and content:
            og[prop] = content

    twitter = {}
    for node in tree.css('meta[name^="twitter:"]'):
        name = node.attributes.get("name")
        content = node.attributes.get("content")
        if name and content:
            twitter[name] = content

    html_node = tree.css_first("html")
    lang = html_node.attributes.get("lang") if html_node else None

    hreflang = []
    for node in tree.css('link[rel="alternate"][hreflang]'):
        hl = node.attributes.get("hreflang")
        href = node.attributes.get("href")
        if hl and href:
            hreflang.append((hl, href))

    # Pagination (rel next/prev), AMP (rel amphtml), mobile-alternate link types.
    def _rel_href(selector: str) -> Optional[str]:
        node = tree.css_first(selector)
        href = node.attributes.get("href") if node else None
        return urljoin(url, str(href)) if href else None

    prev_url = _rel_href('link[rel="prev"]')
    next_url = _rel_href('link[rel="next"]')
    amp_url = _rel_href('link[rel="amphtml"]')
    mobile_alternate = _rel_href('link[rel="alternate"][media]')

    html_bytes = len(html.encode("utf-8"))
    text_bytes = len(full_text.encode("utf-8"))

    # M4 extraction depth: readability, text-to-code ratio, form count.
    readability = flesch_reading_ease(text_content)
    text_to_code = round(text_bytes / html_bytes, 4) if html_bytes else 0.0
    forms_count = len(tree.css("form"))

    url_row = URLRow(
        address=url,
        status=status,
        redirect_chain=[],
        title=title,
        meta_desc=meta_desc,
        canonical=canonical,
        meta_robots=meta_robots,
        x_robots=x_robots,
        h1=h1,
        h2=h2,
        h3=h3,
        h4=h4,
        h5=h5,
        h6=h6,
        word_count=word_count,
        readability=readability,
        text_to_code=text_to_code,
        forms_count=forms_count,
        microdata_types=microdata_types,
        rdfa_types=rdfa_types,
        prev_url=prev_url,
        next_url=next_url,
        amp_url=amp_url,
        mobile_alternate=mobile_alternate,
        content_hash=content_hash,
        near_dup_cluster=near_dup_cluster,
        ttfb=0.0,
        size=len(html),
        inlink_count=0,
        outlink_count=0,
        indexable=True,
        indexability_reason=None,
        internal_links=internal_links,
        external_links=external_links,
        headers=headers or {},
        html_response=html,
        title_count=title_count,
        meta_desc_count=meta_desc_count,
        canonical_count=canonical_count,
        canonical_in_head=canonical_in_head,
        canonical_raw=canonical_raw,
        meta_keywords=_extract_meta(tree, "keywords"),
        viewport=_extract_meta(tree, "viewport"),
        lang=lang,
        hreflang=hreflang,
        og=og,
        twitter=twitter,
        links=link_refs,
        images=images,
        resources=resources,
        jsonld=jsonld,
        main_text=text_content,
        full_text=full_text,
        minhash=mh.hashvalues.tobytes(), # we need bytes to store it in minhash Optional[bytes]  # noqa: E501
        dom_node_count=dom_node_count,
        html_bytes=html_bytes,
        text_bytes=text_bytes,
    )

    if meta_robots and "noindex" in meta_robots.lower():
        url_row.indexable = False
        url_row.indexability_reason = "meta_robots_noindex"
    elif x_robots and "noindex" in x_robots.lower():
        url_row.indexable = False
        url_row.indexability_reason = "x_robots_noindex"

    return url_row, images, sd


def _diff_value(raw: Any, rendered: Any) -> str:
    if raw == rendered:
        return "unchanged"
    if not raw and rendered:
        return "created"
    if raw and not rendered:
        return "deleted"
    return "modified"


def _diff_lists(raw: List[str], rendered: List[str]) -> str:
    set_r = set(raw)
    set_ren = set(rendered)
    if set_r == set_ren:
        if len(raw) != len(rendered):
            return "duplicated"
        return "unchanged"
    if not set_r and set_ren:
        return "created"
    if set_r and not set_ren:
        return "deleted"
    return "modified"


def compute_render_diff(
    url: str, raw_row: URLRow, rendered_row: URLRow
) -> List[UrlRenderDiffRow]:
    diffs = []

    attrs_scalar = [
        ("meta_robots", raw_row.meta_robots, rendered_row.meta_robots),
        ("canonical", raw_row.canonical, rendered_row.canonical),
        ("title", raw_row.title, rendered_row.title),
        ("meta_desc", raw_row.meta_desc, rendered_row.meta_desc),
    ]

    for attr, raw, ren in attrs_scalar:
        state = _diff_value(raw, ren)
        if state != "unchanged":
            diffs.append(UrlRenderDiffRow(url=url, element=attr, state=state))

    attrs_list = [
        ("internal_links", raw_row.internal_links, rendered_row.internal_links),
        ("external_links", raw_row.external_links, rendered_row.external_links),
    ]

    for attr, raw_l, ren_l in attrs_list:
        state = _diff_lists(raw_l, ren_l)
        if state != "unchanged":
            diffs.append(UrlRenderDiffRow(url=url, element=attr, state=state))

    # structured_data diff
    raw_sd = json.dumps(raw_row.jsonld, sort_keys=True)
    ren_sd = json.dumps(rendered_row.jsonld, sort_keys=True)
    state = _diff_value(raw_sd, ren_sd)
    if state != "unchanged":
        diffs.append(UrlRenderDiffRow(url=url, element="structured_data", state=state))

    return diffs
