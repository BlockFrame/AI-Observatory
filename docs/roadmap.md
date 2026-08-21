# Roadmap and AIDLC backlog

This document provides the public, versioned view of R[AI]DAR's product direction. The [GitHub AIDLC Project](https://github.com/users/BlockFrame/projects/2) is the operational source of truth for priority, stage, ownership, and delivery risk.

Every future capability is represented by a GitHub user story. A story must move through discovery, design, build, verification, review, release, and observation as defined in the [AI development lifecycle](ai-development-lifecycle.md). The roadmap does not authorize implementation by itself.

## Delivered foundations

- [x] Deterministic quality scores and category-level publish gates.
- [x] Separate ranking and editorial-writing routes with explicit LLM fallbacks.
- [x] Category-level LLM telemetry for model, provider, latency, tokens, retries, fallbacks, and status.
- [x] Gatherer health and source-funnel observability.
- [x] End-to-end resilience fixtures for provider failures, malformed output, empty feeds, and publish gates.
- [x] Deterministic-first link enrichment with bounded LLM fallback.
- [x] Content checksums and analysis caching for duplicated articles.
- [x] Consolidated public documentation, GitHub Wiki navigation, governance, security, and AIDLC controls.

## Active roadmap

### Reliability, cost, and observability

| User story | Priority | Risk | Current intent |
|---|---:|---:|---|
| [#17 — Reconcile OpenRouter usage with authoritative provider cost](https://github.com/BlockFrame/wiredframe-radar/issues/17) | High | Medium | Distinguish provider-reported cost from local estimates and quantify variance. |
| [#26 — Trace every LLM call across the full pipeline run](https://github.com/BlockFrame/wiredframe-radar/issues/26) | Medium | Medium | Correlate run, phase, provider attempt, fallback, latency, and cost. |
| [#27 — Evaluate Langfuse for multi-provider LLM observability](https://github.com/BlockFrame/wiredframe-radar/issues/27) | Low | Medium | Make a go/no-go decision after 3–5 representative OpenRouter runs. |
| [#28 — Add privacy-safe selective replay for failed LLM calls](https://github.com/BlockFrame/wiredframe-radar/issues/28) | Medium | High | Retain only redacted failures or explicit samples for controlled replay. |

### Coverage and collection quality

| User story | Priority | Risk | Current intent |
|---|---:|---:|---|
| [#29 — Expand and validate AI News source coverage](https://github.com/BlockFrame/wiredframe-radar/issues/29) | Medium | Low | Add authoritative feeds in small, tested batches. |
| [#30 — Expand and validate AI Research source coverage](https://github.com/BlockFrame/wiredframe-radar/issues/30) | Medium | Low | Broaden primary research coverage without treating static hubs as daily items. |
| [#31 — Expand and govern monitored X profiles](https://github.com/BlockFrame/wiredframe-radar/issues/31) | Low | Medium | Add high-signal accounts while controlling paid-query growth and rerun behavior. |
| [#35 — Implement advanced cross-source deduplication](https://github.com/BlockFrame/wiredframe-radar/issues/35) | High | High | Consolidate repeated events while preserving one-to-many provenance. |

### Intelligence products

| User story | Priority | Risk | Current intent |
|---|---:|---:|---|
| [#18 — Design the Technical Updates report section](https://github.com/BlockFrame/wiredframe-radar/issues/18) | Medium | Medium | Define the contract and delivery slices before implementation. |
| [#34 — Add a Regulatory and Ethics intelligence category](https://github.com/BlockFrame/wiredframe-radar/issues/34) | High | Medium | Separate authoritative policy intelligence from generic News. |
| [#39 — Add structured Why it matters guidance](https://github.com/BlockFrame/wiredframe-radar/issues/39) | Medium | Medium | Explain impact, urgency, and audience without duplicating or inventing facts. |
| [#40 — Group continuing stories into 7-day and 30-day timelines](https://github.com/BlockFrame/wiredframe-radar/issues/40) | Medium | Medium | Distinguish new developments from historical context. |
| [#38 — Detect and explain intelligence trends over 30 and 90 days](https://github.com/BlockFrame/wiredframe-radar/issues/38) | Medium | High | Surface sustained evidence-backed movement rather than daily noise. |
| [#42 — Expose an evidence and ranking transparency view](https://github.com/BlockFrame/wiredframe-radar/issues/42) | High | Medium | Make provenance, confidence, ranking rationale, and fallbacks inspectable. |
| [#43 — Build an AI ecosystem comparison dashboard](https://github.com/BlockFrame/wiredframe-radar/issues/43) | Medium | High | Compare models and providers using normalized, dated, primary evidence. |

### Delivery, integration, and community

| User story | Priority | Risk | Current intent |
|---|---:|---:|---|
| [#33 — Deliver high-confidence alerts with Discord support](https://github.com/BlockFrame/wiredframe-radar/issues/33) | Medium | Medium | Add selective evidence-linked notifications without coupling them to publication. |
| [#37 — Extend MCP with semantic and evidence-aware retrieval](https://github.com/BlockFrame/wiredframe-radar/issues/37) | Medium | Medium | Improve AI IDE access while retaining a local deterministic fallback. |
| [#36 — Provide a supported R[AI]DAR SDK client](https://github.com/BlockFrame/wiredframe-radar/issues/36) | Low | Low | Design a versioned read-only integration surface based on demonstrated demand. |
| [#41 — Create a persistent personalized daily digest](https://github.com/BlockFrame/wiredframe-radar/issues/41) | Low | Medium | Add a private personalized view without changing canonical public ranking. |
| [#44 — Add privacy-friendly product analytics](https://github.com/BlockFrame/wiredframe-radar/issues/44) | Low | Low | Evaluate Plausible or Umami with minimal, transparent collection. |
| [#32 — Evaluate GitHub Sponsors for project sustainability](https://github.com/BlockFrame/wiredframe-radar/issues/32) | Low | Low | Define an independence-preserving sponsorship policy after eligibility. |

## Planning rules

- The GitHub Project owns operational fields; this file owns the public strategic narrative.
- `Triage` means the problem is captured but design decisions may still be open. `Ready` means scope, acceptance criteria, dependencies, risk, and validation are sufficient to begin.
- High-risk work must be split into reviewable design and implementation increments before coding.
- Provider, collection, or notification changes must declare recurring cost and external side effects.
- Every implementation requires mocked regression coverage; routine development must not consume paid LLM or X quota.
- A merged capability is moved to **Delivered foundations** only after verification and production observation.

## Supporting contributor work

Contributor-enablement tasks remain tracked in the same AIDLC Project even when they are not product roadmap capabilities:

- [#15 — Document the source contribution and validation workflow](https://github.com/BlockFrame/wiredframe-radar/issues/15)
- [#16 — Document MCP interfaces and local usage examples](https://github.com/BlockFrame/wiredframe-radar/issues/16)
