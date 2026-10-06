# Vendored third-party assets

## axe.min.js — axe-core 4.7.0

- **Upstream:** https://github.com/dequelabs/axe-core
- **Source:** https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.7.0/axe.min.js
- **SHA-256:** `ab962f1efe6968896b5b2cace712836fbf57b665d8a6200715565c83ad5089c9`
- **License:** Mozilla Public License 2.0 — © Deque Systems, Inc.
  Full text: https://github.com/dequelabs/axe-core/blob/develop/LICENSE

### Why this is vendored rather than fetched from a CDN

`measure_agentic()` injects axe-core into every rendered page to collect
accessibility violations. Loading it with `page.add_script_tag(url=...)` put a
third-party host in the crawl's hot path, which was actively harmful:

1. **It froze crawls.** A `url=` script tag waits for the document to fire script
   `onload`. Chromium's built-in XML viewer (what `sitemap.xml` renders as) never
   fires it, so the await blocked forever — it never raised, so the surrounding
   `try/except` never fired and the crawl worker held that URL in-flight
   permanently. A real crawl stalled at 108/109 URLs on `/sitemap.xml`.
2. **Privacy.** It disclosed every crawled URL to the CDN operator.
3. **Offline / air-gapped runs.** A blocked or unreachable CDN silently removed
   all accessibility data.
4. **Speed.** It added a network round-trip per rendered page.

The bundle is now injected with `add_script_tag(content=...)`, which touches no
network and does not depend on document lifecycle events.

### Updating

Re-download the desired version, update the SHA-256 above, and re-run the gate.
Violation rule IDs can change between axe major/minor versions, so check any
accessibility checks that assert on specific rule IDs before upgrading.
