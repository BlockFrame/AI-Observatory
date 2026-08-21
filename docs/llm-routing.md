# LLM routing

R[AI]DAR routes each call by caller and reasoning profile. `config/providers.yaml` is the executable source of truth; this guide explains its current intent and the controls that must remain true when routes change.

## Current route matrix

| Workload and callers | Primary | Ordered fallback | Notes |
|---|---|---|---|
| Bulk per-item analysis and editorial utilities using `QUICK`, `STANDARD`, or `DEEP` | OpenRouter `minimax/minimax-m3` | Gemini 3.5 Flash Lite → Gemini 3.1 Flash Lite | Two concurrent paid requests; high-volume route |
| `news_analyzer.small_batch`, `*_analyzer.reduce_rank`, `analysis.*_summary`, `orchestrator.topics`, `orchestrator.summary` | OpenRouter `minimax/minimax-m3` | Gemini 3.6 Flash → NVIDIA GLM 5.2 → Gemini 3.5 Flash → Gemini 3.5 Flash Lite | Quality route for ranking and synthesis |
| `link_enricher_paid.*` unresolved evidence blocks | OpenRouter `minimax/minimax-m3` | None | Isolated semantic fallback after deterministic matching; cannot spill into unrelated routes |

Every new task starts from its preferred eligible route. A failure can advance within that task's chain, but a previous transient failure does not permanently force later tasks onto a weaker model. Routes may temporarily cool down or become unavailable when quota, model availability, or repeated errors require it.

## Gemini quota boundaries

The configured quality chain reserves scarce quota by caller:

| Model | RPM | TPM | RPD | Role |
|---|---:|---:|---:|---|
| Gemini 3.6 Flash | 15 | 250,000 | 20 | First quality fallback |
| Gemini 3.5 Flash | 5 | 250,000 | 20 | Later quality fallback |
| Gemini 3.5 Flash Lite | 15 | 250,000 | 500 | Bulk and final quality fallback |
| Gemini 3.1 Flash Lite | 15 | 250,000 | 500 | Final bulk fallback |

These values describe local routing limits, not a promise from Google. Provider account limits remain authoritative and may change independently.

## Pricing preflight

The workflow checks the OpenRouter catalog price for `minimax/minimax-m3` before dependency installation, collection, GetXAPI usage, or LLM calls. The run stops if input or output price exceeds the configured ceilings, currently exposed as `OPENROUTER_COMPLEX_MAX_INPUT_PER_MTOK` and `OPENROUTER_COMPLEX_MAX_OUTPUT_PER_MTOK`.

The request path repeats the price constraint. Raising a ceiling is an explicit cost-governance decision: compare the provider price, expected token volume, recent `cost_report.json`, and fallback capacity before changing it.

## Task behavior

- Category analyzers filter, batch-analyze, reduce/rank, and synthesize category briefs.
- Topic Detection and Executive Summary are critical synthesis tasks and must return valid current evidence.
- Link enrichment is deterministic first. MiniMax sees only unresolved evidence blocks and the allowed evidence catalog; its failure cannot invalidate an otherwise grounded report.
- Historical summaries are anti-repetition context only. They are isolated from the current evidence section by `agents/summary_context.py`.
- Structured-output parsing and deterministic validation remain mandatory even for paid frontier models. Payment improves capability and capacity; it does not guarantee schema validity, evidence fidelity, or provider availability.

## Cost semantics

`cost_report.json` currently reports token-based local estimates grouped by component and route, plus separately estimated external-API spend. It is useful for run-to-run comparison but is not yet reconciled with authoritative OpenRouter billing. Provider-cost reconciliation is tracked in [Issue #17](https://github.com/BlockFrame/wiredframe-radar/issues/17).

Tests must mock provider responses and must not consume paid quota. Route changes require fixtures for success, invalid output, timeout, quota exhaustion, fallback, and price-preflight failure.

See [Telemetry](telemetry.md) for field interpretation and [Operations](operations.md) for incident response.

[Back to documentation index](README.md)
