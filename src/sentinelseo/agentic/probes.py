"""The agentic probe catalogue.

Every probe answers one question about whether an AI agent can discover, read,
authenticate against, or transact with this origin. They all run against the
ROOT of the site — well-known paths, response headers and DNS — never per page,
so the cost is fixed (~25 requests) no matter how large the site is.

Design rules, learned the hard way from a crawl that hung forever on a CDN
script tag: every probe is hard-bounded, every network call is wrapped, and a
probe that cannot complete reports ERROR rather than raising or blocking.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from .models import Category, ProbeResult, ProbeStatus, Step

# Response bodies are recorded as evidence, so they must be truncated hard —
# a probe should never pull a 50 MB file into the report.
MAX_BODY = 4096
EXCERPT = 900
DEFAULT_TIMEOUT = 8.0

# Header allow-list for the audit trail. Recording every header would leak
# Set-Cookie and auth material into stored reports (invariant I5).
SAFE_RESPONSE_HEADERS = (
    "content-type", "content-length", "cf-ray", "server", "link",
    "www-authenticate", "x-markdown-tokens", "location", "cache-control",
    "x-robots-tag", "vary", "etag",
)

# The AI crawlers worth having an explicit robots.txt opinion about.
AI_BOTS = (
    "gptbot", "oai-searchbot", "chatgpt-user", "claudebot", "claude-web",
    "claude-searchbot", "claude-user", "anthropic-ai", "perplexitybot",
    "perplexity-user", "google-extended", "google-agent", "ccbot",
    "bytespider", "amazonbot", "applebot-extended", "meta-externalagent",
    "cohere-ai", "diffbot", "timpibot", "youbot",
)

CONTENT_SIGNALS = ("search", "ai-input", "ai-train")


class ProbeContext:
    """Shared state for one origin's probe run.

    robots.txt is fetched once and reused: three separate probes reason about it
    (existence/validity, AI bot rules, content signals) and re-fetching per probe
    would be wasteful and could see inconsistent CDN responses.
    """

    def __init__(
        self,
        origin: str,
        client: httpx.AsyncClient,
        timeout: float = DEFAULT_TIMEOUT,
        user_agent: str = "ScrawlyBot/1.0 (+agentic-readiness-audit)",
    ) -> None:
        p = urlparse(origin if "://" in origin else f"https://{origin}")
        self.scheme = p.scheme or "https"
        self.host = p.netloc or p.path
        self.origin = f"{self.scheme}://{self.host}"
        self.client = client
        self.timeout = timeout
        self.user_agent = user_agent
        self._robots: Optional[Tuple[Optional[httpx.Response], str]] = None
        self._home: Optional[httpx.Response] = None
        self._home_done = False
        self._lock = asyncio.Lock()
        self._home_lock = asyncio.Lock()

    def url(self, path: str) -> str:
        return f"{self.origin}/{path.lstrip('/')}"

    async def get(
        self, path: str, headers: Optional[Dict[str, str]] = None
    ) -> Optional[httpx.Response]:
        h = {"User-Agent": self.user_agent}
        if headers:
            h.update(headers)
        try:
            return await asyncio.wait_for(
                self.client.get(self.url(path), headers=h, follow_redirects=True),
                timeout=self.timeout,
            )
        except Exception:
            return None

    async def robots(self) -> Tuple[Optional[httpx.Response], str]:
        """Fetch /robots.txt once per run (concurrency-safe)."""
        async with self._lock:
            if self._robots is None:
                r = await self.get("/robots.txt")
                body = ""
                if r is not None and r.status_code == 200:
                    body = (r.text or "")[:MAX_BODY]
                self._robots = (r, body)
            return self._robots

    async def homepage(self) -> Optional[httpx.Response]:
        """Fetch `/` once per run and share it.

        Several probes reason about the homepage (Link headers, commerce
        signals, WWW-Authenticate). Fetching it per probe hammered slow origins
        with identical concurrent requests and made them time out — turning a
        real result into a spurious ERROR. One fetch, one retry, shared.
        """
        async with self._home_lock:
            if not self._home_done:
                r = await self.get("/")
                if r is None:
                    # A slow origin under concurrent probe load deserves one
                    # more, more patient attempt before we call it unreachable.
                    try:
                        r = await asyncio.wait_for(
                            self.client.get(
                                self.url("/"),
                                headers={"User-Agent": self.user_agent},
                                follow_redirects=True,
                            ),
                            timeout=self.timeout * 3,
                        )
                    except Exception:
                        r = None
                self._home = r
                self._home_done = True
            return self._home


# ---------------------------------------------------------------- helpers ----
def _safe_headers(r: Optional[httpx.Response]) -> Dict[str, str]:
    if r is None:
        return {}
    return {
        k: v for k, v in r.headers.items()
        if k.lower() in SAFE_RESPONSE_HEADERS
    }


def _step(
    action: str,
    r: Optional[httpx.Response],
    detail: str,
    ok: Optional[bool] = None,
    request_headers: Optional[Dict[str, str]] = None,
    body: bool = True,
) -> Step:
    return Step(
        action=action,
        detail=detail,
        status=r.status_code if r is not None else None,
        request_headers=request_headers or {},
        response_headers=_safe_headers(r),
        body_excerpt=((r.text or "")[:EXCERPT] if (r is not None and body) else ""),
        ok=ok,
    )


def _ctype(r: Optional[httpx.Response]) -> str:
    if r is None:
        return ""
    return (r.headers.get("content-type") or "").split(";")[0].strip().lower()


def _json_body(r: Optional[httpx.Response]) -> Optional[Any]:
    if r is None or r.status_code != 200:
        return None
    try:
        return json.loads((r.text or "")[:MAX_BODY * 8])
    except Exception:
        return None


async def _first_hit(
    ctx: ProbeContext,
    paths: List[str],
    steps: List[Step],
    accept: Optional[str] = None,
    want_json: bool = True,
) -> Tuple[Optional[httpx.Response], Optional[Any], Optional[str], bool]:
    """Try candidate well-known paths in order; return the first usable one.

    Emerging specs routinely move their path between drafts (MCP and Agent
    Skills both did), so probing a small candidate list rather than a single
    path is what keeps this accurate as the ecosystem churns.

    The trailing bool is `reached`: True if the origin answered at least one
    request with a real HTTP status. It matters because "the server said 404"
    and "we never got a reply" are different findings — reporting an unreachable
    origin as a confident FAIL would tell the user to build something they may
    already have.
    """
    req_h = {"Accept": accept} if accept else {}
    reached = False
    for path in paths:
        r = await ctx.get(path, headers=req_h)
        if r is None:
            steps.append(Step(action=f"GET {path}",
                              detail="Request failed (no response from origin)",
                              ok=False))
            continue
        reached = True
        if r.status_code == 200:
            data = _json_body(r) if want_json else None
            if not want_json or data is not None:
                steps.append(_step(f"GET {path}", r, "Found", True, req_h))
                return r, data, path, reached
            steps.append(_step(f"GET {path}", r, "200 but body is not valid JSON", False, req_h))
            continue
        steps.append(_step(f"GET {path}", r, f"Returned {r.status_code}", False, req_h, body=False))
    return None, None, None, reached


def _unreachable(
    pid: str, title: str, cat: Category, goal: str, steps: List[Step],
    specs: List[str], remediation: str,
) -> ProbeResult:
    """Origin never answered — report honestly rather than guessing a verdict."""
    return ProbeResult(
        probe_id=pid, title=title, category=cat, goal=goal,
        status=ProbeStatus.ERROR,
        conclusion="Could not reach the origin to check this",
        steps=steps, remediation=remediation, spec_urls=specs,
    )


def _ok(
    pid: str, title: str, cat: Category, goal: str, concl: str,
    steps: List[Step], specs: List[str], ev: Optional[Dict[str, Any]] = None,
) -> ProbeResult:
    return ProbeResult(
        probe_id=pid, title=title, category=cat, goal=goal,
        status=ProbeStatus.PASS, conclusion=concl, steps=steps,
        evidence=ev or {}, spec_urls=specs,
    )


def _bad(
    pid: str, title: str, cat: Category, goal: str, concl: str,
    steps: List[Step], specs: List[str], remediation: str,
    status: ProbeStatus = ProbeStatus.FAIL, ev: Optional[Dict[str, Any]] = None,
) -> ProbeResult:
    return ProbeResult(
        probe_id=pid, title=title, category=cat, goal=goal,
        status=status, conclusion=concl, steps=steps, evidence=ev or {},
        remediation=remediation, spec_urls=specs,
    )


# ------------------------------------------------------- discoverability ----
async def probe_robots_txt(ctx: ProbeContext) -> ProbeResult:
    pid, title = "AGT.ROBOTS", "robots.txt"
    goal = "Publish /robots.txt with clear crawl rules"
    specs = ["https://www.rfc-editor.org/rfc/rfc9309.html"]
    r, body = await ctx.robots()
    steps = [_step("GET /robots.txt", r, "Fetched robots.txt" if r else "Request failed",
                   bool(r and r.status_code == 200))]
    if r is None or r.status_code != 200:
        return _bad(pid, title, Category.DISCOVERABILITY, goal,
                    "No robots.txt found", steps, specs,
                    "Serve a /robots.txt at the origin root with at least a "
                    "`User-agent: *` group and a `Sitemap:` directive. Without it, "
                    "crawlers and agents have no declared crawl policy.")
    has_ua = bool(re.search(r"(?mi)^\s*user-agent\s*:", body))
    steps.append(Step(action="Validate robots.txt structure",
                      detail="Contains valid User-agent directive(s)" if has_ua
                             else "No User-agent directive found", ok=has_ua))
    if not has_ua:
        return _bad(pid, title, Category.DISCOVERABILITY, goal,
                    "robots.txt present but has no User-agent directive", steps, specs,
                    "Add at least one `User-agent:` group to robots.txt.")
    return _ok(pid, title, Category.DISCOVERABILITY, goal,
               "robots.txt exists with valid format", steps, specs,
               {"bytes": len(body)})


async def probe_sitemap(ctx: ProbeContext) -> ProbeResult:
    pid, title = "AGT.SITEMAP", "Sitemap"
    goal = "Publish a sitemap and reference it from robots.txt"
    specs = ["https://www.sitemaps.org/protocol.html"]
    _, body = await ctx.robots()
    declared = re.findall(r"(?mi)^\s*sitemap\s*:\s*(\S+)", body)
    steps = [Step(action="Extract Sitemap directives from robots.txt",
                  detail=f"Found {len(declared)} Sitemap directive(s) in robots.txt",
                  ok=bool(declared))]
    candidates = declared or [ctx.url("/sitemap.xml")]
    for sm in candidates[:3]:
        path = sm if sm.startswith("http") else ctx.url(sm)
        try:
            r = await asyncio.wait_for(
                ctx.client.get(path, headers={"User-Agent": ctx.user_agent},
                               follow_redirects=True),
                timeout=ctx.timeout)
        except Exception:
            r = None
        if r is None:
            steps.append(Step(action=f"GET {path}", detail="Request failed", ok=False))
            continue
        text = (r.text or "")[:MAX_BODY]
        valid = r.status_code == 200 and ("<urlset" in text or "<sitemapindex" in text)
        steps.append(_step(f"GET {path}", r,
                           f"Found valid xml sitemap at {path}" if valid
                           else f"Returned {r.status_code}, not a valid sitemap",
                           valid, body=False))
        if valid:
            kind = "index" if "<sitemapindex" in text else "urlset"
            return _ok(pid, title, Category.DISCOVERABILITY, goal,
                       "sitemap.xml exists with valid structure", steps, specs,
                       {"sitemap": path, "type": kind,
                        "declared_in_robots": bool(declared)})
    return _bad(pid, title, Category.DISCOVERABILITY, goal,
                "No valid sitemap found", steps, specs,
                "Publish an XML sitemap (urlset or sitemapindex) and reference it "
                "from robots.txt with a `Sitemap:` directive so agents can "
                "enumerate your content without crawling link-by-link.")


async def probe_link_headers(ctx: ProbeContext) -> ProbeResult:
    pid, title = "AGT.LINK_HEADERS", "Link headers"
    goal = "Include Link response headers for agent discovery (RFC 8288)"
    specs = ["https://www.rfc-editor.org/rfc/rfc8288.html",
             "https://www.rfc-editor.org/rfc/rfc9727.html"]
    r = await ctx.homepage()
    if r is None:
        return _bad(pid, title, Category.DISCOVERABILITY, goal,
                    "Could not fetch homepage", [Step("GET /", "Request failed", ok=False)],
                    specs, "", status=ProbeStatus.ERROR)
    link = r.headers.get("link", "")
    steps = [_step("GET /", r, "Link header present" if link
                   else "No Link header present in response", bool(link), body=False)]
    if not link:
        return _bad(pid, title, Category.DISCOVERABILITY, goal,
                    "No Link headers found on homepage", steps, specs,
                    "Add Link response headers to your homepage pointing agents at "
                    'useful resources, e.g. `Link: </.well-known/api-catalog>; '
                    'rel="api-catalog"` or `Link: </docs/api>; rel="service-doc"`.')
    rels = sorted(set(re.findall(r'rel\s*=\s*"?([\w .-]+)"?', link)))
    steps.append(Step(action="Parse Link relations",
                      detail=f"Relations advertised: {', '.join(rels) or 'none'}",
                      ok=bool(rels)))
    return _ok(pid, title, Category.DISCOVERABILITY, goal,
               f"Link header present ({len(rels)} relation(s))", steps, specs,
               {"rels": rels, "link": link[:400]})


async def probe_dns_aid(ctx: ProbeContext) -> ProbeResult:
    """DNS for AI Discovery — SVCB/HTTPS records at _<svc>._agents.<domain>."""
    pid, title = "AGT.DNS_AID", "DNS for AI Discovery (DNS-AID)"
    goal = "Publish DNS-AID records for DNS-based agent discovery"
    specs = ["https://www.rfc-editor.org/rfc/rfc9460.html"]
    host = ctx.host.split(":")[0]
    steps: List[Step] = []
    found: List[str] = []
    # SVCB=64, HTTPS=65, TXT=16 at the spec's well-known entrypoints.
    entrypoints = ["_index._agents", "_a2a._agents", "_mcp._agents"]
    queries = [(e, t, n) for e in entrypoints for t, n in ((64, "SVCB"), (65, "HTTPS"))]
    queries.append(("_index._agents", 16, "TXT"))
    for prefix, rtype, rname in queries:
        name = f"{prefix}.{host}"
        try:
            r = await asyncio.wait_for(
                ctx.client.get(
                    "https://cloudflare-dns.com/dns-query",
                    params={"name": name, "type": str(rtype)},
                    headers={"accept": "application/dns-json"},
                ), timeout=ctx.timeout)
            data = r.json() if r.status_code == 200 else {}
            answers = data.get("Answer") or []
            hit = bool(answers)
            if hit:
                found.append(f"{rname} {name}")
            steps.append(Step(
                action=f"DoH {rname} {name}", status=r.status_code,
                request_headers={"accept": "application/dns-json"},
                detail=f"{len(answers)} answer(s)" if hit
                       else f"No {rname} answers (NXDOMAIN)",
                body_excerpt=(r.text or "")[:300], ok=hit))
        except Exception:
            steps.append(Step(action=f"DoH {rname} {name}",
                              detail="DNS query failed", ok=False))
    steps.append(Step(action="Parse DNS-AID SVCB/HTTPS records",
                      detail=f"Found {len(found)} record(s)" if found
                             else "No DNS-AID SVCB or HTTPS records found at "
                                  "well-known entrypoints",
                      ok=bool(found)))
    if found:
        return _ok(pid, title, Category.DISCOVERABILITY, goal,
                   "DNS-AID records published", steps, specs, {"records": found})
    return _bad(pid, title, Category.DISCOVERABILITY, goal,
                "DNS-AID well-known entrypoint records not found", steps, specs,
                "Publish DNS-AID records under your domain (e.g. "
                "`_index._agents.example.com`, `_a2a._agents.example.com`) as "
                "ServiceMode SVCB/HTTPS records with `alpn` and endpoint params, "
                "and sign the zone with DNSSEC.")


# --------------------------------------------------------------- content ----
async def probe_markdown(ctx: ProbeContext) -> ProbeResult:
    pid, title = "AGT.MARKDOWN", "Markdown negotiation"
    goal = "Return HTML responses as markdown when agents request it"
    specs = ["https://developers.cloudflare.com/ai-crawl-control/"]
    req_h = {"Accept": "text/markdown"}
    r = await ctx.get("/", headers=req_h)
    if r is None:
        return _bad(pid, title, Category.CONTENT, goal, "Could not fetch homepage",
                    [Step("GET / (Accept: text/markdown)", "Request failed", ok=False)],
                    specs, "", status=ProbeStatus.ERROR)
    ct = _ctype(r)
    is_md = "markdown" in ct
    steps = [_step("GET homepage (Accept: text/markdown)", r,
                   f"Response content-type is {ct}, "
                   + ("markdown served" if is_md else "not text/markdown — "
                      "site does not support markdown content negotiation"),
                   is_md, req_h, body=False)]
    if is_md:
        return _ok(pid, title, Category.CONTENT, goal,
                   "Site serves markdown to agents", steps, specs,
                   {"tokens": r.headers.get("x-markdown-tokens", "")})
    return _bad(pid, title, Category.CONTENT, goal,
                "Site does not support Markdown for Agents", steps, specs,
                "Content-negotiate on `Accept: text/markdown`: return a markdown "
                "rendering of the page (`Content-Type: text/markdown`) while HTML "
                "stays the default for browsers. Markdown costs an LLM far fewer "
                "tokens than HTML and removes parsing ambiguity.")


async def probe_llms_txt(ctx: ProbeContext) -> ProbeResult:
    """Scrawly differentiator — isitagentready does not check llms.txt."""
    pid, title = "AGT.LLMS_TXT", "llms.txt"
    goal = "Publish /llms.txt as a curated map of your content for LLMs"
    specs = ["https://llmstxt.org/"]
    r = await ctx.get("/llms.txt")
    if r is None or r.status_code != 200:
        return _bad(pid, title, Category.CONTENT, goal, "No llms.txt found",
                    [_step("GET /llms.txt", r, "Not found", False, body=False)], specs,
                    "Add `/llms.txt`: an H1 with the site name, a blockquote summary, "
                    "then curated `## Section` lists of `[title](url): description` "
                    "links to your highest-value pages. It gives an LLM a hand-written "
                    "index instead of making it infer structure from your nav.")
    body = (r.text or "")[:MAX_BODY]
    has_h1 = bool(re.search(r"(?m)^#\s+\S", body))
    links = len(re.findall(r"\[[^\]]+\]\([^)]+\)", body))
    steps = [_step("GET /llms.txt", r, "Found llms.txt", True, body=False),
             Step(action="Validate llms.txt structure",
                  detail=f"H1: {'yes' if has_h1 else 'no'}; {links} markdown link(s)",
                  ok=has_h1 and links > 0)]
    if not has_h1 or links == 0:
        return _bad(pid, title, Category.CONTENT, goal,
                    "llms.txt present but malformed (needs an H1 and curated links)",
                    steps, specs,
                    "Give llms.txt a top-level `# Heading` and at least a few "
                    "`[title](url): description` links grouped under `##` sections.")
    return _ok(pid, title, Category.CONTENT, goal,
               f"llms.txt present and structured ({links} links)", steps, specs,
               {"links": links})


# --------------------------------------------------------- bot controls ----
async def probe_ai_bot_rules(ctx: ProbeContext) -> ProbeResult:
    pid, title = "AGT.AI_BOTS", "AI bot rules in robots.txt"
    goal = "Declare explicit User-agent rules for AI crawlers"
    specs = ["https://www.rfc-editor.org/rfc/rfc9309.html"]
    r, body = await ctx.robots()
    steps = [_step("GET /robots.txt", r, "Fetched robots.txt", bool(body), body=False)]
    if not body:
        return _bad(pid, title, Category.BOT_CONTROL, goal,
                    "No robots.txt to declare AI bot rules in", steps, specs,
                    "Create robots.txt, then add explicit `User-agent:` groups for "
                    "AI crawlers (GPTBot, ClaudeBot, PerplexityBot, Google-Extended).")
    agents = {m.lower() for m in re.findall(r"(?mi)^\s*user-agent\s*:\s*(\S+)", body)}
    named = sorted(a for a in agents if a in AI_BOTS)
    steps.append(Step(action="Scan for AI bot User-agent directives",
                      detail=f"Found rules for AI bots: {', '.join(named)}" if named
                             else "No AI-bot-specific User-agent directives found",
                      ok=bool(named)))
    if named:
        return _ok(pid, title, Category.BOT_CONTROL, goal,
                   f"Found rules for {len(named)} AI bot(s)", steps, specs,
                   {"bots": named})
    return _bad(pid, title, Category.BOT_CONTROL, goal,
                "No AI bot rules found in robots.txt", steps, specs,
                "Add explicit groups so AI access is intentional rather than "
                "accidental, e.g. `User-agent: GPTBot` / `Allow: /`. Decide "
                "separately for training bots (GPTBot, ClaudeBot, CCBot, "
                "Google-Extended) vs search/answer bots (OAI-SearchBot, "
                "PerplexityBot) — blocking the latter removes you from AI answers.")


async def probe_content_signals(ctx: ProbeContext) -> ProbeResult:
    pid, title = "AGT.CONTENT_SIGNALS", "Content Signals in robots.txt"
    goal = "Declare AI content-usage preferences with Content Signals"
    specs = ["https://contentsignals.org/"]
    r, body = await ctx.robots()
    steps = [_step("GET /robots.txt", r, "Fetched robots.txt", bool(body), body=False)]
    sigs = re.findall(r"(?mi)^\s*content-signal\s*:\s*(.+)$", body)
    parsed: Dict[str, str] = {}
    for line in sigs:
        for part in line.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                if k.strip().lower() in CONTENT_SIGNALS:
                    parsed[k.strip().lower()] = v.strip().lower()
    steps.append(Step(action="Parse Content-Signal directives",
                      detail=(f"Signals: {parsed}" if parsed
                              else "No Content-Signal directives found in robots.txt"),
                      ok=bool(parsed)))
    if parsed:
        return _ok(pid, title, Category.BOT_CONTROL, goal,
                   f"Content Signals declared ({len(parsed)}/3)", steps, specs,
                   {"signals": parsed})
    return _bad(pid, title, Category.BOT_CONTROL, goal,
                "No Content Signals found in robots.txt", steps, specs,
                "Add a `Content-Signal:` line to your robots.txt declaring "
                "preferences for `search`, `ai-input` and `ai-train`, e.g. "
                "`Content-Signal: search=yes, ai-train=no, ai-input=yes`. It states "
                "your reuse terms in machine-readable form (a preference signal, "
                "not an enforcement mechanism — pair it with bot management).")


async def probe_web_bot_auth(ctx: ProbeContext) -> ProbeResult:
    pid, title = "AGT.WEB_BOT_AUTH", "Web Bot Auth request signing"
    goal = "Let your site identify itself as a bot with Web Bot Auth"
    specs = ["https://datatracker.ietf.org/wg/httpbis/documents/"]
    path = "/.well-known/http-message-signatures-directory"
    r = await ctx.get(path)
    data = _json_body(r)
    keys = data.get("keys") if isinstance(data, dict) else None
    ok = bool(keys)
    steps = [_step(f"GET {path}", r,
                   "JWKS directory found" if ok
                   else f"Server returned {r.status_code if r else 'error'} — "
                        "Web Bot Auth directory not found",
                   ok, body=False)]
    if ok:
        return _ok(pid, title, Category.BOT_CONTROL, goal,
                   "Web Bot Auth directory published", steps, specs,
                   {"keys": len(keys or [])})
    # Informational: only meaningful if this site itself sends agent traffic.
    return _bad(pid, title, Category.BOT_CONTROL, goal,
                "Web Bot Auth directory not found (informational)", steps, specs,
                "If your site makes outbound bot/agent requests, publish a JWKS at "
                "`/.well-known/http-message-signatures-directory` so receiving sites "
                "can cryptographically verify your signed requests.",
                status=ProbeStatus.INFO)


# ------------------------------------------------------ api / auth / mcp ----
async def probe_api_catalog(ctx: ProbeContext) -> ProbeResult:
    pid, title = "AGT.API_CATALOG", "API Catalog"
    goal = "Publish an API catalog for automated API discovery (RFC 9727)"
    specs = ["https://www.rfc-editor.org/rfc/rfc9727.html",
             "https://www.rfc-editor.org/rfc/rfc9264.html"]
    steps: List[Step] = []
    r, data, _, reached = await _first_hit(ctx, ["/.well-known/api-catalog"], steps,
                                  accept="application/linkset+json, application/json")
    linkset = (data or {}).get("linkset") if isinstance(data, dict) else None
    if linkset:
        return _ok(pid, title, Category.API_AUTH_MCP, goal,
                   f"API Catalog published ({len(linkset)} entries)", steps, specs,
                   {"entries": len(linkset)})
    if not reached:
        return _unreachable(pid, title, Category.API_AUTH_MCP, goal, steps, specs,
                            "Re-run once the origin is reachable.")
    return _bad(pid, title, Category.API_AUTH_MCP, goal,
                "API Catalog not found", steps, specs,
                "Serve `/.well-known/api-catalog` as `application/linkset+json` with "
                'a `linkset` array. Each entry needs an `anchor` URL plus relations '
                "for `service-desc` (OpenAPI spec), `service-doc` (docs) and "
                "`status` (health). See RFC 9727 Appendix A.")


async def probe_oauth_discovery(ctx: ProbeContext) -> ProbeResult:
    pid, title = "AGT.OAUTH_DISCOVERY", "OAuth / OIDC discovery"
    goal = "Publish OAuth/OIDC discovery metadata so agents can authenticate"
    specs = ["https://openid.net/specs/openid-connect-discovery-1_0.html",
             "https://www.rfc-editor.org/rfc/rfc8414.html"]
    steps: List[Step] = []
    _, data, path, reached = await _first_hit(ctx, [
        "/.well-known/openid-configuration",
        "/.well-known/oauth-authorization-server",
    ], steps)
    required = ("issuer", "authorization_endpoint", "token_endpoint")
    if isinstance(data, dict) and all(k in data for k in required):
        return _ok(pid, title, Category.API_AUTH_MCP, goal,
                   "OAuth/OIDC discovery metadata published", steps, specs,
                   {"path": path, "issuer": str(data.get("issuer", ""))[:200]})
    if not reached:
        return _unreachable(pid, title, Category.API_AUTH_MCP, goal, steps, specs,
                            "Re-run once the origin is reachable.")
    return _bad(pid, title, Category.API_AUTH_MCP, goal,
                "No OAuth/OIDC discovery metadata found", steps, specs,
                "If you expose protected APIs, publish "
                "`/.well-known/openid-configuration` (OIDC) or "
                "`/.well-known/oauth-authorization-server` (OAuth 2.0) with "
                "`issuer`, `authorization_endpoint`, `token_endpoint`, `jwks_uri` "
                "and `grant_types_supported`.")


async def probe_oauth_protected_resource(ctx: ProbeContext) -> ProbeResult:
    pid, title = "AGT.OAUTH_PR", "OAuth Protected Resource"
    goal = "Publish OAuth Protected Resource Metadata (RFC 9728)"
    specs = ["https://www.rfc-editor.org/rfc/rfc9728.html"]
    steps: List[Step] = []
    _, data, _, reached = await _first_hit(ctx, ["/.well-known/oauth-protected-resource"], steps)
    servers = data.get("authorization_servers") if isinstance(data, dict) else None
    if servers:
        return _ok(pid, title, Category.API_AUTH_MCP, goal,
                   "OAuth Protected Resource Metadata published", steps, specs,
                   {"authorization_servers": list(servers)[:5]})
    home = await ctx.homepage()
    wa = home.headers.get("www-authenticate", "") if home else ""
    steps.append(_step("GET /", home,
                       f"WWW-Authenticate: {wa}" if wa
                       else "Homepage returned no WWW-Authenticate header",
                       bool(wa), body=False))
    return _bad(pid, title, Category.API_AUTH_MCP, goal,
                "No OAuth Protected Resource Metadata found", steps, specs,
                "Publish `/.well-known/oauth-protected-resource` with your `resource` "
                "identifier, `authorization_servers` (issuers that can mint tokens "
                "for it) and `scopes_supported`, so agents can discover how to get "
                "an access token for your protected APIs.")


async def probe_auth_md(ctx: ProbeContext) -> ProbeResult:
    pid, title = "AGT.AUTH_MD", "Auth.md agent registration"
    goal = "Publish Auth.md metadata for agent registration"
    specs = ["https://github.com/workos/auth.md"]
    req_h = {"Accept": "text/markdown, text/plain, */*"}
    r = await ctx.get("/auth.md", headers=req_h)
    ok = bool(r and r.status_code == 200 and "html" not in _ctype(r))
    steps = [_step("GET /auth.md", r,
                   "auth.md found" if ok
                   else f"Server returned {r.status_code if r else 'error'} — "
                        "auth.md not found", ok, req_h, body=False)]
    if ok:
        return _ok(pid, title, Category.API_AUTH_MCP, goal, "auth.md published",
                   steps, specs, {})
    return _bad(pid, title, Category.API_AUTH_MCP, goal, "auth.md not found",
                steps, specs,
                "Serve `/auth.md` at the site root describing how agents register "
                "and authenticate, and pair it with "
                "`/.well-known/oauth-protected-resource` plus an `agent_auth` block "
                "(register_uri, identity/credential types) in your authorization "
                "server metadata.")


async def probe_mcp_server_card(ctx: ProbeContext) -> ProbeResult:
    pid, title = "AGT.MCP_CARD", "MCP Server Card"
    goal = "Publish an MCP Server Card so agents can discover your MCP server"
    specs = ["https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2127"]
    steps: List[Step] = []
    _, data, path, reached = await _first_hit(ctx, [
        "/.well-known/mcp/server-card.json",
        "/.well-known/mcp.json",
        "/.well-known/mcp/server-cards.json",
    ], steps)
    if isinstance(data, dict) and (data.get("serverInfo") or data.get("servers")):
        return _ok(pid, title, Category.API_AUTH_MCP, goal,
                   "MCP Server Card published", steps, specs, {"path": path})
    if not reached:
        return _unreachable(pid, title, Category.API_AUTH_MCP, goal, steps, specs,
                            "Re-run once the origin is reachable.")
    return _bad(pid, title, Category.API_AUTH_MCP, goal,
                "MCP Server Card not found at any candidate path", steps, specs,
                "Serve an MCP Server Card at `/.well-known/mcp/server-card.json` "
                "with `serverInfo` (name, version), a transport `endpoint` and your "
                "`capabilities`, so agents can find and connect to your MCP server "
                "without out-of-band configuration.")


async def probe_a2a_agent_card(ctx: ProbeContext) -> ProbeResult:
    pid, title = "AGT.A2A_CARD", "A2A Agent Card"
    goal = "Publish an A2A Agent Card describing your agent's capabilities"
    specs = ["https://a2a-protocol.org/latest/topics/agent-discovery/"]
    steps: List[Step] = []
    _, data, path, reached = await _first_hit(ctx, [
        "/.well-known/agent-card.json",   # current (RFC 8615)
        "/.well-known/agent.json",        # legacy draft path
    ], steps)
    if isinstance(data, dict) and (data.get("name") or data.get("skills")):
        return _ok(pid, title, Category.API_AUTH_MCP, goal,
                   "A2A Agent Card published", steps, specs,
                   {"path": path, "skills": len(data.get("skills") or [])})
    if not reached:
        return _unreachable(pid, title, Category.API_AUTH_MCP, goal, steps, specs,
                            "Re-run once the origin is reachable.")
    return _bad(pid, title, Category.API_AUTH_MCP, goal,
                "A2A Agent Card not found", steps, specs,
                "If you expose an agent, serve `/.well-known/agent-card.json` with "
                "`name`, `description`, `url`, `version`, `capabilities` and a "
                "`skills` array, so other agents can discover what yours can do.")


async def probe_agent_skills(ctx: ProbeContext) -> ProbeResult:
    pid, title = "AGT.AGENT_SKILLS", "Agent Skills index"
    goal = "Publish an agent skills discovery index"
    specs = ["https://github.com/cloudflare/agent-skills-discovery-rfc"]
    steps: List[Step] = []
    _, data, path, reached = await _first_hit(ctx, [
        "/.well-known/agent-skills/index.json",   # RFC v0.2.0
        "/.well-known/skills/index.json",         # legacy
    ], steps)
    skills = (data or {}).get("skills") if isinstance(data, dict) else None
    if skills:
        return _ok(pid, title, Category.API_AUTH_MCP, goal,
                   f"Agent Skills index published ({len(skills)} skills)",
                   steps, specs, {"path": path, "skills": len(skills)})
    if not reached:
        return _unreachable(pid, title, Category.API_AUTH_MCP, goal, steps, specs,
                            "Re-run once the origin is reachable.")
    return _bad(pid, title, Category.API_AUTH_MCP, goal,
                "Agent Skills index not found", steps, specs,
                "Publish `/.well-known/agent-skills/index.json` with a `$schema` "
                "field and a `skills` array where each entry has `name`, `type`, "
                "`description`, `url` and a `sha256` digest, so agents can discover "
                "and verify the skills your site offers.")


async def probe_ai_plugin(ctx: ProbeContext) -> ProbeResult:
    """Legacy ChatGPT plugin manifest — still a real discovery signal."""
    pid, title = "AGT.AI_PLUGIN", "AI plugin manifest"
    goal = "Expose a machine-readable plugin/tool manifest"
    specs = ["https://www.rfc-editor.org/rfc/rfc8615.html"]
    steps: List[Step] = []
    _, data, path, reached = await _first_hit(ctx, ["/.well-known/ai-plugin.json"], steps)
    if isinstance(data, dict) and data.get("api"):
        return _ok(pid, title, Category.API_AUTH_MCP, goal,
                   "AI plugin manifest published", steps, specs, {"path": path})
    return _bad(pid, title, Category.API_AUTH_MCP, goal,
                "No AI plugin manifest (superseded by MCP — informational)",
                steps, specs,
                "Optional/legacy. Prefer an MCP Server Card; only add "
                "`/.well-known/ai-plugin.json` for compatibility with older "
                "plugin-style integrations.",
                status=ProbeStatus.INFO)


# -------------------------------------------------------------- commerce ----
async def _commerce_probe(
    ctx: ProbeContext, pid: str, title: str, goal: str, specs: List[str],
    paths: List[str], validate: Callable[[Any], bool], remediation: str,
    is_commerce: bool,
) -> ProbeResult:
    """Commerce probes are INFO on non-commerce sites so they never distort the
    score — a blog is not deficient for lacking an agent payment rail."""
    steps: List[Step] = []
    _, data, path, reached = await _first_hit(ctx, paths, steps)
    if data is not None and validate(data):
        return _ok(pid, title, Category.COMMERCE, goal, f"{title} detected",
                   steps, specs, {"path": path})
    status = ProbeStatus.FAIL if is_commerce else ProbeStatus.NOT_APPLICABLE
    suffix = "" if is_commerce else " (no e-commerce signals detected)"
    return _bad(pid, title, Category.COMMERCE, goal,
                f"{title} not detected{suffix}", steps, specs, remediation,
                status=status)


async def probe_x402(ctx: ProbeContext, is_commerce: bool) -> ProbeResult:
    pid, title = "AGT.X402", "x402 Protocol"
    goal = "Support x402 for agent-native HTTP payments"
    specs = ["https://x402.org/", "https://github.com/coinbase/x402"]
    steps: List[Step] = []
    hit = False
    for p in ("/api/v1", "/api", "/"):
        r = await ctx.get(p)
        is402 = bool(r and r.status_code == 402)
        steps.append(_step(f"GET {p}", r,
                           "Returned 402 Payment Required" if is402
                           else f"{p} returned {r.status_code if r else 'error'} "
                                "(not 402)", is402, body=False))
        if is402:
            hit = True
            break
    if hit:
        return _ok(pid, title, Category.COMMERCE, goal,
                   "x402 payment protocol detected", steps, specs, {})
    status = ProbeStatus.FAIL if is_commerce else ProbeStatus.NOT_APPLICABLE
    return _bad(pid, title, Category.COMMERCE, goal,
                "x402 payment protocol not detected"
                + ("" if is_commerce else " (no e-commerce signals detected)"),
                steps, specs,
                "Add x402 middleware to your paid API routes so agents can pay "
                "over HTTP: protected routes return `402` with machine-readable "
                "payment requirements the agent can satisfy automatically.",
                status=status)


async def probe_mpp(ctx: ProbeContext, is_commerce: bool) -> ProbeResult:
    return await _commerce_probe(
        ctx, "AGT.MPP", "MPP (Machine Payment Protocol)",
        "Support MPP for agent-native HTTP payments",
        ["https://mpp.dev/"], ["/openapi.json"],
        lambda d: isinstance(d, dict) and "x-payment-info" in json.dumps(d)[:20000],
        "Publish `/openapi.json` with `x-payment-info` extensions on payable "
        "operations, declaring `intent`, `method`, `amount` and `currency`.",
        is_commerce)


async def probe_ucp(ctx: ProbeContext, is_commerce: bool) -> ProbeResult:
    return await _commerce_probe(
        ctx, "AGT.UCP", "Universal Commerce Protocol",
        "Enable agent commerce via UCP",
        ["https://ucp.dev/"], ["/.well-known/ucp"],
        lambda d: isinstance(d, dict) and bool(d.get("services") or d.get("version")),
        "Serve `/.well-known/ucp` with protocol version, services, capabilities "
        "and endpoints.",
        is_commerce)


async def probe_acp(ctx: ProbeContext, is_commerce: bool) -> ProbeResult:
    return await _commerce_probe(
        ctx, "AGT.ACP", "ACP (Agentic Commerce Protocol)",
        "Publish ACP discovery metadata",
        ["https://agenticcommerce.dev/"], ["/.well-known/acp.json"],
        lambda d: isinstance(d, dict)
        and str((d.get("protocol") or {}).get("name", "")).lower() == "acp",
        "Serve `/.well-known/acp.json` at the origin root with `protocol.name` "
        '"acp", `protocol.version`, `api_base_url`, supported transports and '
        "`capabilities.services`.",
        is_commerce)


# Probes that need no commerce hint, in run order.
SIMPLE_PROBES: Tuple[Callable[[ProbeContext], Awaitable[ProbeResult]], ...] = (
    probe_robots_txt, probe_sitemap, probe_link_headers, probe_dns_aid,
    probe_markdown, probe_llms_txt,
    probe_ai_bot_rules, probe_content_signals, probe_web_bot_auth,
    probe_api_catalog, probe_oauth_discovery, probe_oauth_protected_resource,
    probe_auth_md, probe_mcp_server_card, probe_a2a_agent_card,
    probe_agent_skills, probe_ai_plugin,
)

COMMERCE_PROBES: Tuple[
    Callable[[ProbeContext, bool], Awaitable[ProbeResult]], ...
] = (probe_x402, probe_mpp, probe_ucp, probe_acp)
