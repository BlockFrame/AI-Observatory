# Project summary

## Purpose

AI Observatory produces a daily, evidence-grounded view of the AI ecosystem. It is optimized for decision usefulness rather than raw aggregation: collection breadth is reduced into ranked category reports, cross-category themes, and an executive briefing whose claims must point to current source items.

## Current product

- Static SvelteKit observatory at `https://ai-observatory.vercel.app`
- Daily categories: AI News, Research, Social signals from X, GitHub Trending
- Machine-readable `summary.json`, `llms.txt`, `ai-index.json`, and MCP interface
- Automated generation and publishing through GitHub Actions
- Provider, token, latency, error, source, and GetXAPI telemetry

## Differentiating design decisions

1. **Evidence before prose.** Topic and executive outputs carry exact current-item IDs.
2. **History is not evidence.** Previous summaries are isolated in a closed anti-repetition section.
3. **Task-aware routing.** Paid capacity is reserved for ranking and synthesis; bulk work uses lower-cost routes with fallbacks.
4. **Deterministic safety rails.** Filtering, sanitization, scoring, and validation reduce dependence on perfect model behavior.
5. **Last-good publishing.** A failed report does not replace the most recent validated edition.

## Active inputs

- 43 AI News RSS/Atom feeds
- 18 direct web sources
- Hacker News
- Hugging Face Daily Papers and AlphaXiv Trending
- 18 research feeds, including LessWrong via GraphQL
- 171 X accounts through GetXAPI
- GitHub Trending

Bluesky, Mastodon, Reddit, YouTube, Product Hunt, Discord, and Slack are not currently collected.

## Technology

- Python 3.11 asynchronous pipeline
- OpenRouter, Google Gemini, and NVIDIA model routes
- SvelteKit 5, TypeScript, Tailwind CSS, and static generation
- GitHub Actions and Vercel
- JSON-based versioned report storage

For implementation details, see [Architecture](architecture.md), [README](README.md), and [Roadmap](TODO.md).
