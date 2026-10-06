"""Link-type extraction (pagination/AMP/mobile-alt), srcset, cookie names."""
from sentinelseo.crawl.parser import parse_html
from sentinelseo.web.api import _cookie_names


def test_pagination_amp_mobile_extraction() -> None:
    html = """
    <html><head>
      <link rel="prev" href="/page/1">
      <link rel="next" href="/page/3">
      <link rel="amphtml" href="/amp/post">
      <link rel="alternate" media="only screen and (max-width: 640px)" href="https://m.x.com/">
    </head><body>hi</body></html>
    """
    row, _i, _s = parse_html("https://x.com/page/2", html)
    assert row.prev_url is not None and row.prev_url.endswith("/page/1")
    assert row.next_url is not None and row.next_url.endswith("/page/3")
    assert row.amp_url is not None and row.amp_url.endswith("/amp/post")
    assert row.mobile_alternate == "https://m.x.com/"


def test_srcset_extraction() -> None:
    html = '<img src="a.jpg" srcset="a-320.jpg 320w, a-640.jpg 640w">'
    _row, imgs, _s = parse_html("https://x.com/", html)
    assert imgs and imgs[0].srcset == "a-320.jpg 320w, a-640.jpg 640w"


def test_no_link_types() -> None:
    row, _i, _s = parse_html("https://x.com/", "<html><body>plain</body></html>")
    assert row.prev_url is None and row.amp_url is None


def test_cookie_names_parsing() -> None:
    hdr = "sessionid=abc; Path=/, wordpress_test=1; Expires=Wed, 01 Jan 2025; HttpOnly, _ga=GA1.2"
    names = _cookie_names(hdr)
    assert "sessionid" in names and "wordpress_test" in names and "_ga" in names
    # cookie-attribute keywords are not mistaken for names
    assert "Path" not in names and "Expires" not in names and "HttpOnly" not in names


def test_cookie_names_empty() -> None:
    assert _cookie_names(None) == []
    assert _cookie_names("") == []
