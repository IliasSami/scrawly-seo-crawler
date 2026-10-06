"""Custom extraction engine (CSS / regex / search) — M5."""
from sentinelseo.crawl.custom_extract import run_custom_extraction

HTML = """
<html><body>
  <span class="price">$19.99</span>
  <span class="price">$5.00</span>
  <meta property="og:title" content="Widget">
  <a href="/a">one</a><a href="/b">two</a>
  SKU: ABC123
</body></html>
"""


def test_css_text_extraction() -> None:
    out = run_custom_extraction(HTML, [{"name": "prices", "source": "css", "expr": ".price"}])
    assert out["prices"] == ["$19.99", "$5.00"]


def test_css_attribute_extraction() -> None:
    out = run_custom_extraction(
        HTML, [{"name": "og", "source": "css", "expr": 'meta[property="og:title"]', "attr": "content"}]
    )
    assert out["og"] == ["Widget"]


def test_regex_capture_group() -> None:
    out = run_custom_extraction(HTML, [{"name": "sku", "source": "regex", "expr": r"SKU:\s*(\w+)"}])
    assert out["sku"] == ["ABC123"]


def test_regex_full_match_when_no_group() -> None:
    out = run_custom_extraction(HTML, [{"name": "dollars", "source": "regex", "expr": r"\$\d+\.\d{2}"}])
    assert out["dollars"] == ["$19.99", "$5.00"]


def test_xpath_text_extraction() -> None:
    out = run_custom_extraction(HTML, [{"name": "prices", "source": "xpath", "expr": "//span[@class='price']/text()"}])
    assert out["prices"] == ["$19.99", "$5.00"]


def test_xpath_attribute() -> None:
    out = run_custom_extraction(HTML, [{"name": "og", "source": "xpath", "expr": "//meta[@property='og:title']/@content"}])
    assert out["og"] == ["Widget"]


def test_xpath_invalid_is_safe() -> None:
    out = run_custom_extraction(HTML, [{"name": "bad", "source": "xpath", "expr": "//["}])
    assert out["bad"] == []


def test_search_counts() -> None:
    out = run_custom_extraction(HTML, [], [{"name": "links", "regex": r"<a "}])
    assert out["search:links"] == 2


def test_invalid_regex_is_safe() -> None:
    out = run_custom_extraction(HTML, [{"name": "bad", "source": "regex", "expr": "("}])
    assert out["bad"] == []


def test_empty_config_returns_empty() -> None:
    assert run_custom_extraction(HTML, [], []) == {}
