"""Tech-stack profiles.

The same SEO or agentic defect is fixed in a completely different place on every
platform: `robots.txt` is a physical file on a static site, a `robots.ts` route
handler on Next.js, a filter hook on WordPress, and a theme setting on Shopify.
A prompt that says "edit robots.txt" is useless to an agent working on Next.js —
it will create a dead file under `public/` that the framework overrides.

Each profile therefore carries the concrete *where* and *how* for a stack, so the
generated prompt lands the agent in the right file with the right idiom on the
first try.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class StackProfile:
    key: str
    label: str
    # Where the agent should put/edit each artefact on this stack.
    robots: str
    sitemap: str
    headers: str
    static_root: str
    well_known: str
    # Platform idioms, keyed by the artefact they apply to ("*" = always).
    # Scoped rather than flat so a 404 fix is not handed advice about
    # robots.txt route handlers — irrelevant notes are noise that make an agent
    # second-guess the actual task.
    notes: Dict[str, List[str]] = field(default_factory=dict)
    verify: List[str] = field(default_factory=list)

    def notes_for(self, artefact: str) -> List[str]:
        return list(self.notes.get(artefact, [])) + list(self.notes.get("*", []))

    def location(self, artefact: str) -> str:
        return {
            "robots": self.robots,
            "sitemap": self.sitemap,
            "headers": self.headers,
            "static": self.static_root,
            "well_known": self.well_known,
        }.get(artefact, self.static_root)


_GENERIC = StackProfile(
    key="generic",
    label="Generic / unknown stack",
    robots="the file served at /robots.txt",
    sitemap="the file served at /sitemap.xml",
    headers="your web server or CDN response-header configuration",
    static_root="the document root served at /",
    well_known="a `.well-known/` directory at the document root",
    notes={"*": [
        "Identify how static files at the document root are served before "
        "creating any file, and confirm the framework does not generate the "
        "same path dynamically (a generated route always wins over a static file).",
    ]},
    verify=["curl -sSI https://<domain>/<path>", "curl -sS https://<domain>/<path>"],
)

PROFILES: Dict[str, StackProfile] = {
    "generic": _GENERIC,
    "wordpress": StackProfile(
        key="wordpress",
        label="WordPress",
        robots="a physical `robots.txt` in the web root, or the `robots_txt` filter "
               "in your theme's `functions.php` / a small mu-plugin",
        sitemap="your SEO plugin's sitemap (Yoast, Rank Math, AIOSEO) or WordPress "
                "core's `wp-sitemap.xml`",
        headers="`.htaccess` (Apache), the nginx server block, or the "
                "`send_headers` action in a mu-plugin",
        static_root="the WordPress web root (alongside `wp-config.php`)",
        well_known="a `.well-known/` directory in the web root (ensure the server "
                   "does not block dotted directories)",
        notes={
            "*": ["Never edit WordPress core files.",
                  "Prefer a small must-use plugin in `wp-content/mu-plugins/` over "
                  "editing theme files: theme edits are lost on theme updates."],
            "robots": ["If an SEO plugin (Yoast/Rank Math/AIOSEO) manages robots.txt, "
                       "change it THERE — a static file is shadowed by the plugin's "
                       "virtual route."],
            "sitemap": ["If an SEO plugin owns the sitemap, change it there; WordPress "
                        "core's `wp-sitemap.xml` is disabled when a plugin takes over."],
            "static": ["Content changes belong in the CMS field or template, not in "
                       "rendered output, or the next edit reverts them."],
        },
        verify=["curl -sS https://<domain>/robots.txt",
                "wp option get blog_public   # 0 blocks indexing entirely"],
    ),
    "nextjs": StackProfile(
        key="nextjs",
        label="Next.js",
        robots="`app/robots.ts` (App Router) or `pages/api/robots.ts`; a static "
               "`public/robots.txt` only if no route handler exists",
        sitemap="`app/sitemap.ts` (App Router `MetadataRoute.Sitemap`) or a "
                "generated `public/sitemap.xml`",
        headers="the `headers()` function in `next.config.js`, or middleware",
        static_root="the `public/` directory",
        well_known="`public/.well-known/` (files there are served verbatim), or a "
                   "route handler under `app/.well-known/…/route.ts`",
        notes={
            "robots": ["A route handler (`app/robots.ts`) overrides a static file of "
                       "the same path in `public/` — never create both."],
            "sitemap": ["`app/sitemap.ts` overrides `public/sitemap.xml`; use one."],
            "well_known": ["For JSON at a well-known path, a Route Handler returning "
                           "`NextResponse.json()` with an explicit `Content-Type` is "
                           "more reliable than a static file."],
            "headers": ["Set redirects in `redirects()` and headers in `headers()` in "
                        "`next.config.js`; on Vercel `vercel.json` can also set them — "
                        "keep it in ONE place to avoid conflicts."],
            "static": ["Metadata belongs in the route's `metadata` export (App Router) "
                       "rather than hand-written <head> tags."],
        },
        verify=["npm run build", "curl -sSI https://<domain>/", "curl -sS https://<domain>/robots.txt"],
    ),
    "shopify": StackProfile(
        key="shopify",
        label="Shopify",
        robots="`templates/robots.txt.liquid` in your theme",
        sitemap="Shopify generates `/sitemap.xml` automatically (not directly editable)",
        headers="Shopify does not expose arbitrary response headers; use theme "
                "`<meta>` tags, or Shopify Oxygen/Hydrogen if you need headers",
        static_root="theme `assets/` (served under `/cdn/shop/files/…`, NOT at the root)",
        well_known="Shopify does not allow arbitrary root paths — use a reverse "
                   "proxy in front, or Shopify Functions/App Proxy",
        notes={
            "well_known": ["Shopify restricts root-level files: you generally CANNOT "
                           "serve `/.well-known/…` from the theme. Report this limit "
                           "rather than inventing a path that cannot exist."],
            "robots": ["`templates/robots.txt.liquid` is the supported override point."],
            "headers": ["Shopify does not expose arbitrary response headers from the "
                        "theme; report this rather than faking it."],
        },
        verify=["curl -sS https://<domain>/robots.txt"],
    ),
    "astro": StackProfile(
        key="astro", label="Astro",
        robots="`public/robots.txt`, or an endpoint at `src/pages/robots.txt.ts`",
        sitemap="`@astrojs/sitemap` integration output",
        headers="your host's config (`netlify.toml`, `vercel.json`, `_headers`)",
        static_root="the `public/` directory",
        well_known="`public/.well-known/`",
        notes={"*": ["Files in `public/` are copied verbatim to the build output root."]},
        verify=["npm run build", "curl -sS https://<domain>/robots.txt"],
    ),
    "hugo": StackProfile(
        key="hugo", label="Hugo",
        robots="`static/robots.txt`, or `layouts/robots.txt` with "
               "`enableRobotsTXT = true` in `hugo.toml`",
        sitemap="Hugo's built-in sitemap (`/sitemap.xml`)",
        headers="your host's config (`_headers` for Netlify/Cloudflare Pages)",
        static_root="the `static/` directory",
        well_known="`static/.well-known/`",
        notes={"*": ["Everything under `static/` is copied to the site root at build."]},
        verify=["hugo --gc --minify", "curl -sS https://<domain>/robots.txt"],
    ),
    "django": StackProfile(
        key="django", label="Django",
        robots="a URL route returning `TemplateResponse(content_type='text/plain')`, "
               "or `STATIC_ROOT` if served statically",
        sitemap="`django.contrib.sitemaps`",
        headers="middleware, or the fronting nginx/Apache config",
        static_root="`STATIC_ROOT` / whatever the web server serves at `/`",
        well_known="an explicit URL route per well-known path (simplest and most "
                   "reliable in Django)",
        notes={"well_known": ["Prefer explicit `urlpatterns` entries for well-known "
                              "paths so they work identically in dev and production."]},
        verify=["python manage.py check", "curl -sS https://<domain>/robots.txt"],
    ),
    "rails": StackProfile(
        key="rails", label="Ruby on Rails",
        robots="`public/robots.txt`",
        sitemap="a generated sitemap (e.g. `sitemap_generator` gem)",
        headers="`config/application.rb` (`config.action_dispatch.default_headers`) "
                "or the fronting web server",
        static_root="the `public/` directory",
        well_known="`public/.well-known/`",
        notes={"*": ["Files under `public/` are served directly and bypass the router."]},
        verify=["bin/rails zeitwerk:check", "curl -sS https://<domain>/robots.txt"],
    ),
    "cloudflare": StackProfile(
        key="cloudflare", label="Cloudflare Pages / Workers",
        robots="`public/robots.txt`, or a Worker route",
        sitemap="a build-generated sitemap, or a Worker route",
        headers="the `_headers` file, or `Response` headers set in the Worker",
        static_root="the build output directory",
        well_known="`public/.well-known/`, or a Worker route matching the path",
        notes={
            "robots": ["Cloudflare can serve managed robots.txt and Content Signals "
                       "from the dashboard — check there first, or the two conflict."],
            "well_known": ["A Worker can synthesise well-known JSON without a rebuild."],
            "headers": ["Set headers in `_headers` or in the Worker response, not both."],
        },
        verify=["curl -sSI https://<domain>/", "curl -sS https://<domain>/robots.txt"],
    ),
    "static": StackProfile(
        key="static", label="Static site",
        robots="`/robots.txt` at the document root",
        sitemap="`/sitemap.xml` at the document root",
        headers="your host or CDN header configuration",
        static_root="the document root",
        well_known="a `.well-known/` directory at the document root",
        notes={"well_known": ["Confirm your host does not strip dot-directories "
                              "like `.well-known`."]},
        verify=["curl -sS https://<domain>/robots.txt"],
    ),
}

# Detector output → profile key. The detector emits lowercase stack slugs.
_ALIASES = {
    "woocommerce": "wordpress",
    "wp": "wordpress",
    "next": "nextjs",
    "next.js": "nextjs",
    "vercel": "nextjs",
    "gatsby": "static",
    "jekyll": "static",
    "eleventy": "static",
    "11ty": "static",
    "nuxt": "nextjs",
    "sveltekit": "nextjs",
    "remix": "nextjs",
    "cloudflare pages": "cloudflare",
    "cf-pages": "cloudflare",
    "shopify plus": "shopify",
}


def resolve_stack(stack: Optional[str]) -> StackProfile:
    """Map a detected stack string to the closest profile (never raises)."""
    if not stack:
        return _GENERIC
    key = stack.strip().lower()
    key = _ALIASES.get(key, key)
    return PROFILES.get(key, _GENERIC)
