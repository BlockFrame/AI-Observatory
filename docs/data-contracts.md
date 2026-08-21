# Data contracts

R[AI]DAR publishes immutable, date-addressed JSON artifacts under `web/data/<YYYY-MM-DD>/`. The files are the interface between the Python pipeline, the static frontend, discovery surfaces, and local MCP clients. Producers must preserve current evidence IDs; consumers must tolerate additive fields.

## Artifact set

| Artifact | Purpose | Stability |
|---|---|---|
| `summary.json` | Executive briefing, top topics, category previews, evidence, quality, and operational telemetry | Public primary contract |
| `news.json`, `research.json`, `social.json`, `github_trending.json` | Complete category inventory and category summary | Public category contracts |
| `cost_report.json` | Token, call, duration, estimated LLM cost, and external-API usage | Operational contract |
| `endpoint_status.json` | Per-endpoint collection outcome and diagnostics | Operational contract |
| `digest.md` | Human-readable generated briefing | Derived output |
| `web/data/index.json` | Available report dates and headline metadata | Public discovery contract |

Pipeline checkpoints under `data/checkpoints/<date>/` are recovery artifacts, not public API contracts. Their shape may evolve with the implementation.

## `summary.json`

Required identity and coverage fields are `date`, `coverage_date`, `coverage_start`, `coverage_end`, `generated_at`, `total_items_collected`, and `total_items_analyzed`. `date` addresses the publication; the coverage fields describe the actual collection window and must be used when evaluating freshness.

The main content fields are:

- `executive_summary`, `executive_summary_html`, `executive_summary_evidence`, and `executive_evidence_items`;
- `top_topics`, where each topic carries a name, concise description, business implication, representative items, category breakdown, importance, and trend velocity;
- `categories`, keyed by `news`, `research`, `social`, and `github_trending`;
- `hero_image_url`, which may be `null` when image generation is disabled.

Each category contains `count`, `current_item_ids`, `category_summary`, `category_summary_html`, `category_summary_evidence`, `themes`, `top_items`, `analysis_quality`, and category-level `llm_telemetry`. `summary.json` intentionally embeds only the top ten items per category; the category file contains the complete list.

## Item and evidence identity

Every current item has a stable run-local `id`, canonical `url`, `title`, `source`, `source_type`, publication timestamp when available, normalized content, summary, analysis fields, and metadata. Evidence arrays contain current item IDs, not free-form citations.

The following invariants are publish-critical:

1. evidence IDs must resolve to an item collected for the current coverage window;
2. executive and category claims cannot rely on historical context as current evidence;
3. a cross-category topic must be supported by current items from at least two non-empty categories;
4. machine IDs may exist in JSON evidence fields but must not leak into rendered prose;
5. missing link markup is non-fatal, while unknown or fabricated evidence is invalid.

## Category files

Each category file contains `category`, `date`, `category_summary`, `category_summary_html`, `category_summary_evidence`, `themes`, `total_items`, and `items`. These files power full-list views; consumers must not infer the complete category inventory from `summary.json.top_items`.

## Compatibility and versioning

The current top-level report contract is not yet explicitly versioned. `quality_score.version` versions only the scoring algorithm and must not be interpreted as a report-schema version.

Until a top-level `schema_version` is introduced:

- producers may add optional fields without a migration;
- renamed, removed, or type-changed fields require a design specification, consumer migration, fixtures for old and new shapes, and release notes;
- consumers must use defensive defaults for optional fields and ignore unknown fields;
- historical date directories remain immutable except for a documented correction;
- contract changes must update this guide, frontend types/readers, MCP behavior, validation, and mocked tests in the same pull request.

The migration is tracked in [Issue #48](https://github.com/BlockFrame/wiredframe-radar/issues/48), so documentation does not imply a runtime guarantee that does not yet exist.

## Validation boundary

`scripts/validate_report.py` and deterministic quality scoring enforce structure, current-evidence coverage, category preservation, editorial safety, and minimum quality. Current thresholds are 70/100 for the report and 55/100 per category. Link enrichment is best effort and does not independently block publication.

See [Architecture](architecture.md) for production flow and [Telemetry](telemetry.md) for operational fields.

[Back to documentation index](README.md)
