"""Phase-7 SF-parity: Content Area (include/exclude) restricts the text used for
word count / duplicates / readability, and the DOM-flatten render flags are
stored on the crawler."""
from sentinelseo.crawl.fetcher import Crawler
from sentinelseo.crawl.parser import _content_area_text, parse_html

PAGE = (
    "<html><body>"
    "<nav>Home About Contact Menu Navigation Links</nav>"
    "<main><article>The actual article body has real words worth counting here today.</article></main>"
    "<footer>Copyright boilerplate footer text repeated on every single page here</footer>"
    "</body></html>"
)


def test_content_area_none_when_no_selectors() -> None:
    assert _content_area_text(PAGE, "", "") is None


def test_content_include_restricts_text() -> None:
    txt = _content_area_text(PAGE, include="main", exclude="")
    assert txt is not None
    assert "actual article body" in txt
    assert "Navigation" not in txt
    assert "boilerplate" not in txt


def test_content_exclude_drops_regions() -> None:
    txt = _content_area_text(PAGE, include="", exclude="nav, footer")
    assert txt is not None
    assert "actual article body" in txt
    assert "Navigation" not in txt
    assert "boilerplate" not in txt


def test_invalid_selector_falls_back_gracefully() -> None:
    # A malformed selector must not raise; include with no match yields None so
    # the caller keeps the default body text.
    assert _content_area_text(PAGE, include=">>bad>>", exclude="") is None


def test_parse_html_wordcount_follows_content_area() -> None:
    full, _, _ = parse_html("http://t/", PAGE)
    restricted, _, _ = parse_html("http://t/", PAGE, content_include="main")
    assert restricted.word_count < full.word_count
    assert "actual article body" in restricted.main_text
    assert "boilerplate" not in restricted.main_text
    # The content hash / near-dup cluster derive from the restricted text too.
    assert restricted.content_hash != full.content_hash


def test_crawler_stores_phase7_flags() -> None:
    c = Crawler(
        render=False, content_include="main", content_exclude="nav",
        flatten_shadow_dom=True, flatten_iframes=True,
    )
    assert c.content_include == "main"
    assert c.content_exclude == "nav"
    assert c.flatten_shadow_dom is True
    assert c.flatten_iframes is True


def test_crawler_flatten_defaults_off() -> None:
    c = Crawler(render=False)
    assert c.flatten_shadow_dom is False
    assert c.flatten_iframes is False
    assert c.content_include == ""
    assert c.content_exclude == ""
