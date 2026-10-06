# Scrawly Connector - native WordPress integration

The **Scrawly Connector** is a tiny (single-file, about 6 KB, zero dependencies)
WordPress plugin that lets Scrawly connect to a WordPress site natively: no Application
Passwords and no JWT server configuration. It generates a unique connection key, exposes a
small set of *guarded* REST endpoints, and adds WP-CLI commands.

Source: [`src/sentinelseo/wp/companion_plugin/scrawly-connector.php`](../src/sentinelseo/wp/companion_plugin/scrawly-connector.php)
Installable zip: [`src/sentinelseo/wp/companion_plugin/dist/scrawly-connector.zip`](../src/sentinelseo/wp/companion_plugin/dist/scrawly-connector.zip)

## Install (site owner, ~60 seconds)

1. **wp-admin** → Plugins → Add New → **Upload Plugin** → choose
   `scrawly-connector.zip` → **Install Now** → **Activate**.
2. Open the new **Scrawly** menu item in the sidebar. It shows your **Site URL**
   and a generated **Connection Key** (`sk_…`). Use *Copy*.

CLI alternative:

```bash
wp plugin install /path/to/scrawly-connector.zip --activate
wp scrawly key          # prints the connection key
```

## Connect (in Scrawly)

Each client connects its own site through a guided wizard:

- **UI:** Clients → **+ New Client** → enter name + Site URL → on the
  **Connect WordPress** step, paste the **Connection Key** → **Test connection**
  (expects a green ✓) → **Finish**. The key is stored on that client and used for
  its fixes; it's never shown again in lists.
- **Or API:**
  ```bash
  # create the client, then attach + verify its connection
  curl -X POST localhost:8000/api/clients -H 'Content-Type: application/json' \
    -d '{"name":"Acme","base_url":"https://example.com"}'
  curl -X POST localhost:8000/api/clients/1/wp-test -H 'Content-Type: application/json' \
    -d '{"wp_url":"https://example.com","wp_connection_key":"sk_..."}'   # handshake
  curl -X PUT  localhost:8000/api/clients/1 -H 'Content-Type: application/json' \
    -d '{"wp_url":"https://example.com","wp_connection_key":"sk_..."}'   # save
  ```
- **Or env (single-site fallback):** `SCRAWLY_WP_URL` + `SCRAWLY_WP_KEY`.

## What the plugin exposes (namespace `scrawly/v1`)

All endpoints require the `X-Scrawly-Key` header and work with **any** permalink
setting (Scrawly calls them via the universal `?rest_route=` form).

| Route | Method | Purpose |
|-------|--------|---------|
| `/status` | GET | Handshake; reports WP version, active SEO plugin, fixes-allowed |
| `/resolve` | POST | URL → post ID |
| `/post-meta/{id}` | GET / POST | Read / write **whitelisted** SEO fields only |
| `/redirects` | GET / POST / DELETE | Built-in simple redirect store |
| `/robots` | GET / POST | robots.txt additions |
| `/mcp` | GET | Tool manifest for discovery |

## Safety model

- **Auth:** constant-time (`hash_equals`) key check on every request; 401 otherwise.
- **Write whitelist:** only `title`, `meta_desc`, `canonical`, `robots` - mapped
  to Yoast / Rank Math meta keys server-side. Never edits files, post content, or
  arbitrary options.
- **Ambiguity guard:** if both Yoast and Rank Math are active, writes are refused.
- **Kill switch:** per-site *Allow fixes* toggle on the admin screen.
- **Rollback:** Scrawly snapshots the exact before-value and saves it *before*
  writing, so every fix can be undone: click an issue's **Fixed** button and choose
  **Undo**. Manual-only (higher-risk) issues are never auto-fixed, and every live
  write asks for your confirmation first.

## Verified end-to-end (local Docker WP)

Handshake → resolve URL → guarded `meta_desc` write → verify → revert → verify,
plus a FLAG-tier write correctly refused. See the connector client
[`src/sentinelseo/wp/connector.py`](../src/sentinelseo/wp/connector.py).
