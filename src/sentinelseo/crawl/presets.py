"""Predefined crawl-configuration presets per tech stack / CMS.

Each preset supplies sensible exclude patterns (internal files, admin areas,
faceted/cart URLs that waste crawl budget), a JS-render default, and — for some
stacks — sub-categories (e.g. WordPress → WooCommerce / Blog / SaaS) that add
further exclusions. The UI exposes these as cascading dropdowns; `resolve()`
turns a (tech, subcategory) choice into concrete config deltas.
"""
from __future__ import annotations

from typing import Any, Dict, List

# tech -> {label, exclude[], js_render, subcategories{key -> {label, exclude_add[]}}}
TECH_PRESETS: Dict[str, Dict[str, Any]] = {
    "wordpress": {
        "label": "WordPress",
        "js_render": False,
        "exclude": [
            "/wp-admin/", "/wp-includes/", "/wp-json/", "/xmlrpc.php",
            "/wp-login.php", "/wp-content/plugins/", "/wp-content/themes/",
            "/feed/?$", "/trackback/", "/cgi-bin/", r"\?replytocom",
        ],
        "subcategories": {
            "woocommerce": {"label": "WooCommerce (store)", "exclude_add": [
                "/cart/", "/checkout/", "/my-account/", r"\?add-to-cart=",
                r"\?orderby=", r"\?wc-ajax=", r"\?filter_", "/wishlist/"]},
            "blog": {"label": "Blog / Magazine", "exclude_add": ["/tag/", "/author/", r"/page/\d+"]},
            "local_business": {"label": "Local Business", "exclude_add": []},
            "service": {"label": "Service / Agency", "exclude_add": []},
            "saas": {"label": "SaaS / App", "exclude_add": ["/login/", "/signup/", "/register/", "/dashboard/", "/app/", "/account/"]},
            "portfolio": {"label": "Portfolio", "exclude_add": []},
        },
    },
    "shopify": {
        "label": "Shopify",
        "js_render": False,
        "exclude": [
            "/cart", "/checkout", "/account", "/apps/", "/tools/", "/a/",
            r"\?variant=", r"\?sort_by=", r"/collections/.+\?", "/cdn/",
        ],
    },
    "webflow": {"label": "Webflow", "js_render": False, "exclude": ["/404", "/401", "/detail_"]},
    "framer": {"label": "Framer", "js_render": True, "exclude": []},
    "nextjs": {"label": "Next.js", "js_render": True, "exclude": ["/_next/", "/api/", "/static/"]},
    "react": {"label": "React (SPA)", "js_render": True, "exclude": ["/static/", "/assets/", "/api/"]},
    "laravel": {"label": "Laravel", "js_render": False, "exclude": [
        "/storage/", "/vendor/", "/login", "/register", "/password", "/admin", r"\?page="]},
    "drupal": {"label": "Drupal", "js_render": False, "exclude": ["/admin", "/user", "/node/add", r"\?q=", "/sites/default/files/"]},
    "joomla": {"label": "Joomla", "js_render": False, "exclude": ["/administrator/", r"\?task=", r"index\.php\?option="]},
    "magento": {"label": "Magento", "js_render": False, "exclude": [
        "/checkout/", "/customer/", "/catalogsearch/", r"\?SID=", r"\?p=", "/wishlist/"]},
    "squarespace": {"label": "Squarespace", "js_render": True, "exclude": ["/config", r"\?format=", r"\?category="]},
    "wix": {"label": "Wix", "js_render": True, "exclude": ["/_partials/", r"\?lightbox="]},
    "ghost": {"label": "Ghost", "js_render": False, "exclude": ["/ghost/", "/tag/", "/author/", "/rss/"]},
    "generic": {"label": "Generic / Custom", "js_render": False, "exclude": []},
}


def get_presets() -> Dict[str, Any]:
    """Serialize the preset catalogue for the UI (labels + subcategory options)."""
    out: Dict[str, Any] = {}
    for key, p in TECH_PRESETS.items():
        subs = p.get("subcategories") or {}
        out[key] = {
            "label": p["label"],
            "subcategories": {k: v["label"] for k, v in subs.items()},
        }
    return out


def resolve(tech: str, subcategory: str = "") -> Dict[str, Any]:
    """Turn a (tech, subcategory) choice into crawl-config deltas."""
    p = TECH_PRESETS.get(tech)
    if not p:
        return {}
    exclude: List[str] = list(p.get("exclude", []))
    subs = p.get("subcategories") or {}
    if subcategory and subcategory in subs:
        exclude += subs[subcategory].get("exclude_add", [])
    # de-dupe, preserve order
    exclude = list(dict.fromkeys(exclude))
    return {
        "exclude_patterns": ", ".join(exclude),
        "js_render": bool(p.get("js_render", False)),
    }
