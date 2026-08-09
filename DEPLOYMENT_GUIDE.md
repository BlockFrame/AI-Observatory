# Deployment guide

Production is split into two concerns: GitHub Actions generates and commits validated report data; Vercel builds and serves the static SvelteKit frontend.

## Deployment flow

```mermaid
flowchart LR
    CRON[1 AM America/New_York schedule] --> ACTION[GitHub Actions]
    MANUAL[workflow_dispatch] --> ACTION
    ACTION --> TESTS[Mocked regression tests]
    TESTS --> PIPELINE[Generate report]
    PIPELINE --> GATE[Validate report]
    GATE -->|Valid| COMMIT[Signed data commit]
    GATE -->|Invalid| RESTORE[Restore last good data]
    COMMIT --> MAIN[main]
    MAIN --> VERCEL[Vercel build]
    VERCEL --> SITE[Static site]
```

## GitHub configuration

Required repository secrets:

- `GEMINI_API_KEY`
- `OPENROUTER_API_KEY`
- `NVIDIA_API_KEY`
- `PIPELINE_SIGNING_KEY` when generated output commits are enabled

Optional secrets:

- `GETXAPI_KEY` for X collection
- `GOOGLE_API_KEY` for optional hero-image generation
- `PIPELINE_PUSH_TOKEN` when the default GitHub token is insufficient
- `LESSWRONG_PROXY_URL` or `PIPELINE_PROXY_URL` for restricted egress
- Mullvad credentials when using the workflow-managed tunnel

Useful repository variables:

- `PIPELINE_BASE_URL`
- `PIPELINE_COMMIT_PATHS`
- `LLM_MAX_RETRIES`, `LLM_HEARTBEAT_SECONDS`, and route cooldown settings
- analyzer batch and fallback-rate controls

The canonical defaults are in `.github/workflows/daily-pipeline.yml` and `config/providers.yaml`.

## Manual run

Open **Actions → Daily Pipeline → Run workflow**. Optional inputs support an explicit target date, checkpoint phase, model override, and disabling generated-output commits.

Before paid calls, the workflow runs mocked regression tests with production secrets shadowed. After generation, `scripts/validate_report.py` enforces the publish gate. Invalid output is reverted and never committed.

## Vercel

Import `BlockFrame/AI-Observatory` into Vercel. The repository’s `vercel.json` and frontend configuration define the build. Use `https://ai-observatory.vercel.app` or set the production domain through `PIPELINE_BASE_URL`.

Vercel requires no runtime database for reports: generated JSON is versioned under `web/data/` and included in the static build.

## Diagnostics

Every workflow run uploads a `pipeline-diagnostics` artifact when available:

- `data/llm_metrics.jsonl`
- `web/data/*/cost_report.json`

The report itself includes phase status, collection status, analysis funnels, evidence coverage, and LLM telemetry. Start incident analysis from the first failed or degraded phase, then inspect provider/caller telemetry rather than relying only on the final job status.

## Rollback

The publish gate automatically keeps the last good report when generation is invalid. For a code rollback, revert the relevant commit through normal Git history; do not delete historical report directories or rewrite `main`.
