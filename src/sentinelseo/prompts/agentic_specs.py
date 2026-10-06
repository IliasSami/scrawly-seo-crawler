"""Fix specs for every agentic probe.

One entry per probe id. These carry the *exact* artefact an agent must produce —
a literal robots.txt directive, a JSON document with the required keys — because
"add an API catalog" is not actionable but a concrete document plus acceptance
criteria is.
"""
from __future__ import annotations

from typing import Dict

from .engine import PromptSpec

AGENTIC_SPECS: Dict[str, PromptSpec] = {
    "AGT.ROBOTS": PromptSpec(
        check_id="AGT.ROBOTS",
        title="Publish a valid robots.txt",
        problem="The site does not serve a usable /robots.txt, so crawlers and AI "
                "agents have no declared crawl policy and must guess.",
        artefact="robots",
        body="Serve `/robots.txt` as `text/plain` containing at least a "
             "`User-agent: *` group with explicit `Allow`/`Disallow` rules, and a "
             "`Sitemap:` line with the absolute sitemap URL.",
        acceptance=[
            "GET /robots.txt returns 200 with Content-Type: text/plain",
            "It contains at least one `User-agent:` directive",
            "It contains a `Sitemap:` directive with an absolute https URL",
        ],
        verify=["curl -sS -D- https://<domain>/robots.txt | head -20"],
    ),
    "AGT.SITEMAP": PromptSpec(
        check_id="AGT.SITEMAP",
        title="Publish an XML sitemap and reference it from robots.txt",
        problem="No valid XML sitemap was found, so agents and crawlers must "
                "discover every URL by following links, which misses orphaned "
                "pages entirely.",
        artefact="sitemap",
        body="Generate a valid `<urlset>` (or `<sitemapindex>` for large sites) "
             "listing canonical, indexable URLs only — no redirects, no 404s, no "
             "noindex pages. Add `Sitemap: https://<domain>/sitemap.xml` to robots.txt.",
        acceptance=[
            "GET /sitemap.xml returns 200 with an XML content type",
            "The document root element is <urlset> or <sitemapindex>",
            "robots.txt contains a matching `Sitemap:` directive",
            "Every <loc> is canonical, indexable and returns 200",
        ],
        verify=["curl -sS https://<domain>/sitemap.xml | head -20",
                "curl -sS https://<domain>/robots.txt | grep -i sitemap"],
    ),
    "AGT.LINK_HEADERS": PromptSpec(
        check_id="AGT.LINK_HEADERS",
        title="Advertise agent resources with Link response headers (RFC 8288)",
        problem="The homepage returns no `Link` response header, so an agent has "
                "no header-level pointer to your API catalog, docs or service "
                "description and must scrape HTML to find them.",
        artefact="headers",
        body="Add a `Link` response header on the homepage (ideally all HTML "
             "responses) pointing at the resources you publish, e.g.:\n\n"
             "```\nLink: </.well-known/api-catalog>; rel=\"api-catalog\", "
             "</docs/api>; rel=\"service-doc\"\n```\n\n"
             "Only advertise relations for resources that actually exist.",
        acceptance=[
            "GET / returns a `Link` header",
            "Each advertised URL resolves to 200",
            "Relation types are registered IANA link relations",
        ],
        verify=["curl -sSI https://<domain>/ | grep -i '^link:'"],
    ),
    "AGT.DNS_AID": PromptSpec(
        check_id="AGT.DNS_AID",
        title="Publish DNS-AID records for DNS-based agent discovery",
        problem="No DNS for AI Discovery records exist at the well-known "
                "entrypoints, so agents cannot discover your agent endpoints "
                "without already knowing your URLs.",
        artefact="headers",
        body="Publish ServiceMode SVCB/HTTPS records (RFC 9460) under "
             "`_index._agents.<domain>`, and per-protocol entrypoints such as "
             "`_a2a._agents.<domain>` / `_mcp._agents.<domain>`, with `alpn` and "
             "endpoint parameters. Sign the zone with DNSSEC so validating "
             "resolvers return authenticated data.",
        acceptance=[
            "SVCB or HTTPS records resolve at _index._agents.<domain>",
            "Records point at endpoints that are actually reachable",
            "The zone is DNSSEC-signed",
        ],
        verify=["dig +short SVCB _index._agents.<domain>",
                "dig +short HTTPS _mcp._agents.<domain>"],
        constraints=["This changes DNS. Make the change in the DNS provider's "
                     "zone editor and confirm each record before/after."],
    ),
    "AGT.MARKDOWN": PromptSpec(
        check_id="AGT.MARKDOWN",
        title="Serve markdown to agents via content negotiation",
        problem="Requests sending `Accept: text/markdown` still receive HTML. "
                "Agents must then strip markup, which wastes tokens and "
                "introduces parsing errors.",
        artefact="headers",
        body="Content-negotiate on the `Accept` request header: when it prefers "
             "`text/markdown`, return a markdown rendering of the same page with "
             "`Content-Type: text/markdown; charset=utf-8`. HTML stays the default "
             "for browsers. Add `Vary: Accept` so caches do not mix the two.",
        acceptance=[
            "GET / with `Accept: text/markdown` returns Content-Type: text/markdown",
            "GET / with a normal browser Accept header still returns HTML",
            "Responses include `Vary: Accept`",
            "The markdown reflects the same main content as the HTML page",
        ],
        verify=["curl -sSI -H 'Accept: text/markdown' https://<domain>/ | grep -i content-type",
                "curl -sSI https://<domain>/ | grep -i -E 'content-type|vary'"],
    ),
    "AGT.LLMS_TXT": PromptSpec(
        check_id="AGT.LLMS_TXT",
        title="Publish a curated /llms.txt",
        problem="There is no `/llms.txt`, so an LLM has to infer which of your "
                "pages matter by crawling navigation instead of reading a "
                "hand-curated index.",
        artefact="static",
        body="Create `/llms.txt` (markdown, served as text/plain or text/markdown):\n\n"
             "```markdown\n# <Site name>\n\n> One-sentence description of what "
             "this site is and who it is for.\n\n## Docs\n- [Page title]"
             "(https://<domain>/path): what this page answers\n\n## Optional\n"
             "- [Secondary page](https://<domain>/other): lower-priority context\n```\n\n"
             "Curate it — link your highest-value pages, not every URL.",
        acceptance=[
            "GET /llms.txt returns 200",
            "It starts with a single H1 and a blockquote summary",
            "Links are absolute and grouped under `##` sections with descriptions",
            "It is curated, not a dump of every URL on the site",
        ],
        verify=["curl -sS https://<domain>/llms.txt | head -30"],
    ),
    "AGT.AI_BOTS": PromptSpec(
        check_id="AGT.AI_BOTS",
        title="Declare explicit robots.txt rules for AI crawlers",
        problem="robots.txt has no AI-crawler-specific groups, so AI access is "
                "accidental rather than intentional — you have not decided "
                "whether these bots may use your content.",
        artefact="robots",
        body="Add explicit groups, deciding separately for the two classes:\n\n"
             "- **Training crawlers** (GPTBot, ClaudeBot, CCBot, Google-Extended) "
             "— blocking these keeps your content out of model training.\n"
             "- **Search/answer crawlers** (OAI-SearchBot, Claude-SearchBot, "
             "PerplexityBot) — blocking these removes you from AI answers and "
             "citations, which usually costs you traffic.\n\n"
             "Example:\n```\nUser-agent: GPTBot\nDisallow: /\n\n"
             "User-agent: OAI-SearchBot\nAllow: /\n```",
        acceptance=[
            "robots.txt contains explicit User-agent groups for AI crawlers",
            "Training vs search/answer bots are handled as deliberate, separate decisions",
            "No AI bot is blocked by accident via an over-broad wildcard rule",
        ],
        verify=["curl -sS https://<domain>/robots.txt"],
    ),
    "AGT.CONTENT_SIGNALS": PromptSpec(
        check_id="AGT.CONTENT_SIGNALS",
        title="Declare AI usage preferences with Content Signals",
        problem="robots.txt carries no `Content-Signal` directives, so your reuse "
                "terms for search, AI answers and AI training are not stated in "
                "machine-readable form.",
        artefact="robots",
        body="Add a `Content-Signal` line inside the relevant User-agent group, "
             "using comma-separated `yes`/`no` values for `search`, `ai-input` "
             "and `ai-train`:\n\n```\nUser-agent: *\n"
             "Content-Signal: search=yes, ai-input=yes, ai-train=no\nAllow: /\n```\n\n"
             "Omit a key entirely to express no preference.",
        acceptance=[
            "robots.txt contains a `Content-Signal:` directive",
            "Only the keys search / ai-input / ai-train are used, with yes|no values",
            "The stated preferences match the site owner's actual policy",
        ],
        verify=["curl -sS https://<domain>/robots.txt | grep -i content-signal"],
        constraints=["Content Signals express preferences and are not an "
                     "enforcement mechanism — do not present them as blocking."],
    ),
    "AGT.WEB_BOT_AUTH": PromptSpec(
        check_id="AGT.WEB_BOT_AUTH",
        title="Publish a Web Bot Auth key directory",
        problem="No JWKS is published at "
                "`/.well-known/http-message-signatures-directory`, so when this "
                "site makes outbound agent requests, receivers cannot verify them.",
        artefact="well_known",
        body="Publish a JWKS document at "
             "`/.well-known/http-message-signatures-directory` containing the "
             "public keys used to sign your outbound bot requests, served as "
             "`application/json`.",
        acceptance=[
            "GET /.well-known/http-message-signatures-directory returns 200 JSON",
            "The document contains a `keys` array of public JWKs",
            "Only PUBLIC keys are published",
        ],
        verify=["curl -sS https://<domain>/.well-known/http-message-signatures-directory"],
        constraints=["Publish public keys only. Never place a private key in a "
                     "web-served file or in version control."],
    ),
    "AGT.API_CATALOG": PromptSpec(
        check_id="AGT.API_CATALOG",
        title="Publish an API catalog (RFC 9727)",
        problem="`/.well-known/api-catalog` is absent, so agents cannot "
                "programmatically discover your APIs, their specs or their docs.",
        artefact="well_known",
        body="Serve `/.well-known/api-catalog` as `application/linkset+json`:\n\n"
             "```json\n{\n  \"linkset\": [\n    {\n"
             "      \"anchor\": \"https://<domain>/api/v1\",\n"
             "      \"service-desc\": [{\"href\": \"https://<domain>/openapi.json\", "
             "\"type\": \"application/openapi+json\"}],\n"
             "      \"service-doc\":  [{\"href\": \"https://<domain>/docs/api\", "
             "\"type\": \"text/html\"}],\n"
             "      \"status\":       [{\"href\": \"https://<domain>/api/health\"}]\n"
             "    }\n  ]\n}\n```",
        acceptance=[
            "GET /.well-known/api-catalog returns 200 with Content-Type: application/linkset+json",
            "The body has a `linkset` array; each entry has an `anchor`",
            "Every href in the catalog resolves to 200",
        ],
        verify=["curl -sS -H 'Accept: application/linkset+json' https://<domain>/.well-known/api-catalog"],
    ),
    "AGT.OAUTH_DISCOVERY": PromptSpec(
        check_id="AGT.OAUTH_DISCOVERY",
        title="Publish OAuth/OIDC discovery metadata",
        problem="Neither `/.well-known/openid-configuration` nor "
                "`/.well-known/oauth-authorization-server` is served, so agents "
                "cannot discover how to authenticate against your APIs.",
        artefact="well_known",
        body="Publish discovery metadata containing at minimum `issuer`, "
             "`authorization_endpoint`, `token_endpoint`, `jwks_uri` and "
             "`grant_types_supported`. Use `/.well-known/openid-configuration` for "
             "OIDC or `/.well-known/oauth-authorization-server` for plain OAuth 2.0. "
             "If you use a hosted IdP (Auth0, Clerk, WorkOS, Okta, Keycloak), the "
             "correct action is usually to proxy or link to ITS discovery document "
             "rather than hand-writing one.",
        acceptance=[
            "The discovery document returns 200 JSON",
            "`issuer` exactly matches the URL it is served from (per spec)",
            "`jwks_uri` resolves and returns a valid key set",
        ],
        verify=["curl -sS https://<domain>/.well-known/openid-configuration | head -40"],
        constraints=["Only publish this if the site genuinely exposes protected "
                     "APIs — advertising an auth server that does not exist is "
                     "worse than publishing nothing."],
    ),
    "AGT.OAUTH_PR": PromptSpec(
        check_id="AGT.OAUTH_PR",
        title="Publish OAuth Protected Resource Metadata (RFC 9728)",
        problem="`/.well-known/oauth-protected-resource` is absent, so an agent "
                "holding no token cannot learn which authorization server issues "
                "tokens for this resource.",
        artefact="well_known",
        body="Serve `/.well-known/oauth-protected-resource`:\n\n"
             "```json\n{\n  \"resource\": \"https://<domain>\",\n"
             "  \"authorization_servers\": [\"https://auth.<domain>\"],\n"
             "  \"scopes_supported\": [\"read\", \"write\"],\n"
             "  \"bearer_methods_supported\": [\"header\"]\n}\n```\n\n"
             "Also return `WWW-Authenticate: Bearer resource_metadata=\"…\"` on 401 "
             "responses from protected endpoints.",
        acceptance=[
            "GET /.well-known/oauth-protected-resource returns 200 JSON",
            "`authorization_servers` lists reachable issuer URLs",
            "Protected endpoints return WWW-Authenticate pointing at this metadata",
        ],
        verify=["curl -sS https://<domain>/.well-known/oauth-protected-resource",
                "curl -sSI https://<domain>/api/ | grep -i www-authenticate"],
    ),
    "AGT.AUTH_MD": PromptSpec(
        check_id="AGT.AUTH_MD",
        title="Publish /auth.md for agent registration",
        problem="`/auth.md` is absent, so an agent cannot read, in plain language, "
                "how to register and obtain credentials for this site.",
        artefact="static",
        body="Serve `/auth.md` as markdown describing: how an agent registers, "
             "which identity and credential types you accept, the scopes "
             "available, rate limits, and revocation/contact details. Pair it with "
             "`/.well-known/oauth-protected-resource` and, where applicable, an "
             "`agent_auth` block in your authorization-server metadata.",
        acceptance=[
            "GET /auth.md returns 200 and is markdown (not an HTML 404 page)",
            "It documents registration, credential types, scopes and revocation",
            "Any URLs it references resolve",
        ],
        verify=["curl -sS -H 'Accept: text/markdown' https://<domain>/auth.md | head -40"],
    ),
    "AGT.MCP_CARD": PromptSpec(
        check_id="AGT.MCP_CARD",
        title="Publish an MCP Server Card",
        problem="No MCP Server Card was found, so agents cannot discover or "
                "connect to your MCP server without manual configuration.",
        artefact="well_known",
        body="Serve `/.well-known/mcp/server-card.json`:\n\n"
             "```json\n{\n  \"serverInfo\": {\"name\": \"<site> MCP\", "
             "\"version\": \"1.0.0\"},\n"
             "  \"endpoint\": \"https://<domain>/mcp\",\n"
             "  \"transport\": \"streamable-http\",\n"
             "  \"capabilities\": {\"tools\": {}, \"resources\": {}}\n}\n```\n\n"
             "Only publish this if an MCP server is actually running at `endpoint`.",
        acceptance=[
            "GET /.well-known/mcp/server-card.json returns 200 JSON",
            "It contains `serverInfo` (name, version) and a transport `endpoint`",
            "The `endpoint` is reachable and speaks MCP",
        ],
        verify=["curl -sS https://<domain>/.well-known/mcp/server-card.json"],
    ),
    "AGT.A2A_CARD": PromptSpec(
        check_id="AGT.A2A_CARD",
        title="Publish an A2A Agent Card",
        problem="No A2A Agent Card is served, so other agents cannot discover "
                "what your agent does or how to call it.",
        artefact="well_known",
        body="Serve `/.well-known/agent-card.json` (RFC 8615 well-known path):\n\n"
             "```json\n{\n  \"name\": \"<Agent name>\",\n"
             "  \"description\": \"What this agent does\",\n"
             "  \"url\": \"https://<domain>/a2a\",\n"
             "  \"version\": \"1.0.0\",\n"
             "  \"capabilities\": {\"streaming\": true},\n"
             "  \"skills\": [{\"id\": \"search\", \"name\": \"Search\", "
             "\"description\": \"Search the catalogue\"}]\n}\n```\n\n"
             "Add `Cache-Control` and an `ETag` so clients can revalidate cheaply.",
        acceptance=[
            "GET /.well-known/agent-card.json returns 200 JSON",
            "It contains name, description, url, version and a skills array",
            "The `url` endpoint actually serves A2A",
        ],
        verify=["curl -sS https://<domain>/.well-known/agent-card.json"],
    ),
    "AGT.AGENT_SKILLS": PromptSpec(
        check_id="AGT.AGENT_SKILLS",
        title="Publish an Agent Skills discovery index",
        problem="No Agent Skills index is served, so agents cannot discover or "
                "integrity-check the skills your site offers.",
        artefact="well_known",
        body="Serve `/.well-known/agent-skills/index.json` (Agent Skills Discovery "
             "RFC v0.2.0):\n\n```json\n{\n"
             "  \"$schema\": \"https://agentskills.io/schema/v0.2.0/index.json\",\n"
             "  \"skills\": [\n    {\n      \"name\": \"example-skill\",\n"
             "      \"type\": \"prompt\",\n      \"description\": \"What it does\",\n"
             "      \"url\": \"https://<domain>/skills/example.md\",\n"
             "      \"sha256\": \"<digest of the skill file>\"\n    }\n  ]\n}\n```\n\n"
             "The `sha256` must be the real digest of the fetched skill file.",
        acceptance=[
            "GET /.well-known/agent-skills/index.json returns 200 JSON",
            "It has a `$schema` and a `skills` array",
            "Each skill has name, type, description, url and a correct sha256",
            "Each skill `url` resolves to 200",
        ],
        verify=["curl -sS https://<domain>/.well-known/agent-skills/index.json"],
    ),
    "AGT.AI_PLUGIN": PromptSpec(
        check_id="AGT.AI_PLUGIN",
        title="(Optional) Publish a legacy AI plugin manifest",
        problem="No `/.well-known/ai-plugin.json` is served. This is a legacy "
                "discovery format largely superseded by MCP.",
        artefact="well_known",
        body="Only add this for compatibility with older plugin-style clients. "
             "Prefer an MCP Server Card as the primary integration point.",
        acceptance=[
            "If published, GET /.well-known/ai-plugin.json returns 200 JSON",
            "Its `api.url` points at a real OpenAPI document",
        ],
        verify=["curl -sS https://<domain>/.well-known/ai-plugin.json"],
    ),
    "AGT.WEBMCP": PromptSpec(
        check_id="AGT.WEBMCP",
        title="Expose site actions to agents with WebMCP",
        problem="No WebMCP tools are registered, so an in-browser agent must "
                "reverse-engineer your UI — clicking around and guessing at "
                "selectors — instead of calling your functionality directly.",
        artefact="static",
        body="Register your key actions on page load:\n\n"
             "```js\nif (navigator.modelContext) {\n"
             "  navigator.modelContext.provideContext({\n    tools: [{\n"
             "      name: 'search_products',\n"
             "      description: 'Search the catalogue by keyword',\n"
             "      inputSchema: { type: 'object',\n"
             "        properties: { query: { type: 'string' } },\n"
             "        required: ['query'] },\n"
             "      async execute({ query }) {\n"
             "        const r = await fetch(`/api/search?q=${encodeURIComponent(query)}`);\n"
             "        return { content: [{ type: 'text', text: await r.text() }] };\n"
             "      }\n    }]\n  });\n}\n```\n\n"
             "Start with the 3-5 actions that matter most (search, add to cart, "
             "book, contact). Feature-detect so browsers without WebMCP are "
             "unaffected.",
        acceptance=[
            "navigator.modelContext.provideContext() is called on page load",
            "Each tool has name, description, a valid JSON-Schema inputSchema and execute()",
            "Tools call real endpoints and return useful content",
            "The code is feature-detected and breaks nothing without WebMCP",
        ],
        verify=["# In the browser console on the homepage:",
                "navigator.modelContext ? 'WebMCP available' : 'not supported'"],
    ),
    "AGT.X402": PromptSpec(
        check_id="AGT.X402",
        title="Support x402 agent-native payments",
        problem="No endpoint returns HTTP 402 with machine-readable payment "
                "requirements, so an agent cannot pay for access programmatically.",
        artefact="headers",
        body="Add x402 middleware to paid API routes so they return `402 Payment "
             "Required` with the payment requirements an agent can satisfy "
             "automatically (facilitator URL, accepted asset, amount, pay-to address).",
        acceptance=[
            "A protected route returns 402 with an x402 payment-requirements body",
            "Paying the stated requirement grants access to the resource",
            "Unpaid requests never leak the protected content",
        ],
        verify=["curl -sS -D- https://<domain>/api/v1 | head -20"],
        constraints=["This handles money. Test end-to-end on a testnet/sandbox "
                     "facilitator before enabling in production."],
    ),
    "AGT.MPP": PromptSpec(
        check_id="AGT.MPP",
        title="Support MPP payment discovery",
        problem="No `/openapi.json` with `x-payment-info` extensions was found, so "
                "agents cannot discover which operations are payable or on what terms.",
        artefact="static",
        body="Publish `/openapi.json` and add `x-payment-info` to each payable "
             "operation, declaring `intent` (charge|session), `method`, `amount` "
             "and `currency`.",
        acceptance=[
            "GET /openapi.json returns 200 JSON",
            "Payable operations carry an `x-payment-info` extension",
            "Declared amounts and currencies match what you actually charge",
        ],
        verify=["curl -sS https://<domain>/openapi.json | head -40"],
        constraints=["This handles money. Verify amounts against your billing "
                     "system before publishing."],
    ),
    "AGT.UCP": PromptSpec(
        check_id="AGT.UCP",
        title="Publish a UCP profile",
        problem="`/.well-known/ucp` is absent, so agents cannot discover your "
                "Universal Commerce Protocol services.",
        artefact="well_known",
        body="Serve `/.well-known/ucp` describing your protocol version, services, "
             "capabilities and endpoints. Ensure every referenced spec URL and "
             "schema is reachable.",
        acceptance=[
            "GET /.well-known/ucp returns 200 JSON",
            "It declares version, services, capabilities and endpoints",
            "Referenced endpoints resolve",
        ],
        verify=["curl -sS https://<domain>/.well-known/ucp"],
        constraints=["This handles money. Validate against the UCP schema first."],
    ),
    "AGT.ACP": PromptSpec(
        check_id="AGT.ACP",
        title="Publish ACP discovery metadata",
        problem="`/.well-known/acp.json` is absent, so agents must create a "
                "checkout session before they can discover your commerce API.",
        artefact="well_known",
        body="Serve `/.well-known/acp.json` at the origin root:\n\n"
             "```json\n{\n  \"protocol\": {\"name\": \"acp\", \"version\": \"1.0\"},\n"
             "  \"api_base_url\": \"https://<domain>/api/acp\",\n"
             "  \"transports\": [\"https\"],\n"
             "  \"capabilities\": {\"services\": [\"checkout\"]}\n}\n```",
        acceptance=[
            "GET /.well-known/acp.json returns 200 JSON",
            'protocol.name is "acp" and protocol.version is set',
            "`api_base_url` is reachable and implements the declared services",
        ],
        verify=["curl -sS https://<domain>/.well-known/acp.json"],
        constraints=["This handles money. Test the checkout flow in sandbox first."],
    ),
}
