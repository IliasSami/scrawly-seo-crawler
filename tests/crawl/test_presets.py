"""Tech-stack config presets."""
from sentinelseo.crawl.presets import TECH_PRESETS, get_presets, resolve


def test_catalogue_has_popular_stacks() -> None:
    for k in ("wordpress", "shopify", "nextjs", "laravel", "webflow", "framer", "generic"):
        assert k in TECH_PRESETS
    cat = get_presets()
    assert cat["wordpress"]["label"] == "WordPress"
    # WordPress exposes sub-categories; a flat stack does not.
    assert "woocommerce" in cat["wordpress"]["subcategories"]
    assert cat["shopify"]["subcategories"] == {}


def test_resolve_wordpress_base() -> None:
    d = resolve("wordpress")
    assert "/wp-admin/" in d["exclude_patterns"]
    assert d["js_render"] is False


def test_resolve_woocommerce_adds_cart() -> None:
    base = resolve("wordpress")["exclude_patterns"]
    woo = resolve("wordpress", "woocommerce")["exclude_patterns"]
    assert "/cart/" not in base and "/cart/" in woo  # sub-category adds store excludes


def test_resolve_spa_enables_js() -> None:
    assert resolve("nextjs")["js_render"] is True
    assert "/_next/" in resolve("nextjs")["exclude_patterns"]


def test_resolve_unknown_is_empty() -> None:
    assert resolve("nonsense") == {}
