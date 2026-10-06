"""Runner for the origin-level agentic audit.

Fixed cost by design: one pass over the origin's well-known paths, headers and
DNS — roughly 25 requests whether the site has 10 pages or 100,000. All probes
run concurrently behind a bounded semaphore, and the whole run is wrapped in a
hard deadline so an unresponsive origin degrades to partial results instead of
stalling an audit.
"""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any, List, Optional

import httpx

from .models import AgenticReport, Category, ProbeResult, ProbeStatus, Step
from .probes import (
    COMMERCE_PROBES,
    SIMPLE_PROBES,
    ProbeContext,
)

# Does this origin actually SELL something an agent could transact against?
# Commerce probes only score when it does, so a blog is never marked down for
# lacking an agent payment rail.
#
# This has to key on transactional MECHANISM, not vocabulary. Naive matching on
# words like "shopify"/"woocommerce" or on a bare schema.org/Offer produces false
# positives on ordinary marketing sites: an agency that lists the platforms it
# works with, or a consultancy whose Offer wraps a *Service* with a monthly
# price, is not a storefront. Each pattern below requires a runtime artefact, a
# real cart/checkout route, or a Product (never merely an Offer).

# Platform runtime artefacts — asset hosts, plugin paths and JS globals that
# only exist when the store software is actually running.
_PLATFORM_RUNTIME = re.compile(
    r"(cdn\.shopify\.com|shopify\.shop|Shopify\.theme|"
    r"/wp-content/plugins/woocommerce|woocommerce-(?:js|no-js|page|cart)|"
    r"cdn11\.bigcommerce\.com|bigcommerce\.com/s-|"
    r"Mage\.Cookies|/static/version\d+/frontend|"          # Magento
    r"prestashop|opencart|snipcart|ecwid|"
    r"squarespace\.com/commerce|checkout\.stripe\.com|js\.stripe\.com/v3)",
    re.I,
)

# A real cart/checkout affordance: an add-to-cart control, or a link/form
# targeting a cart or checkout route.
_CART_CONTROL = re.compile(
    r"(add[\s_-]?to[\s_-]?(?:cart|bag|basket)|"
    r"""(?:href|action)\s*=\s*["'][^"']*/(?:cart|checkout|basket)(?:[/?"']|$))""",
    re.I,
)

# schema.org Product (not Offer — an Offer alone covers priced services too).
_PRODUCT_SCHEMA = re.compile(
    r"""("@type"\s*:\s*"Product"|itemtype\s*=\s*["']https?://schema\.org/Product["'])""",
    re.I,
)


def _commerce_signals(html: str) -> List[str]:
    """Names of the transactional signals present, for explainability."""
    found = []
    if _PLATFORM_RUNTIME.search(html):
        found.append("ecommerce_platform_runtime")
    if _CART_CONTROL.search(html):
        found.append("cart_or_checkout_route")
    if _PRODUCT_SCHEMA.search(html):
        found.append("schema_org_product")
    return found

PROBE_CONCURRENCY = 8
RUN_DEADLINE_S = 90.0


def attach_fix_prompts(
    results: List[ProbeResult], *, site_url: str, stack: str = ""
) -> None:
    """Attach a stack-aware, copy-pasteable agent prompt to each actionable probe.

    Only probes the user can act on get one: a PASS needs no fix, and a
    NOT_APPLICABLE probe (commerce rails on a blog) would be noise.
    """
    from sentinelseo.prompts import build_agentic_prompt

    for r in results:
        if r.status not in (ProbeStatus.FAIL, ProbeStatus.INFO):
            continue
        try:
            p = build_agentic_prompt(
                r.probe_id, site_url=site_url, stack=stack, evidence=r.evidence)
        except Exception:
            continue
        if p is not None:
            r.fix_prompt = p.text


async def detect_commerce(ctx: ProbeContext) -> bool:
    r = await ctx.homepage()
    if r is None or r.status_code != 200:
        return False
    return bool(_commerce_signals((r.text or "")[:400_000]))


