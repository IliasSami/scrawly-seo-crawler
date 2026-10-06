"""On-demand page screenshots via Playwright.

Lean by design: rendered on request (when a URL detail is opened), never stored
for the whole crawl. Desktop + Googlebot-Smartphone presets.
"""
from __future__ import annotations

from typing import Any, Dict, cast

from playwright.async_api import async_playwright

from sentinelseo.crawl.browser import launch_chromium

_MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile "
    "Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)

_PRESETS: Dict[str, Dict[str, Any]] = {
    "desktop": {"viewport": {"width": 1280, "height": 800}},
    "mobile": {
        "viewport": {"width": 412, "height": 915},
        "user_agent": _MOBILE_UA,
        "is_mobile": True,
        "device_scale_factor": 2,
    },
}


async def capture_screenshot(
    url: str, device: str = "desktop", timeout_s: float = 15.0, full_page: bool = False
) -> bytes:
    """Render `url` and return a PNG. Captures whatever rendered even if the
    navigation times out (partial pages still yield a useful screenshot)."""
    opts: Dict[str, Any] = dict(_PRESETS.get(device, _PRESETS["desktop"]))
    async with async_playwright() as p:
        browser = await launch_chromium(p, headless=True)
        try:
            context = await browser.new_context(ignore_https_errors=True, **opts)
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="load", timeout=int(timeout_s * 1000))
            except Exception:
                pass  # capture the partially-rendered page
            return cast(bytes, await page.screenshot(full_page=full_page))
        finally:
            await browser.close()
