from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LinkRef:
    href: str
    anchor: str
    rel: tuple[str, ...]
    is_internal: bool
    source_in: str


@dataclass
class ImageRef:
    src: str
    alt: Optional[str]
    bytes: Optional[int]
    natural_w: Optional[int]
    natural_h: Optional[int]
    rendered_w: Optional[int]
    rendered_h: Optional[int]
    loading: Optional[str]
    is_background: bool = False
    srcset: Optional[str] = None


@dataclass
class ResourceRef:
    """A non-page sub-resource referenced by a page (CSS / JS / media). Status,
    content-type and size are filled in by the crawler's resource sweep."""
    url: str
    type: str          # css | js | media
    from_page: str
    status: Optional[int] = None
    content_type: Optional[str] = None
    size: Optional[int] = None
    ref_count: int = 0  # how many pages reference this resource (filled post-sweep)


@dataclass
class URLRow:
    address: str
    status: int
    redirect_chain: list[str]
    title: Optional[str]
    meta_desc: Optional[str]
    canonical: Optional[str]
    meta_robots: Optional[str]
    x_robots: Optional[str]
    h1: list[str]
    h2: list[str]
    h3: list[str]
    h4: list[str]
    h5: list[str]
    h6: list[str]
    word_count: int
    content_hash: str
    near_dup_cluster: str
    ttfb: float
    size: int
    inlink_count: int
    outlink_count: int
    indexable: bool
    indexability_reason: Optional[str]
    internal_links: list[str] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)

    # --- New fields ---
    requested_url: Optional[str] = None
    fetched_at: Optional[str] = None
    headers: dict[str, str] = field(default_factory=dict)
    content_type: Optional[str] = None
    html_response: Optional[str] = None
    html_render: Optional[str] = None
    mobile_context: Optional[Any] = None
    agentic_context: Optional[Any] = None
    title_count: int = 0
    meta_desc_count: int = 0
    canonical_count: int = 0
    canonical_in_head: bool = False
    canonical_raw: Optional[str] = None
    meta_keywords: Optional[str] = None
    viewport: Optional[str] = None
    lang: Optional[str] = None
    hreflang: list[tuple[str, str]] = field(default_factory=list)
    og: dict[str, str] = field(default_factory=dict)
    twitter: dict[str, str] = field(default_factory=dict)
    links: list[LinkRef] = field(default_factory=list)
    images: list[ImageRef] = field(default_factory=list)
    resources: list["ResourceRef"] = field(default_factory=list)
    # Title/Author/Subject/dates/page+word count for application/pdf rows.
    pdf_properties: dict[str, Any] = field(default_factory=dict)
    # Segment name assigned post-crawl by the config's segment rules (Pattern N).
    segment: Optional[str] = None
    # JS console errors/warnings captured during render (SF JS error reporting).
    js_errors: list[str] = field(default_factory=list)
    jsonld: list[dict[str, Any]] = field(default_factory=list)
    microdata_types: list[str] = field(default_factory=list)
    rdfa_types: list[str] = field(default_factory=list)
    main_text: str = ""
    full_text: str = ""
    minhash: Optional[bytes] = None
    dom_node_count: int = 0
    html_bytes: int = 0
    text_bytes: int = 0
    render_ms: Optional[float] = None
    in_sitemap: bool = False
    depth: Optional[int] = None
    # Core Web Vitals: lab (Playwright render) or field (PSI/CrUX) when available.
    lcp_s: Optional[float] = None
    cls: Optional[float] = None
    inp_ms: Optional[float] = None  # field-only (needs real-user data via PSI/CrUX)
    # M4 extraction depth
    readability: Optional[float] = None
    text_to_code: Optional[float] = None
    forms_count: int = 0
    # Link types
    prev_url: Optional[str] = None
    next_url: Optional[str] = None
    amp_url: Optional[str] = None
    mobile_alternate: Optional[str] = None


@dataclass
class UrlRenderDiffRow:
    url: str
    element: str
    state: str


@dataclass
class ImageRow:
    url: str
    src: str
    alt: str
    size_kb: float
    has_dimensions: bool


@dataclass
class StructuredDataRow:
    url: str
    type: str
    format: str
    valid: bool
    missing_required: list[str]
    missing_recommended: list[str]
    jsonld_parse_errors: list[str] = field(default_factory=list)


# --- New Context Models ---
@dataclass
class MobileContext:
    mobile_text: str
    mobile_html: str
    smallTapTargets: int
    contentWiderThanViewport: bool
    blocked_resources: set[str]
    smallFonts: int = 0
    hasInterstitial: bool = False


@dataclass
class AgenticContext:
    post_load_cls: float
    webmcp_probe_result: dict[str, Any]
    axe_violations: list[str]
    js_errors: list[str] = field(default_factory=list)


@dataclass
class AIAccessMatrix:
    matrix: dict[str, dict[str, bool | str]]


@dataclass
class ExternalStatus:
    cache: dict[str, int]


@dataclass
class CWVContext:
    lcp_s: float
    inp_ms: float
    cls: float
    source: str
