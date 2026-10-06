=== Scrawly Connector ===
Contributors: therundigital
Tags: seo, technical-seo, rest-api, wp-cli, audit
Requires at least: 5.6
Tested up to: 6.7
Requires PHP: 7.4
Stable tag: 1.0.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Secure, lightweight bridge that connects any WordPress site to Scrawly — a
technical-SEO / GEO auditor and guarded auto-fixer.

== Description ==

Scrawly Connector is a single-file, dependency-free plugin that lets Scrawly
connect to your site natively — no Application Passwords, no complicated setup.

On activation it generates a unique connection key. Paste that key (plus your
site URL) into Scrawly and you are connected. The plugin exposes a small set of
**guarded** REST endpoints (namespace `scrawly/v1`) that let Scrawly:

* Read status and detect your active SEO plugin (Yoast / Rank Math)
* Resolve a URL to its post ID
* Read and update only whitelisted SEO fields (title, meta description,
  canonical, robots) — mapped to your SEO plugin's meta keys server-side
* Manage simple redirects (built in — no extra plugin required)
* Read/serve robots.txt additions

**Safety by design**

* Every request is authenticated with a constant-time key comparison.
* Writes are limited to a fixed whitelist of SEO meta fields — the plugin never
  edits theme/plugin files and never touches post content or arbitrary options.
* A per-site "Allow fixes" toggle lets you keep the connection read-only.
* If both Yoast and Rank Math are active, writes are refused (ambiguous target).

**WP-CLI**

  wp scrawly key            # show the connection key
  wp scrawly key --regenerate
  wp scrawly status

== Installation ==

1. In wp-admin go to Plugins → Add New → Upload Plugin, choose
   `scrawly-connector.zip`, and Activate.
2. Open the new **Scrawly** menu item. Copy the Site URL and Connection Key.
3. In Scrawly, open Settings → WordPress Connection, paste both, and click Test.

== Changelog ==

= 1.0.0 =
* Initial beta release: connection-key auth, guarded SEO-meta endpoints,
  built-in redirects, robots.txt filter, WP-CLI commands, admin screen.
