"""SF-parity crawl config (Phase 1) — engine-wired options."""
from sentinelseo.crawl.fetcher import Crawler


def test_remove_parameters_strips_keys() -> None:
    c = Crawler(remove_parameters="utm_source, ref", render=False)
    out = c._rewrite_url("https://ex.com/p?utm_source=x&id=5&ref=y")
    assert "utm_source" not in out and "ref=y" not in out
    assert "id=5" in out


def test_regex_replace_is_ordered() -> None:
    c = Crawler(render=False, regex_replace=[
        {"pattern": r"^http://", "replacement": "https://"},
        {"pattern": r"page=\d+", "replacement": "page=1"},
    ])
    assert c._rewrite_url("http://ex.com/?page=7") == "https://ex.com/?page=1"


def test_lowercase_urls() -> None:
    c = Crawler(render=False, lowercase_urls=True)
    assert c._rewrite_url("https://EX.com/Path") == "https://ex.com/path"


def test_max_urls_per_depth_gate() -> None:
    c = Crawler(render=False, max_urls_per_depth=2)
    assert c._url_allowed("https://ex.com/a", 1)
    c._count_enqueue("https://ex.com/a", 1)
    c._count_enqueue("https://ex.com/b", 1)
    assert not c._url_allowed("https://ex.com/c", 1)  # depth-1 quota hit
    assert c._url_allowed("https://ex.com/d", 2)      # other depth unaffected


def test_max_per_subdomain_gate() -> None:
    c = Crawler(render=False, max_per_subdomain=1)
    assert c._url_allowed("https://a.ex.com/1", 1)
    c._count_enqueue("https://a.ex.com/1", 1)
    assert not c._url_allowed("https://a.ex.com/2", 1)   # a.ex.com quota hit
    assert c._url_allowed("https://b.ex.com/1", 1)       # different subdomain ok


def test_robots_mode_ignore_disables_respect() -> None:
    assert Crawler(render=False, robots_mode="ignore").respect_robots is False
    assert Crawler(render=False, robots_mode="respect").respect_robots is True
    # ignore_but_report still fetches (respect stays truthy so the seed check runs
    # and records, but the enforcement branch is skipped in crawl_site).
    assert Crawler(render=False, robots_mode="ignore_but_report").respect_robots is True


def test_robots_user_agent_defaults_to_http_ua() -> None:
    c = Crawler(render=False, user_agent="MyBot/1.0")
    assert c.robots_user_agent == "MyBot/1.0"
    c2 = Crawler(render=False, user_agent="MyBot/1.0", robots_user_agent="Googlebot")
    assert c2.robots_user_agent == "Googlebot"