async def probe_webmcp(origin: str, browser: Any, timeout: float = 30.0) -> ProbeResult:
    """Detect WebMCP tools registered via `navigator.modelContext`.

    This is the one probe that needs a real browser: WebMCP tools are registered
    at runtime by page JS, so there is nothing to fetch statically. Fully
    bounded, and reports ERROR (never raises) when no browser is available.
    """
    pid, title = "AGT.WEBMCP", "WebMCP"
    goal = "Expose site actions to agents via the WebMCP browser API"
    specs = ["https://webmachinelearning.github.io/webmcp/",
             "https://developer.chrome.com/docs/ai/webmcp"]
    steps: List[Step] = [Step(action="WebMCP detection",
                              detail="Checking page for WebMCP tool registrations")]
    remediation = (
        "Call `navigator.modelContext.provideContext()` with tool definitions that "
        "expose your key actions to agents. Each tool needs a `name`, "
        "`description`, JSON-Schema `inputSchema`, and an `execute` callback — it "
        "lets an agent invoke your functionality directly instead of scraping and "
        "guessing at your UI."
    )
    if browser is None:
        steps.append(Step(action="Launch browser",
                          detail="Skipped: needs the built-in browser.",
                          ok=False))
        return ProbeResult(
            probe_id=pid, title=title, category=Category.AGENT_RUNTIME, goal=goal,
            status=ProbeStatus.ERROR,
            conclusion="WebMCP not evaluated (JS rendering disabled)",
            steps=steps, remediation=remediation, spec_urls=specs)

    ctx_b = None
    try:
        ctx_b = await asyncio.wait_for(browser.new_context(), timeout=timeout)
        page = await ctx_b.new_page()
        steps.append(Step(action=f"Navigate to {origin}",
                          detail="Loading page to detect WebMCP tool registrations"))
        # "load", not "networkidle": networkidle never settles on sites with
        # polling or analytics beacons, which turned a real result into a
        # spurious timeout. Tools are registered by page JS, so a short settle
        # after load catches late registration without waiting on the network.
        await asyncio.wait_for(
            page.goto(origin, wait_until="load", timeout=int(timeout * 1000)),
            timeout=timeout + 5)
        await page.wait_for_timeout(1200)
        info = await asyncio.wait_for(page.evaluate(
            """() => {
                const mc = navigator.modelContext;
                if (!mc) return { present: false, tools: [] };
                const t = (mc.tools || mc._tools || []);
                return {
                    present: true,
                    tools: Array.from(t).map(x => x && x.name).filter(Boolean),
                };
            }"""), timeout=timeout)
        present = bool(info.get("present"))
        tools = info.get("tools") or []
        steps.append(Step(
            action="Check imperative WebMCP API",
            detail=(f"{len(tools)} tool(s) registered via navigator.modelContext: "
                    f"{', '.join(tools[:8])}" if tools
                    else ("navigator.modelContext present but no tools registered"
                          if present else
                          "No tools registered via navigator.modelContext")),
            ok=bool(tools)))
        if tools:
            return ProbeResult(
                probe_id=pid, title=title, category=Category.AGENT_RUNTIME, goal=goal,
                status=ProbeStatus.PASS,
                conclusion=f"WebMCP exposes {len(tools)} tool(s)",
                steps=steps, evidence={"tools": tools[:20]}, spec_urls=specs)
        return ProbeResult(
            probe_id=pid, title=title, category=Category.AGENT_RUNTIME, goal=goal,
            status=ProbeStatus.FAIL,
            conclusion="No WebMCP tools detected on page load",
            steps=steps, remediation=remediation, spec_urls=specs)
    except Exception as exc:
        steps.append(Step(action="WebMCP detection",
                          detail=f"Probe failed: {type(exc).__name__}", ok=False))
        return ProbeResult(
            probe_id=pid, title=title, category=Category.AGENT_RUNTIME, goal=goal,
            status=ProbeStatus.ERROR, conclusion="WebMCP probe could not complete",
            steps=steps, remediation=remediation, spec_urls=specs)
    finally:
        if ctx_b is not None:
            try:
                await ctx_b.close()
            except Exception:
                pass


async def run_agentic_audit(
    origin: str,
    *,
    browser: Any = None,
    stack: str = "",
    client: Optional[httpx.AsyncClient] = None,
    timeout: float = 8.0,
    user_agent: str = "ScrawlyBot/1.0 (+agentic-readiness-audit)",
) -> AgenticReport:
    """Run every agentic probe against one origin and return a scored report."""
    started = time.time()
    owns_client = client is None
    client = client or httpx.AsyncClient(
        timeout=timeout, follow_redirects=True,
        limits=httpx.Limits(max_connections=12),
    )
    try:
        ctx = ProbeContext(origin, client, timeout=timeout, user_agent=user_agent)
        is_commerce = await detect_commerce(ctx)

        sem = asyncio.Semaphore(PROBE_CONCURRENCY)

        async def _guard(coro: Any, pid: str) -> Optional[ProbeResult]:
            """One failing probe must never take down the run."""
            async with sem:
                try:
                    return await asyncio.wait_for(coro, timeout=timeout * 4)
                except Exception:
                    return ProbeResult(
                        probe_id=pid, title=pid, category=Category.DISCOVERABILITY,
                        goal="", status=ProbeStatus.ERROR,
                        conclusion="Probe did not complete (timeout or network error)",
                        steps=[Step(action=pid, detail="Probe aborted", ok=False)])

        tasks = [_guard(fn(ctx), fn.__name__) for fn in SIMPLE_PROBES]
        tasks += [_guard(fn(ctx, is_commerce), fn.__name__) for fn in COMMERCE_PROBES]
        tasks.append(_guard(probe_webmcp(ctx.origin, browser), "probe_webmcp"))

        try:
            gathered = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=RUN_DEADLINE_S)
        except asyncio.TimeoutError:
            gathered = []

        results = [r for r in gathered if isinstance(r, ProbeResult)]
        # Stable, human-meaningful ordering: category first, then declaration order.
        order = {c: i for i, c in enumerate(Category)}
        results.sort(key=lambda r: (order.get(r.category, 99), r.probe_id))
        attach_fix_prompts(results, site_url=ctx.origin, stack=stack)

        return AgenticReport(
            origin=ctx.origin, results=results, stack=stack,
            is_commerce=is_commerce,
            duration_ms=int((time.time() - started) * 1000),
        )
    finally:
        if owns_client:
            await client.aclose()
