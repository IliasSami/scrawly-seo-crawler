# Scrawly (formerly SentinelSEO) — Agent Knowledge Base

## Project Purpose
Scrawly is a free, open-source desktop SEO crawler (Python engine + web UI in a native window) that crawls any website, runs 250 technical SEO, GEO, and agentic-web checks, and generates client-readable reports. It serves as an MCP-orchestrated auditor and auto-fixer, bridging classic desktop crawler capabilities with modern AI-crawler access and agentic-web readiness checks. For a guarded, tiered subset of issues, it safely applies fixes to live WordPress sites via the REST API with a strict rollback mechanism.

## INVARIANTS (Do Not List)
These are absolute, non-negotiable rules. Any agent working on this repository MUST abide by them:

  I1. NEVER run this system against a live client website during development.
      All testing targets the local Docker WordPress at http://localhost:8080.
  I2. Every mutating operation MUST capture before-state to the `fix` table
      before writing, and MUST have a working `revert(fix_id)`. A write without
      a stored rollback is a defect, not a feature.
  I3. The fix-tier gate is enforced in CODE, inside `apply_fix`, not by model
      judgment. `apply_fix` hard-refuses any issue whose tier is FLAG
      (never-auto), regardless of what any caller, prompt, or LLM requests.
      It also requires an explicit `confirm=True` argument.
  I4. NEVER edit WordPress core files, theme PHP, `.htaccess`, `wp-config.php`,
      or robots.txt directly on disk. All writes go through the WP REST API,
      or through guarded endpoints in our own companion plugin.
  I5. Authenticate ONLY via WordPress Application Passwords, stored encrypted,
      never logged. No admin cookies. No credentials in artifacts, diffs, or
      commit messages.
  I6. Checks are pure functions. They read a CrawlContext and return a Finding
      or None. They never write to the database, the network, or the filesystem.
  I7. Crawling is polite: configurable concurrency, exponential backoff on
      429/5xx, respect robots.txt by default (and separately REPORT on it).
  I8. Do not invent SEO checks. The catalogue in docs/CHECK_MANIFEST.yaml is authoritative.
      Do not silently drop checks you find hard to implement — mark them
      `status: deferred` in the manifest and surface them to the maintainer.
  I9. Never claim a task is complete without producing a Walkthrough artifact
      showing the tests you ran and their actual output.

## Frozen Module Boundaries
The architecture is divided into the following isolated modules. Contracts and data models are defined in `docs/CONTRACTS.md` and MUST NOT be changed without explicit approval.

1. **Crawler**: Handles fetching (`httpx` + Playwright fallback), parsing, and populating the URL state. Does not run checks.
2. **Audit Rule Engine**: Executes pure check functions from `CHECK_MANIFEST.yaml` against the `CrawlContext`. Returns findings but does not write to the DB.
3. **Enrichment**: Interacts with GSC, PageSpeed Insights, DataForSEO, and Lighthouse to augment URL records.
4. **WP Fix Layer**: Interacts with the WordPress REST API and the custom companion plugin. Strictly handles writes, before-state captures, and rollbacks.
5. **MCP Server**: FastMCP implementation defining the tool surface. Enforces tier gates in code.
6. **Data Storage Layer**: SQLAlchemy models mapping to Postgres/SQLite. Owned by the DB session manager.
7. **Report/Dashboard**: Reads data to produce the final client deliverables (PDF/HTML).

## Coding Standards
- **Python Version**: Python 3.11+
- **Types**: Full type hints are required. The codebase must be `mypy --strict` clean.
- **Linting & Formatting**: Strict `ruff` compliance.
- **Exceptions**: No bare `except:` blocks allowed. Catch specific exceptions.
- **Defaults**: No mutable default arguments in functions or methods.
- **Paths**: Use `pathlib` over `os.path`.
- **Logging**: Use structured logging via `structlog`. NEVER use `print`.
- **Concurrency**: All I/O must be `async` where the underlying library supports it.

## Testing Standards
- **Framework**: Use `pytest`.
- **Rule Tests**: Every check rule MUST have at least one positive and one negative fixture test.
- **Isolation**: NO network calls in unit tests. Use recorded HTML fixtures or `respx` for `httpx` mocking.

## Definition of Done (DoD)
Before declaring ANY task complete, you must satisfy the following checklist:
- [ ] Code meets all Coding Standards (`ruff` and `mypy --strict` clean).
- [ ] Tests meet all Testing Standards (no network calls, positive/negative fixtures included).
- [ ] You have run `make lint`, `make typecheck`, and `make test`, and all pass.
- [ ] If interacting with WordPress, `make wp-up` works and the code successfully executes against the local instance.
- [ ] A Walkthrough artifact has been produced showing the exact tests run and their outputs.
- [ ] No INVARIANTS have been violated.
