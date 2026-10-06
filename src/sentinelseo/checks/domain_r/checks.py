from typing import Optional

from sentinelseo.checks.registry import CheckSpec, CrawlContext, Finding, register


def _blocked_meta_bots(ctx: CrawlContext, bots: list[str]) -> list[str]:
    """Return bot names that appear as `<meta name=bot content=...noindex...>`."""
    tree = ctx.dom(not ctx.raw_html)  # raw-first (matches raw_html or rendered_html)
    out = []
    for meta in tree.css("meta[name]"):
        name = (meta.attributes.get("name") or "").lower()
        content = (meta.attributes.get("content") or "").lower()
        if name in bots and "noindex" in content:
            out.append(name)
    return out


@register(
    CheckSpec(
        check_id="R01",
        domain="AI search readiness (GEO)",
        title="AI training crawlers blocked in robots.txt (GPTBot, ClaudeBot, CCBot, Google-Extended)",  # noqa: E501
        description="Detects: AI training crawlers blocked in robots.txt (GPTBot, ClaudeBot, CCBot, Google-Extended)",  # noqa: E501
        why_it_matters="Excluded from AI training/knowledge (a *choice*, but flag it)",
        default_severity="Info",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_R01(ctx: CrawlContext) -> Optional[Finding]:
    if not (ctx.raw_html or ctx.rendered_html):
        return None

    issues = _blocked_meta_bots(ctx, ["gptbot", "claudebot", "ccbot", "google-extended"])

    if issues:
        return Finding(
            check_id="R01",
            severity="Info",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"blocked_bots": issues},
            why_it_matters="Excluded from AI training/knowledge (a *choice*, but flag it)",  # noqa: E501
            recommended_fix="Review if blocking AI training bots is intentional.",
        )
    return None


@register(
    CheckSpec(
        check_id="R02",
        domain="AI search readiness (GEO)",
        title="AI **search** crawlers blocked (OAI-SearchBot, Claude-SearchBot, PerplexityBot)",  # noqa: E501
        description="Detects: AI **search** crawlers blocked (OAI-SearchBot, Claude-SearchBot, PerplexityBot)",  # noqa: E501
        why_it_matters="Excluded from AI search answers → visibility loss",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_R02(ctx: CrawlContext) -> Optional[Finding]:
    if not (ctx.raw_html or ctx.rendered_html):
        return None

    issues = _blocked_meta_bots(ctx, ["oai-searchbot", "claude-searchbot", "perplexitybot"])  # noqa: E501

    if issues:
        return Finding(
            check_id="R02",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"blocked_bots": issues},
            why_it_matters="Excluded from AI search answers → visibility loss",
            recommended_fix="Unblock AI search bots to retain visibility in generative search.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="R03",
        domain="AI search readiness (GEO)",
        title="AI user-fetch agents blocked (ChatGPT-User, Claude-User, Perplexity-User)",  # noqa: E501
        description="Detects: AI user-fetch agents blocked (ChatGPT-User, Claude-User, Perplexity-User)",  # noqa: E501
        why_it_matters="Users can't pull your page into AI",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_R03(ctx: CrawlContext) -> Optional[Finding]:
    if not (ctx.raw_html or ctx.rendered_html):
        return None

    issues = _blocked_meta_bots(ctx, ["chatgpt-user", "claude-user", "perplexity-user"])

    if issues:
        return Finding(
            check_id="R03",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"blocked_bots": issues},
            why_it_matters="Users can't pull your page into AI",
            recommended_fix="Allow AI user-fetch agents.",
        )
    return None


@register(
    CheckSpec(
        check_id="R04",
        domain="AI search readiness (GEO)",
        title="CDN/WAF (Cloudflare) silently blocks AI bots",
        description="Detects: CDN/WAF (Cloudflare) silently blocks AI bots",
        why_it_matters="AI traffic 403'd despite robots.txt allow",
        default_severity="High",
        fix_tier="FLAG",
        data_source="X",
        fix_template=None,
    )
)
def check_R04(ctx: CrawlContext) -> Optional[Finding]:
    # Pure function can't test external WAF easily, return None
    return None


@register(
    CheckSpec(
        check_id="R05",
        domain="AI search readiness (GEO)",
        title="Primary content client-side rendered (AI bots don't run JS)",
        description="Detects: Primary content client-side rendered (AI bots don't run JS)",  # noqa: E501
        why_it_matters="AI can't read content",
        default_severity="High",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_R05(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.raw_html or not ctx.rendered_html:
        return None

    raw_body = ctx.dom().css_first("body")
    rendered_body = ctx.dom(use_rendered=True).css_first("body")
    raw_text = raw_body.text(strip=True) if raw_body else ""
    rendered_text = rendered_body.text(strip=True) if rendered_body else ""

    # If rendered text is significantly larger (e.g. >2x)
    if len(rendered_text) > 100 and len(rendered_text) > len(raw_text) * 2:
        return Finding(
            check_id="R05",
            severity="High",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={
                "raw_length": len(raw_text),
                "rendered_length": len(rendered_text),
            },
            why_it_matters="AI can't read content",
            recommended_fix="Implement server-side rendering or dynamic rendering for bots.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="R06",
        domain="AI search readiness (GEO)",
        title="Content behind login/paywall/interaction",
        description="Detects: Content behind login/paywall/interaction",
        why_it_matters="Invisible to AI",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="R",
        fix_template=None,
    )
)
def check_R06(ctx: CrawlContext) -> Optional[Finding]:
    html = ctx.rendered_html or ctx.raw_html
    if not html:
        return None

    tree = ctx.dom(bool(ctx.rendered_html))

    has_password = tree.css_first('input[type="password"]') is not None
    has_paywall_class = False
    for el in tree.css("[class]"):
        cls = (el.attributes.get("class") or "").lower()
        if "paywall" in cls or "premium" in cls:
            has_paywall_class = True
            break

    if has_password or has_paywall_class:
        return Finding(
            check_id="R06",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={
                "has_password": has_password,
                "has_paywall_class": has_paywall_class,
            },
            why_it_matters="Invisible to AI",
            recommended_fix="Use flexible sampling or make key content public.",
        )
    return None


@register(
    CheckSpec(
        check_id="R07",
        domain="AI search readiness (GEO)",
        title="Missing answer-capsule structure (direct answer before context)",
        description="Detects: Missing answer-capsule structure (direct answer before context)",  # noqa: E501
        why_it_matters="Lower extraction/citation odds",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_R07(ctx: CrawlContext) -> Optional[Finding]:
    # Answer-capsule heuristic: substantial content that opens straight into a
    # heading with no lead paragraph is harder for AI to extract a direct answer.
    if not ctx.url_row or (getattr(ctx.url_row, "word_count", 0) or 0) < 300:
        return None
    main = ctx.dom().css_first("main, article, .entry-content, #content") or ctx.dom().css_first("body")  # noqa: E501
    if main is None:
        return None
    first_heading = main.css_first("h1, h2")
    first_para = main.css_first("p")
    para_text = first_para.text(strip=True) if first_para else ""
    if first_heading is not None and (first_para is None or len(para_text) < 40):
        return Finding(
            check_id="R07",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"lead_paragraph_chars": len(para_text)},
            why_it_matters="Lower extraction/citation odds",
            recommended_fix="Open with a concise direct-answer paragraph before the first heading.",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="R08",
        domain="AI search readiness (GEO)",
        title="Weak heading hierarchy / not scannable (one topic per section)",
        description="Detects: Weak heading hierarchy / not scannable (one topic per section)",  # noqa: E501
        why_it_matters="Harder to extract passages",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_R08(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.url_row:
        return None
    word_count = getattr(ctx.url_row, "word_count", 0) or 0
    h2s = getattr(ctx.url_row, "h2", None) or []
    # Substantial content with no subheadings is hard for AI to extract passages.
    if word_count > 400 and len(h2s) == 0:
        return Finding(
            check_id="R08",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"word_count": word_count, "h2_count": 0},
            why_it_matters="Harder to extract passages",
            recommended_fix="Break long content into scannable H2/H3 sections (one topic each).",  # noqa: E501
        )
    return None


@register(
    CheckSpec(
        check_id="R09",
        domain="AI search readiness (GEO)",
        title="Missing author + freshness signals (E-E-A-T for GEO)",
        description="Detects: Missing author + freshness signals (E-E-A-T for GEO)",
        why_it_matters="AI favors sourced, recent content",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_R09(ctx: CrawlContext) -> Optional[Finding]:
    html = ctx.rendered_html or ctx.raw_html
    if not html:
        return None

    tree = ctx.dom(bool(ctx.rendered_html))

    has_author = tree.css_first('meta[name="author"]') or tree.css_first(
        'meta[property="article:author"]'
    )
    has_date = tree.css_first('meta[property="article:published_time"]') or tree.css_first("time")  # noqa: E501

    if not has_author or not has_date:
        return Finding(
            check_id="R09",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"has_author": bool(has_author), "has_date": bool(has_date)},
            why_it_matters="AI favors sourced, recent content",
            recommended_fix="Add author and publish/modify date signals.",
        )
    return None


@register(
    CheckSpec(
        check_id="R10",
        domain="AI search readiness (GEO)",
        title="Missing/weak entity + Organization/Website schema",
        description="Detects: Missing/weak entity + Organization/Website schema",
        why_it_matters="AI can't confirm entity for citation",
        default_severity="Medium",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_R10(ctx: CrawlContext) -> Optional[Finding]:
    schemas = (
        [s.get("type", "").lower() for s in ctx.structured_data]
        if ctx.structured_data
        else []
    )
    if "organization" not in schemas and "website" not in schemas:
        return Finding(
            check_id="R10",
            severity="Medium",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"found_schemas": schemas},
            why_it_matters="AI can't confirm entity for citation",
            recommended_fix="Add Organization or Website structured data.",
        )
    return None


@register(
    CheckSpec(
        check_id="R11",
        domain="AI search readiness (GEO)",
        title="Google-Agent / Google-Extended handling not set intentionally",
        description="Detects: Google-Agent / Google-Extended handling not set intentionally",  # noqa: E501
        why_it_matters="Uncontrolled AI-agent posture",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_R11(ctx: CrawlContext) -> Optional[Finding]:
    html = ctx.rendered_html or ctx.raw_html
    if not html:
        return None

    has_extended = False
    for meta in ctx.dom(bool(ctx.rendered_html)).css("meta[name]"):
        if (meta.attributes.get("name") or "").lower() == "google-extended":
            has_extended = True
            break

    if not has_extended:
        return Finding(
            check_id="R11",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={},
            why_it_matters="Uncontrolled AI-agent posture",
            recommended_fix="Explicitly allow or block Google-Extended.",
        )
    return None


@register(
    CheckSpec(
        check_id="R12",
        domain="AI search readiness (GEO)",
        title="No first-party structured facts (pricing, FAQ, policies) exposed",
        description="Detects: No first-party structured facts (pricing, FAQ, policies) exposed",  # noqa: E501
        why_it_matters="Misses ~44% first-party citation share",
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_R12(ctx: CrawlContext) -> Optional[Finding]:
    schemas = (
        [s.get("type", "").lower() for s in ctx.structured_data]
        if ctx.structured_data
        else []
    )
    facts = {"faqpage", "product", "price"}

    if not any(f in schemas for f in facts):
        return Finding(
            check_id="R12",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"found_schemas": schemas},
            why_it_matters="Misses ~44% first-party citation share",
            recommended_fix="Add FAQPage, Product, or pricing schema.",
        )
    return None


@register(
    CheckSpec(
        check_id="R13",
        domain="AI search readiness (GEO)",
        title="Hard-to-read content (low readability)",
        description="Detects: substantial content with a very low Flesch reading-ease score",  # noqa: E501
        why_it_matters="Dense, hard-to-parse prose lowers comprehension for readers and passage extraction for AI answer engines.",  # noqa: E501
        default_severity="Low",
        fix_tier="REVIEW",
        data_source="C",
        fix_template=None,
    )
)
def check_R13(ctx: CrawlContext) -> Optional[Finding]:
    if not ctx.url_row:
        return None
    words = getattr(ctx.url_row, "word_count", 0) or 0
    score = getattr(ctx.url_row, "readability", None)
    # Only judge readability on pages with enough prose to score meaningfully.
    if score is not None and words >= 300 and score < 30:
        return Finding(
            check_id="R13",
            severity="Low",
            tier="REVIEW",
            affected_urls=[ctx.url],
            wp_object_map={},
            evidence={"flesch_reading_ease": score, "word_count": words},
            why_it_matters="Dense prose lowers comprehension and AI passage extraction.",  # noqa: E501
            recommended_fix="Shorten sentences, simplify wording; target a Flesch score of 60+ (plain English).",  # noqa: E501
        )
    return None
