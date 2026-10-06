"""SF scope / rendering / extraction options wired into the crawler."""
from typing import Any

from sentinelseo.crawl.fetcher import Crawler, _srcset_urls


def _c(**kw: Any) -> Crawler:
    c = Crawler(render=False, **kw)
    # Simulate crawl_site's seed setup.
    c._seed_netloc = "www.example.com"
    c._seed_registrable = c._registrable("www.example.com")
    c._seed_folder = kw.pop("_folder", "/")
    return c


# ---- registrable domain ----

def test_registrable_domain() -> None:
    c = Crawler(render=False)
    assert c._registrable("www.example.com") == "example.com"
    assert c._registrable("blog.example.com") == "example.com"
    assert c._registrable("example.com") == "example.com"
    assert c._registrable("shop.example.co.uk") == "example.co.uk"   # 2-part TLD


# ---- subdomain scope ----

def test_subdomains_off_excludes_other_hosts() -> None:
    c = _c()
    assert c._in_site_scope("https://www.example.com/x") is True
    assert c._in_site_scope("https://blog.example.com/x") is False   # subdomain, off


def test_subdomains_on_includes_siblings() -> None:
    c = _c(crawl_subdomains=True)
    assert c._in_site_scope("https://blog.example.com/x") is True
    assert c._in_site_scope("https://example.com/x") is True
    assert c._in_site_scope("https://other.com/x") is False          # different site


def test_cdn_treated_as_internal() -> None:
    c = _c(cdns="cdn.acme.net, assets.example.org")
    assert c._in_site_scope("https://cdn.acme.net/app.js") is True
    assert c._in_site_scope("https://evil.com/app.js") is False


# ---- start-folder scope ----

def test_start_folder_scope() -> None:
    c = _c()
    c._seed_folder = "/blog/"
    assert c._in_site_scope("https://www.example.com/blog/post") is True
    assert c._in_site_scope("https://www.example.com/about") is False   # outside folder


def test_start_folder_override() -> None:
    c = _c(crawl_outside_start_folder=True)
    c._seed_folder = "/blog/"
    assert c._in_site_scope("https://www.example.com/about") is True     # roaming allowed


# ---- srcset extraction ----

def test_srcset_urls_parsed_and_resolved() -> None:
    out = _srcset_urls("a-1x.png 1x, /img/a-2x.png 2x, https://cdn/x.png 3x",
                       "https://ex.com/page")
    assert "https://ex.com/a-1x.png" in out
    assert "https://ex.com/img/a-2x.png" in out
    assert "https://cdn/x.png" in out


def test_srcset_skips_data_uris_and_empty() -> None:
    assert _srcset_urls("data:image/png;base64,xxx 1x", "https://ex.com/") == []
    assert _srcset_urls("", "https://ex.com/") == []
    assert _srcset_urls(None, "https://ex.com/") == []


# ---- flags stored ----

def test_render_and_size_flags_stored() -> None:
    c = Crawler(render=False, window_width=411, window_height=731,
                js_error_reporting=True, max_page_size_kb=500, assume_html=False,
                follow_nofollow=True)
    assert c.window_width == 411 and c.window_height == 731
    assert c.js_error_reporting is True
    assert c.max_page_size_kb == 500
    assert c.assume_html is False
    assert c.follow_nofollow is True


def test_nofollow_default_is_respected() -> None:
    # follow_nofollow defaults False → nofollow links are skipped (SF default).
    assert Crawler(render=False).follow_nofollow is False
