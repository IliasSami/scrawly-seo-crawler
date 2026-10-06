from dataclasses import dataclass


@dataclass
class Thresholds:
    title_px_max: int = 561
    title_px_min: int = 200
    title_char_max: int = 60
    title_char_min: int = 30
    metadesc_px_max: int = 985
    metadesc_px_min: int = 400
    heading_char_max: int = 70
    low_content_words: int = 200
    thin_content_words: int = 100
    near_dup_similarity: float = 0.90
    url_char_max: int = 115
    max_links_on_page: int = 150
    max_crawl_depth: int = 4
    image_kb_max: int = 100
    alt_char_max: int = 100
    ttfb_ms_warn: float = 800.0
    dom_node_warn: int = 1500
    page_weight_mb_warn: float = 3.0
    lcp_good_s: float = 2.5
    lcp_poor_s: float = 4.0
    inp_good_ms: float = 200.0
    inp_poor_ms: float = 500.0
    cls_good: float = 0.10
    cls_poor: float = 0.25
    text_html_ratio_min: float = 0.10
    coverage_high: float = 0.20
    coverage_critical: float = 0.40
