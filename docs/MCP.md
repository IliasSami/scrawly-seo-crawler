# Use your audits from an AI assistant (MCP)

Scrawly includes an **MCP server** (Model Context Protocol), so AI assistants that support
MCP (for example Claude Desktop, Claude Code or Cursor) can read your audits, explain
findings, compare crawls and, with your confirmation, apply WordPress fixes.

Audits are run in the Scrawly app; the MCP server works with the audits stored on your
computer.

## Set it up

Add Scrawly to your assistant's MCP configuration. Replace `/path/to/Scrawly` with the
folder Scrawly is installed in (by default `Scrawly` in your home folder), and point
`SCRAWLY_DB_PATH` at your audit database:

| System | Audit database |
|---|---|
| macOS | `~/Library/Application Support/Scrawly/scrawly.db` |
| Windows | `%APPDATA%\Scrawly\scrawly.db` |
| Linux | `~/.local/share/scrawly/scrawly.db` |

```json
{
  "mcpServers": {
    "scrawly": {
      "command": "/path/to/Scrawly/.venv/bin/fastmcp",
      "args": ["run", "/path/to/Scrawly/src/sentinelseo/mcp/server.py"],
      "env": {
        "SCRAWLY_DB_PATH": "/Users/you/Library/Application Support/Scrawly/scrawly.db"
      }
    }
  }
}
```

On Windows, use `C:\\Users\\you\\Scrawly\\.venv\\Scripts\\fastmcp.exe` as the command.

## Tools

| Tool | What it does |
|---|---|
| `list_crawls` | Your recent audits with their ids |
| `get_issues` | Findings for an audit, optionally by severity or fix tier |
| `get_page_detail` | Everything Scrawly recorded about one page |
| `propose_fix` | The recommended fix for a finding and the pages it affects (writes nothing) |
| `diff_crawls` | What was resolved, what is new and what persists between two audits |
| `check_ai_access` | Which AI crawlers a site allows or blocks |
| `run_lighthouse` | PageSpeed Insights data for a URL (needs `PAGESPEED_API_KEY`) |
| `generate_report` | The audit report as HTML or PDF |
| `apply_fix` | Apply a fix to WordPress (requires `confirm=True`) |
| `create_redirect` | Add a 301 redirect on WordPress to resolve a finding (requires `confirm=True`) |
| `revert` | Undo a fix using its stored rollback snapshot |

## Safety

The write tools follow the same rules as the app:

- nothing is written without an explicit `confirm=True`;
- a rollback snapshot is stored **before** every write, and `revert` undoes it;
- findings in the manual-only tier are **never** auto-fixed, whatever the request says.

The write tools talk to WordPress through its REST API with an Application Password set in
the environment: `SCRAWLY_WP_URL`, `SCRAWLY_WP_USER`, `SCRAWLY_WP_APP_PASS` (encrypted with
`SCRAWLY_ENCRYPTION_KEY`). Add them to the `env` block above only if you want the assistant
to make changes.
