"""Render the audit report HTML to PDF with the crawler's own Chromium, so the
PDF looks identical to the on-screen report and needs no extra system libraries."""
from __future__ import annotations

import asyncio

from playwright.async_api import async_playwright

from sentinelseo.crawl.browser import launch_chromium


async def html_to_pdf(html: str) -> bytes:
    async with async_playwright() as pw:
        browser = await launch_chromium(pw)
        try:
            page = await browser.new_page()
            await page.set_content(html, wait_until="load")
            pdf: bytes = await page.pdf(
                format="A4", print_background=True,
                margin={"top": "12mm", "bottom": "14mm", "left": "10mm", "right": "10mm"})
            return pdf
        finally:
            await browser.close()


def html_to_pdf_sync(html: str) -> bytes:
    """Blocking variant for synchronous callers (CLI, MCP tools)."""
    return asyncio.run(html_to_pdf(html))
