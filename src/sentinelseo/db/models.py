from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):  # type: ignore[misc]
    pass


class Client(Base):
    __tablename__ = "client"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    base_url: Mapped[str] = mapped_column(String, nullable=False)
    canonical_nap: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    service_cities: Mapped[Optional[List[str]]] = mapped_column(JSON)
    plugin_stack: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    auth_ref: Mapped[Optional[str]] = mapped_column(
        String
    )  # encrypted App Password reference
    # Per-client Scrawly Connector plugin connection (guarded auto-fixes).
    wp_url: Mapped[Optional[str]] = mapped_column(String)
    wp_connection_key: Mapped[Optional[str]] = mapped_column(String)
    # How Scrawly reaches this site: url_only | wp_connector | connector_file |
    # ssh | credentials | mcp. Drives which capabilities (audit vs fix) are gated.
    connection_method: Mapped[Optional[str]] = mapped_column(String)
    detected_stack: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    # Hidden bucket that owns anonymous public-window audits (not shown in the
    # client list). Nullable/defaulted so the auto-migrator can add it in place.
    is_public: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)


class Crawl(Base):
    __tablename__ = "crawl"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"))
    # The URL actually crawled. For per-client audits this equals the client's
    # base_url; for public-window audits it's the anonymously submitted target.
    target_url: Mapped[Optional[str]] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    url_count: Mapped[int] = mapped_column(Integer, default=0)
    # Semantic-similarity / low-relevance pass (Pattern J), when embeddings ran.
    embeddings_report: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    # Origin-level Agentic Web readiness report (probes the site ROOT once, so
    # this is a single fixed-cost result per crawl rather than per-URL data).
    agentic_report: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)


class URL(Base):
    __tablename__ = "url"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    crawl_id: Mapped[int] = mapped_column(ForeignKey("crawl.id"))
    address: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[int] = mapped_column(Integer, nullable=True)
    redirect_chain: Mapped[Optional[List[str]]] = mapped_column(JSON)
    title: Mapped[Optional[str]] = mapped_column(String)
    meta_desc: Mapped[Optional[str]] = mapped_column(String)
    canonical: Mapped[Optional[str]] = mapped_column(String)
    meta_robots: Mapped[Optional[str]] = mapped_column(String)
    x_robots: Mapped[Optional[str]] = mapped_column(String)
    # Keeping this simple for MVP
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[Optional[str]] = mapped_column(String)
    near_dup_cluster: Mapped[Optional[str]] = mapped_column(String)
    ttfb: Mapped[Optional[float]] = mapped_column(Float)
    size: Mapped[Optional[int]] = mapped_column(Integer)
    inlink_count: Mapped[int] = mapped_column(Integer, default=0)
    outlink_count: Mapped[int] = mapped_column(Integer, default=0)
    indexable: Mapped[bool] = mapped_column(Boolean, default=True)
    indexability_reason: Mapped[Optional[str]] = mapped_column(String)
    depth: Mapped[Optional[int]] = mapped_column(Integer)
    lcp_s: Mapped[Optional[float]] = mapped_column(Float)
    cls: Mapped[Optional[float]] = mapped_column(Float)
    inp_ms: Mapped[Optional[float]] = mapped_column(Float)
    readability: Mapped[Optional[float]] = mapped_column(Float)
    text_to_code: Mapped[Optional[float]] = mapped_column(Float)
    forms_count: Mapped[Optional[int]] = mapped_column(Integer)
    microdata_types: Mapped[Optional[List[str]]] = mapped_column(JSON)
    rdfa_types: Mapped[Optional[List[str]]] = mapped_column(JSON)
    last_modified: Mapped[Optional[str]] = mapped_column(String)
    custom_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    prev_url: Mapped[Optional[str]] = mapped_column(String)
    next_url: Mapped[Optional[str]] = mapped_column(String)
    amp_url: Mapped[Optional[str]] = mapped_column(String)
    mobile_alternate: Mapped[Optional[str]] = mapped_column(String)
    cookies: Mapped[Optional[List[str]]] = mapped_column(JSON)
    pagerank: Mapped[Optional[float]] = mapped_column(Float)
    gsc_impressions: Mapped[Optional[int]] = mapped_column(Integer)
    gsc_clicks: Mapped[Optional[int]] = mapped_column(Integer)
    render_diff: Mapped[Optional[List[dict[str, Any]]]] = mapped_column(JSON)
    internal_links: Mapped[Optional[List[str]]] = mapped_column(JSON)
    h1: Mapped[Optional[List[str]]] = mapped_column(JSON)
    h2: Mapped[Optional[List[str]]] = mapped_column(JSON)
    images: Mapped[Optional[List[dict[str, Any]]]] = mapped_column(JSON)
    jsonld: Mapped[Optional[List[dict[str, Any]]]] = mapped_column(JSON)
    headers: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    # Stored HTML (SF Extraction: Store HTML / Store Rendered HTML) — opt-in via
    # config; null unless the profile enables them (avoids DB bloat by default).
    raw_html: Mapped[Optional[str]] = mapped_column(String)
    rendered_html: Mapped[Optional[str]] = mapped_column(String)
    # PDF document properties (Title/Author/Subject/dates/page+word count).
    pdf_properties: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    # Segment assigned by the profile's segment rules (SF Pattern N).
    segment: Mapped[Optional[str]] = mapped_column(String)
    # GA4 engagement metrics matched onto this URL (sessions, views, ...).
    ga4: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    # Spelling/grammar issues found in this page's content area (Pattern I).
    spelling: Mapped[Optional[List[dict[str, Any]]]] = mapped_column(JSON)
    # JS console errors/warnings captured during render (SF JS error reporting).
    js_errors: Mapped[Optional[List[str]]] = mapped_column(JSON)


