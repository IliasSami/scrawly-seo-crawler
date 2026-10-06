"""Tech-stack fingerprinting."""
from sentinelseo.detect.fingerprint import DetectionResult, detect_from_response


def _d(headers: dict[str, str] | None = None, html: str = "") -> DetectionResult:
    return detect_from_response("https://ex.com", headers, html)


def test_wordpress_from_wp_content() -> None:
    r = _d(html='<link href="https://ex.com/wp-content/themes/x/style.css">')
    assert r.stack == "wordpress"
    assert r.confidence > 0.4


def test_woocommerce_subcategory() -> None:
    html = (
        '<link href="/wp-content/plugins/woocommerce/assets/x.css">'
        '<body class="woocommerce-page"><a class="add-to-cart">Buy</a>'
    )
    r = _d(html=html)
    assert r.stack == "wordpress"
    assert r.subcategory == "woocommerce"


def test_shopify_from_header() -> None:
    r = _d(headers={"X-ShopId": "12345"}, html="<html></html>")
    assert r.stack == "shopify"


def test_nextjs_case_sensitive_marker() -> None:
    r = _d(html='<script id="__NEXT_DATA__" type="application/json">{}</script>')
    assert r.stack == "nextjs"


def test_generator_meta_drives_ghost() -> None:
    r = _d(html='<meta name="generator" content="Ghost 5.0">')
    assert r.stack == "ghost"
    assert r.generator.startswith("Ghost")


def test_laravel_from_cookie() -> None:
    r = _d(headers={"Set-Cookie": "laravel_session=abc; path=/"}, html="<html></html>")
    assert r.stack == "laravel"


def test_unknown_is_generic_zero_confidence() -> None:
    r = _d(html="<html><body>hello</body></html>")
    assert r.stack == "generic"
    assert r.confidence == 0.0


def test_server_and_powered_by_surfaced() -> None:
    r = _d(headers={"Server": "nginx", "X-Powered-By": "PHP/8.2"}, html="")
    assert r.server == "nginx"
    assert r.powered_by == "PHP/8.2"  # original case preserved for display
