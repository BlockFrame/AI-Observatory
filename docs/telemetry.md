# Telemetry reference

R[AI]DAR stores run telemetry with each date-addressed report so an operator can explain what was collected, selected, generated, retried, rejected, and paid for without relying only on transient workflow logs.

## Report-level telemetry

| Field | Meaning | Operator question |
|---|---|---|
| `collection_status` | Category/source completion, item counts, and errors | Did each collector finish and return usable data? |
| `source_funnel` | Counts through source collection and eligibility stages | Did a source produce candidates, and where were they removed? |
| `source_coverage_alerts` | Deterministic warnings about potentially over-constrained coverage | Are framework or source signals being systematically excluded? |
| `analysis_funnel` | Counts entering and surviving analysis/ranking | Did filtering or model analysis collapse a populated category? |
| `phase_status` | Status, duration, detail, and errors for orchestrator phases | What was the first degraded or failed phase? |
| `generation_quality` | Topic/summary result and critical fallback indicator | Did critical synthesis complete normally? |
| `quality_score` | Deterministic report/category components and pass decision | Was the artifact publishable, and why? |
| `llm_telemetry` | Calls, attempts, retries, latency, tokens, routes, and errors | Which model handled each workload and at what reliability? |

`quality_score.version` versions the scoring formula, not the complete report schema.

## Cost report

`cost_report.json` contains:

- `api_calls`, timing, failures, and aggregate token fields;
- `cost`, `cost_by_component`, and `cost_by_provider` based on the local pricing table;
- `external_apis`, including GetXAPI call count, item count, and estimated spend;
- the detailed `llm_telemetry` snapshot used to calculate provider and caller status.

Current LLM costs are estimates and can differ from the provider dashboard because reasoning, cache, rounding, or promotional billing fields may not be fully represented. Do not label them authoritative until [Issue #17](https://github.com/BlockFrame/wiredframe-radar/issues/17) is complete. GetXAPI is reported separately and must not be added to LLM cost without explicitly naming the combined total.

## LLM status and error rate

For a scope, `successful_calls` counts completed logical calls, `provider_attempts` includes retries/fallback attempts, and `failed_attempts` counts failed attempts. `error_rate` therefore measures attempt reliability, not the fraction of final tasks with no output. A non-zero attempt error rate can coexist with successful final output when a retry or fallback recovers.

Inspect telemetry in this order:

1. overall status and failed attempts;
2. pipeline scope or category;
3. caller/component;
4. route/model and retry reason;
5. token, latency, and cost deltas against recent successful runs.

## Endpoint status

`endpoint_status.json` is the detailed collection-side companion to `collection_status`. Empty results must be distinguishable from transport failure, malformed response, date-window exclusion, and disabled configuration. Source-health interpretation and status vocabulary are documented in the [Source handbook](sources.md).

## Retention and privacy

Generated reports and aggregate telemetry are versioned in Git. Secrets, authorization headers, full provider payloads, proxy credentials, and private vulnerability details must never be written to telemetry. Workflow diagnostic artifacts may contain larger checkpoints; handle and retain them according to repository access and incident needs.

[Back to documentation index](README.md)
