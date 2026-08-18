# Architecture

Wiredframe Radar is a checkpointed, multi-stage data pipeline with a static publishing layer. Collection and analysis are category-specific; topic detection and executive synthesis operate across categories only after evidence has been normalized and validated.

## System topology

```mermaid
flowchart TB
    subgraph External[External systems]
        SOURCES[RSS, web, APIs, X, GitHub]
        LLMS[OpenRouter, Gemini, NVIDIA]
        GHA[GitHub Actions]
    end

    subgraph Core[Python pipeline]
        GATHER[Gatherers]
        NORMALIZE[Normalization and deduplication]
        CATEGORY[Category analyzers]
        ORCH[Cross-category orchestrator]
        ENRICH[Link enrichment]
        QUALITY[Editorial and quality gates]
        SERIALIZE[JSON generator]
        CHECKPOINTS[(Checkpoints)]
        TELEMETRY[(Metrics and costs)]
    end

    subgraph Delivery[Delivery]
        REPORTS[(web/data)]
        FRONTEND[SvelteKit static frontend]
        MACHINE[llms.txt, ai-index.json, MCP]
        VERCEL[Vercel]
    end

    GHA --> GATHER
    SOURCES --> GATHER --> NORMALIZE --> CATEGORY
    CATEGORY <--> LLMS
    CATEGORY --> ORCH <--> LLMS
    ORCH --> ENRICH <--> LLMS
    ENRICH --> QUALITY --> SERIALIZE
    GATHER --> CHECKPOINTS
    CATEGORY --> CHECKPOINTS
    ORCH --> CHECKPOINTS
    CATEGORY --> TELEMETRY
    ORCH --> TELEMETRY
    SERIALIZE --> REPORTS --> FRONTEND --> VERCEL
    SERIALIZE --> MACHINE
```

## Processing sequence

```mermaid
sequenceDiagram
    participant W as Workflow
    participant G as Gatherers
    participant A as Analyzers
    participant O as Orchestrator
    participant V as Validator
    participant P as Publisher

    W->>G: Collect exact coverage window
    G-->>W: Items and source status
    W->>A: Filter, batch analyze, rank
    A-->>W: Category reports and evidence IDs
    W->>O: Current reports plus historical anti-repeat context
    O->>O: Detect cross-category topics
    O->>O: Generate executive summary
    O-->>W: Grounded synthesis and telemetry
    W->>V: Validate schema, coverage, quality and evidence
    alt report valid
        V->>P: Commit generated artifacts
    else report invalid
        V-->>W: Fail run
        W->>W: Restore last good report
    end
```

## Context boundary

Historical executive summaries are loaded only to prevent repetition. `agents/summary_context.py` wraps them in a closed historical section, then opens a separate current-evidence section containing current topic candidates and exact item records. Both the live orchestrator and `scripts/regenerate_summary.py` use this shared builder.

The model must return evidence IDs from current records. Validation rejects missing IDs, unknown IDs, and insufficient category coverage.

## Failure boundaries

- **Source failure:** recorded per source; a category that collected data cannot silently collapse to zero during filtering or analysis.
- **LLM failure:** caller-aware fallback chains retry from the preferred route on each new task and cool down unhealthy routes.
- **Schema failure:** deterministic fallbacks preserve eligible inputs where safe; critical synthesis fails closed.
- **Editorial failure:** unsupported topics, prohibited branding, and invalid evidence are rejected or sanitized.
- **Publish failure:** the report validator blocks commit and the workflow retains the last known-good report.

## Data contracts

`OrchestratorResult` is serialized to `web/data/<date>/summary.json`. The frontend consumes static JSON and does not need a runtime application database. Report metadata includes collection status, analysis funnels, phase status, evidence IDs, quality diagnostics, and LLM telemetry.

Provider and prompt behavior is configuration-driven through `config/providers.yaml` and `config/prompts.yaml`.