class Resource(Base):
    """A non-page sub-resource (CSS / JS / media) discovered during a crawl and
    HEAD-checked for status/type/size (SF Pattern A resource sweep)."""
    __tablename__ = "resource"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    crawl_id: Mapped[int] = mapped_column(ForeignKey("crawl.id"))
    url: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # css | js | media
    status: Mapped[Optional[int]] = mapped_column(Integer)
    content_type: Mapped[Optional[str]] = mapped_column(String)
    size: Mapped[Optional[int]] = mapped_column(Integer)
    ref_count: Mapped[int] = mapped_column(Integer, default=0)


class Issue(Base):
    __tablename__ = "issue"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    crawl_id: Mapped[int] = mapped_column(ForeignKey("crawl.id"))
    check_id: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False)
    affected_url_ids: Mapped[List[int]] = mapped_column(JSON)
    wp_object_id: Mapped[Optional[str]] = mapped_column(String)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    why_it_matters: Mapped[Optional[str]] = mapped_column(String)
    recommended_fix: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="open")  # open, fixed, ignored


class AppSettings(Base):
    """Single-row table holding global crawl defaults (id is always 1)."""

    __tablename__ = "app_settings"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ConfigProfile(Base):
    """A named, reusable crawl-configuration profile (agency workflow).

    `data` holds a full crawl-settings dict. One profile may be flagged the
    default; a profile may optionally be scoped to a client.
    """

    __tablename__ = "config_profile"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_preset: Mapped[bool] = mapped_column(Boolean, default=False)
    client_id: Mapped[Optional[int]] = mapped_column(ForeignKey("client.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Fix(Base):
    __tablename__ = "fix"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issue.id"))
    check_id: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    before_state: Mapped[dict[str, Any]] = mapped_column(JSON)
    after_state: Mapped[dict[str, Any]] = mapped_column(JSON)
    applied_by: Mapped[str] = mapped_column(String)
    reverted: Mapped[bool] = mapped_column(Boolean, default=False)


class PromptKB(Base):
    """Knowledge base of stack-specific fix guidance.

    The prompt engine renders deterministic templates. This table is the layer
    that lets it *learn*: when a (check, stack) pair has no hand-written
    guidance, the AI provider is asked once, the result is stored here, and
    every later audit reuses it — so each pair costs one call, ever.

    Deliberately a plain, inspectable table rather than an opaque model: every
    row can be read, edited or deleted, and a bad generation is one UPDATE away
    from being fixed. `source` distinguishes human-authored rows (which always
    win) from generated ones.
    """

    __tablename__ = "prompt_kb"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    check_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    stack: Mapped[str] = mapped_column(String, nullable=False, index=True)
    guidance: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, default="ai")   # ai | manual
    model: Mapped[Optional[str]] = mapped_column(String)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
