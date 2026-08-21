# AGENTS.md

Repository guidance for coding agents working on R[AI]DAR.

## Project

R[AI]DAR is a Python 3.11 multi-agent pipeline and SvelteKit frontend. It collects current AI News, Research, X social signals, and GitHub Trending repositories; produces evidence-grounded category and executive analysis; and publishes validated static JSON and web output.

Active source details live in `docs/sources.md`. Do not describe Bluesky, Mastodon, Reddit, YouTube, Product Hunt, Discord, or Slack as supported sources.

## Safety and quota rules

- Do not run the live pipeline or make provider/GetXAPI calls unless the user explicitly requests it.
- Unit tests are mocked and may be run to validate code changes; keep production API keys shadowed or absent.
- Never commit `.env`, credentials, proxy secrets, raw prompts, or provider responses containing secrets.
- Preserve generated historical reports unless the task explicitly requires changing them.
- Do not bypass `scripts/validate_report.py` or weaken the publish gate to make a run green.

## Common commands

```bash
# Pipeline setup and local execution
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_pipeline.py --date 2026-08-10
python run_pipeline.py --resume
python run_pipeline.py --resume-from 4.5

# Mocked regression tests; no paid calls
python -m unittest discover -s tests -p '*_test.py'

# Frontend
npm run install:frontend
npm run dev
npm run check
npm run build

# Report validation
python scripts/validate_report.py --web-dir ./web --date 2026-08-10
```

## Architecture

The pipeline is coordinated by `agents/orchestrator.py`:

1. Initialize ecosystem and release-date grounding.
2. Gather News, Research, Social, and GitHub Trending in parallel.
3. Apply deterministic filters, deduplication, batch analysis, and ranking.
4. Detect topics supported by at least two populated current categories.
5. Generate an executive summary with exact current evidence IDs.
6. Enrich links, sanitize editorial output, and calculate quality diagnostics.
7. Serialize static reports and machine-readable discovery artifacts.
8. Validate before a generated report may be committed.

See `docs/architecture.md` for diagrams and failure boundaries.

## Active gatherers

| Category | Inputs | Implementation |
|---|---|---|
| News | RSS/Atom, direct web pages, Hacker News, articles linked from X | `agents/gatherers/news_gatherer.py`, `webscraper_gatherer.py`, `hackernews.py`, `link_follower.py` |
| Research | Hugging Face Daily Papers, AlphaXiv, research feeds, LessWrong GraphQL | `agents/gatherers/research_gatherer.py` |
| Social | X accounts through GetXAPI, 20 accounts maximum per query | `agents/gatherers/social_gatherer.py` |
| GitHub Trending | GitHub Trending | `agents/gatherers/github_trending.py` |

Source lists are configuration-driven:

- `config/rss_feeds.txt`
- `config/web_scraper_sources.txt`
- `config/research_feeds.txt`
- `config/research_web_sources.txt`
- `config/research_reference_sources.txt`
- `config/twitter_accounts.txt`

## LLM routing

`config/providers.yaml` is authoritative. The current strategy separates bulk and quality work:

- bulk map/filter: NVIDIA Nemotron, then Gemini Flash Lite fallbacks;
- ranking and synthesis: OpenRouter paid GLM 5.2, then Gemini 3.6, NVIDIA GLM, Gemini 3.5, and Flash Lite;
- link enrichment: evidence-ID-driven deterministic matching first, then an isolated
  OpenRouter MiniMax fallback that receives only still-uncovered evidence.

Routes may select both analysis profiles and `caller_patterns`. Retryable transport, timeout, rate-limit, and server failures can fail over. Prompt/schema errors must be handled by the caller according to the task’s safety policy.

New tasks should always start from their preferred route. Route cooldown state prevents repeatedly calling a provider known to be temporarily unhealthy.

## Summary grounding contract

`agents/summary_context.py` is the only place that assembles executive-summary history and current data. Both the orchestrator and `scripts/regenerate_summary.py` must use it.

- Previous summaries are anti-repetition context only and end at `=== END PREVIOUS DAYS' COVERAGE ===`.
- Current factual evidence lives inside `=== TODAY'S DATA (CURRENT EVIDENCE) ===`.
- Executive and topic outputs must return exact IDs for current items.
- Historical claims cannot be reused unless a current item independently supports them.

## Reliability requirements

- News LLM filtering is fail-open to the deterministic keyword-filtered set when JSON/schema output is invalid.
- A category that collected eligible items cannot silently collapse to zero downstream.
- Cross-category topics need current evidence from at least two non-empty categories.
- Executive evidence must cover at least two categories when two or more are available.
- `t.co` redirects are expanded before link following.
- Editorial output is sanitized through `agents/editorial_guard.py`.
- Quality rules live in `agents/quality_score.py` and the final gate in `scripts/validate_report.py`.
- Checkpoints under `data/checkpoints/<date>/` support resume; do not change checkpoint compatibility casually.

## Telemetry

`agents/llm_client.py` emits provider, route, caller, attempts, latency, token, and error metadata. `agents/cost_tracker.py` aggregates estimated spend and GetXAPI usage. Diagnostics are written to `data/llm_metrics.jsonl` and `web/data/<date>/cost_report.json` when enabled.

Telemetry must remain prompt-free and secret-safe.

## Key paths

```text
agents/                  Pipeline agents, routing, context and reliability guards
config/                  Providers, prompts, sources and grounding data
frontend/                SvelteKit 5 application
generators/              JSON, feed and optional visual generators
scripts/                 Validation, regeneration and deployment utilities
tests/                   Mocked unit and regression tests
web/data/<date>/          Generated report artifacts
.github/workflows/        Daily generation and publishing workflow
```

## Adding a source or agent

For a source, update the appropriate config file, implement date-window behavior, expose source status, add empty/error tests, and update `docs/sources.md` plus the README source table.

For a gatherer, extend `BaseGatherer` and return `List[CollectedItem]`. For an analyzer, extend `BaseAnalyzer`, preserve item-ID coverage, and return a valid `CategoryReport`. Register new components in `MainOrchestrator` and add mocked failure-path tests.

## Publishing

`.github/workflows/daily-pipeline.yml` runs the critical mocked tests before paid calls, generates the report, applies the publish gate, and commits only validated public artifacts. Failed runs restore the last good report.

The workflow is guarded for `BlockFrame/wiredframe-radar`. Do not enable scheduled publishing in a fork without intentionally changing repository guards, secrets, signing, and output ownership.
