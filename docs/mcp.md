# MCP interface

The local Model Context Protocol server exposes versioned R[AI]DAR reports to compatible clients over standard input/output. It reads repository files only: it does not collect sources, invoke an LLM, use GetXAPI, or require provider credentials.

## Install and start

From a cloned repository and active Python 3.11+ virtual environment:

```bash
python -m pip install -r requirements/mcp.txt
python mcp_server.py
```

Direct execution waits for an MCP client on stdio, so an apparently idle terminal is expected.

## Client configuration

Use an absolute repository path in the client that launches the process. Replace the placeholders with local paths; do not commit a user-specific path.

```json
{
  "mcpServers": {
    "wiredframe-radar": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["/absolute/path/to/wiredframe-radar/mcp_server.py"]
    }
  }
}
```

No `env` block is required for read-only report access.

## Tools

| Tool | Input | Output |
|---|---|---|
| `list_available_dates` | Empty object | Descending list of date directories under `web/data/` |
| `get_daily_summary` | `date` in `YYYY-MM-DD` | Complete `summary.json` for that date |
| `search_intelligence` | Non-empty `query` string | Matching dates from executive summaries and top-topic names/descriptions |

Search is a case-insensitive substring scan of summary artifacts, not semantic retrieval and not a complete scan of every category item. Use `get_daily_summary` or the category JSON files when exact evidence inspection is required.

## Availability and failures

- Historical availability is limited to date directories present in the local checkout.
- An invalid date format, missing report, missing data directory, or unknown tool returns a textual error result rather than calling an external service.
- Malformed historical JSON is skipped during search; a directly requested malformed file currently surfaces a server-side parsing failure.
- Update the checkout to receive newly published reports.

The public report shape is documented in [Data contracts](data-contracts.md). MCP changes require mocked protocol tests and must preserve the zero-paid-call guarantee.

[Back to documentation index](README.md)
