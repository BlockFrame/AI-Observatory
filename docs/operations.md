# Operations runbook

This runbook covers the normal daily check and the first response to failed, stale, or partial R[AI]DAR publications. The [deployment guide](deployment.md) remains canonical for platform configuration.

## Daily health check

1. Confirm the nominal **Daily Pipeline** run performed work rather than exiting through the daylight-saving schedule gate.
2. Confirm the workflow published `web/data/<report-date>/summary.json` to `main`.
3. Check that the Vercel production deployment for that commit completed successfully.
4. Open the live briefing and verify its report date, four category counts, top topics, and executive summary.
5. Review warnings in `endpoint_status.json`, source-health telemetry, and the cost report when the run was partial or materially more expensive than normal.

## Failure triage

Start from the first failing phase, not the last generic job error.

| Failure area | First evidence to inspect | Safe first action |
|---|---|---|
| Pricing preflight | `Verify paid model promotional pricing` | Update the accepted ceiling only after reviewing the current OpenRouter price and expected spend. |
| Collection | gathering logs, `endpoint_status.json`, gathering checkpoint | Repair or rerun only failed categories; preserve successful Social/X collection. |
| LLM analysis | caller, route, status, latency and token telemetry | Identify whether the route is unavailable, cooling down, quota-exhausted, or returning invalid output. |
| Topic or executive synthesis | Phase 3/4 status and evidence diagnostics | Rerun from the latest valid checkpoint after the provider issue is understood. |
| Link enrichment | enrichment logs and unresolved evidence blocks | Do not discard a valid report solely because links are incomplete; enrichment is best effort. |
| Publish gate | validator failures and uploaded candidate `summary.json` | Fix the failed contract or rerun; never weaken the gate merely to publish. |
| Vercel | deployment status and build logs | Fix the frontend/build problem or promote a known-good deployment; report data remains versioned in Git. |

## Rerun and checkpoint policy

- Keep the original target date when recovering a failed run. A GitHub rerun resolves the report date from the original workflow creation time.
- The gathering cache is keyed by report date and source configuration. Reusing it avoids paying GetXAPI again after successful X collection.
- `--resume` auto-detects the latest valid checkpoint. Use `--resume-from` only when the phase boundary and downstream effects are understood.
- Selective checkpoint repair recollects failed categories while retaining successful ones.
- Do not launch another run while one is queued or in progress. The watchdog applies the same guard.

Manual local recovery commands:

```bash
python run_pipeline.py --resume
python run_pipeline.py --resume-from 4.5
python scripts/validate_report.py --web-dir ./web --date YYYY-MM-DD
```

## Publication safety

Topic Detection and Executive Summary are critical phases and must contain valid model-generated, current-evidence output. The publish validator also checks:

- substantive category summaries and executive copy;
- a maximum 20% analysis fallback rate for sufficiently populated categories;
- no category wipeout after collection;
- current evidence IDs and cross-category topic support;
- report quality of at least 70/100 and category quality of at least 55/100;
- absence of leaked machine IDs, internal style references, and malformed links.

Missing enrichment links alone are non-fatal. If validation fails, generated paths are discarded and the previous published report remains live.

## Diagnostics and escalation

The workflow uploads `pipeline-diagnostics` even when publication fails. It may contain LLM metrics, the gathering checkpoint, candidate summaries, endpoint status, and cost reports.

Create or update an Issue with:

- workflow and job URLs;
- target report date and affected phase;
- user-visible impact;
- provider, source, or deployment evidence;
- whether paid collection already completed;
- proposed recovery and regression test.

Suspected credential exposure or security vulnerabilities must use [private vulnerability reporting](../.github/SECURITY.md), never a public operational Issue.

## Recovery completion

A recovery is complete only when the report exists on `origin/main`, Vercel has deployed that commit, the production validator passes, and the live page displays the intended report date. Link the successful run or pull request in the incident before closing it.

[Back to documentation index](README.md)
