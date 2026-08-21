# Project summary

## Purpose

R[AI]DAR produces a daily, evidence-grounded view of the AI ecosystem. It is optimized for decision usefulness rather than raw aggregation: collection breadth is reduced into ranked category reports, cross-category themes, and an executive briefing whose claims must point to current source items.

## Current product

- Static SvelteKit site at `https://radar.wiredframe.xyz`
- Daily categories: AI News, Research, Social signals from X, GitHub Trending
- Searchable directories for AI models, tools, and influential people
- Machine-readable `summary.json`, `llms.txt`, `ai-index.json`, and MCP interface
- Automated generation and publishing through GitHub Actions
- Provider, token, latency, error, source, and GetXAPI telemetry

## Differentiating design decisions

1. **Evidence before prose.** Topic and executive outputs carry exact current-item IDs.
2. **History is not evidence.** Previous summaries are isolated in a closed anti-repetition section.
3. **Task-aware routing.** Price-guarded MiniMax M3 is the primary route for bulk analysis and critical synthesis; caller-specific Gemini and NVIDIA chains provide fallback capacity.
4. **Deterministic safety rails.** Filtering, sanitization, scoring, and validation reduce dependence on perfect model behavior.
5. **Last-good publishing.** A failed report does not replace the most recent validated edition.

## Active inputs

- 43 AI News RSS/Atom feeds
- 13 direct web sources
- Hacker News
- Hugging Face Daily Papers and AlphaXiv Trending
- 20 configured Research feed routes, including LessWrong via GraphQL
- 4 deterministic, date-validated Research hubs
- 170 X accounts through GetXAPI
- GitHub Trending

## Technology

- Python 3.11 asynchronous pipeline
- OpenRouter, Google Gemini, and NVIDIA model routes
- SvelteKit 5, TypeScript, Tailwind CSS, and static generation
- GitHub Actions and Vercel
- JSON-based versioned report storage

For implementation details, see the [architecture](architecture.md), the [project README](../README.md), and the [roadmap](roadmap.md).
