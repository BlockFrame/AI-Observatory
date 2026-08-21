# Troubleshooting

Use the first observable failure and the stored artifact for the report date. Avoid rerunning the entire pipeline until you know whether paid collection and reusable checkpoints already completed.

## Pipeline will not start

| Symptom | Likely cause | Action |
|---|---|---|
| Pricing preflight stops immediately | MiniMax price exceeds the approved ceiling or catalog lookup is invalid | Verify OpenRouter pricing; deliberately approve a new ceiling or change the route before spending on collection. |
| Missing-key error | Required route secret is absent in GitHub or `.env` | Compare enabled routes with `config/providers.yaml`; add the secret without logging its value. |
| Python/import failure | Unsupported Python or incomplete environment | Use Python 3.11+, recreate the virtual environment, and install `requirements.txt`. |

## Collection is empty or partial

- Inspect `endpoint_status.json`, `collection_status`, and `source_funnel` before changing filters.
- Distinguish an HTTP/parser failure from a valid empty coverage window.
- LessWrong uses its date-range GraphQL path; an RSS assumption is not sufficient to diagnose it.
- X is queried in batches of at most 20 accounts. A same-date rerun can reuse a successful gathering checkpoint and selectively repair failed categories.
- A category collected with items must not silently become empty during filtering or analysis; that condition is publish-blocking.

## LLM output is degraded

Inspect `llm_telemetry` by caller and route. A failed attempt may have recovered through retry or fallback, so use final status and generation quality as well as raw error rate. Invalid JSON/schema output is not proof that a model was unreachable. Topic Detection and Executive Summary fail closed when current evidence cannot be established; News filtering preserves deterministic eligible items when model filtering is malformed.

## Links are missing or malformed

Link enrichment first attaches deterministic entity/title matches, then sends only unresolved evidence blocks to the isolated MiniMax route. Missing links do not block a grounded report. Unknown evidence IDs, raw alphanumeric markers in prose, unrelated deterministic matches, malformed Markdown, or unsupported URLs are defects and should be captured with the report date and exact bullet.

## Run succeeded but production is stale

1. Confirm `web/data/<date>/summary.json` exists on `origin/main`.
2. Confirm the corresponding Vercel production deployment used that commit.
3. Check build output and the live `web/data/index.json`/page report date.
4. Distinguish a stale static deployment from a pipeline that completed without committing output.

Do not edit generated production files in the Vercel dashboard. Correct the repository source or rerun the date-pinned pipeline.

## MCP appears stuck

`python mcp_server.py` waits on stdio and normally prints no interactive prompt. Launch it through an MCP client, verify `requirements/mcp.txt` is installed, and confirm the checkout contains `web/data/`.

## Docker status

The repository contains a legacy container definition, but the current Compose environment does not yet expose the active OpenRouter/Gemini/NVIDIA routing configuration. Docker is therefore not a supported production execution path at present. Use the Python and Vercel/GitHub Actions paths documented here until [Issue #49](https://github.com/BlockFrame/wiredframe-radar/issues/49) is complete.

For incident evidence and recovery completion, follow the [Operations runbook](operations.md).

[Back to documentation index](README.md)
