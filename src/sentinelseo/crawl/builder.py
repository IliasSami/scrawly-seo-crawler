from typing import List, Optional

from sentinelseo.checks.registry import CrawlContext

from .models import ImageRow, StructuredDataRow, UrlRenderDiffRow, URLRow


def build_crawl_context(
    url_row: URLRow,
    render_diffs: List[UrlRenderDiffRow],
    images: List[ImageRow],
    structured_data: List[StructuredDataRow],
    raw_html: str,
    rendered_html: Optional[str] = None,
) -> CrawlContext:
    return CrawlContext(
        url=url_row.address,
        title=url_row.title,
        url_row=url_row,
        render_diffs=render_diffs,
        images=images,
        structured_data=structured_data,
        raw_html=raw_html,
        rendered_html=rendered_html,
    )
