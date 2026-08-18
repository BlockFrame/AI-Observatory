# Active source inventory

This document describes sources that are wired into the current pipeline. The files under `config/` remain authoritative; update this page whenever a source class is added or removed.

## AI News

- `config/rss_feeds.txt`: 43 RSS/Atom feeds from AI labs, technology publications, engineering blogs, policy sources, and industry analysts. Active additions include Hugging Face Blog, OECD.AI, Databricks, EU Digital Strategy, EDPB, AI Laws by State, and AI Law Tracker. Broad EU/EDPB feeds are narrowed to AI-policy entries; Databricks is narrowed to AI/ML/model/agent posts; AI Law Tracker retains only news and the weekly digest.
- `config/web_scraper_sources.txt`: 13 direct web pages used where no reliable feed is available. Alongside Anthropic, Cohere, Lovable, CopilotKit, Microsoft Copilot, ElevenLabs, Aleph Alpha, and Artificial Analysis, News now includes Kimi, NIST CAISI, The Batch, MiniMax News, and Z.ai's official dated release stream. The five new routes use deterministic, exact-date extraction and consume no LLM calls; MiniMax uses the public structured endpoint behind its official News index. Z.ai's `/blog` has no discoverable index/feed, so the official release page is used for reliable daily discovery.
- Hacker News: current stories collected through the Algolia API and filtered for AI relevance.
- Links from X: `LinkFollower` expands `t.co` redirects and collects qualifying linked articles.

News filtering is deterministic-first. If the LLM relevance filter returns invalid JSON or violates its schema, the pipeline retains the keyword-filtered candidates instead of zeroing the category.

## Research

- Hugging Face Daily Papers for date-addressable curated papers.
- AlphaXiv Trending for recent rolling-window signals.
- `config/research_feeds.txt`: 20 configured routes: 19 research/technical feeds plus the LessWrong GraphQL marker. They include the research-tagged subset of OpenAI's canonical feed and Meta's official AI Research engineering feed.
- `config/research_web_sources.txt`: 4 deterministic, date-validated hubs: Anthropic Research, Anthropic Economic Futures, Arena Research, and Epoch AI. These collectors make no LLM calls and discard undated entries. Kimi, OECD.AI, and NIST CAISI are intentionally classified as News.
- `config/research_reference_sources.txt`: authoritative non-daily hubs for Meta AI Research, Microsoft AIEI, OECD.AI, Stanford HAI AI Index, EU AI Office, the EC AI Act, GovAI, AI Laws by State, and AI Law Tracker. These pages ground source coverage but are not emitted as fresh daily items merely because a static page changed.
- LessWrong through its GraphQL endpoint for date-range queries. The LessWrong feed entry in `research_feeds.txt` selects this special route; collection is not performed through ordinary RSS.

AlphaXiv cannot provide arbitrary historical snapshots beyond its supported ranking windows. Hugging Face remains the primary source for older backfills.

## Social

- `config/twitter_accounts.txt`: 170 X accounts. `@NVIDIAAI` is retained for model and AI releases; the broader corporate `@nvidia` account is excluded to reduce promotional and duplicate coverage.
- GetXAPI is the active provider.
- Accounts are grouped into chunks of at most 20 per paid query.
- Calls, tweets returned, estimated cost, balance probes, and empty responses are logged.

## GitHub Trending

GitHub Trending repositories are collected and analyzed as their own category. They are not folded into generic News.

## Not active

The current pipeline does not collect Bluesky, Mastodon, Reddit, YouTube, Product Hunt, Discord, or Slack. Do not describe these as supported sources until a gatherer is implemented, tested, configured, and included in the orchestrator.

## Adding or changing a source

1. Update the appropriate file in `config/`.
2. Verify the source supports the report’s exact coverage window.
3. Add mocked collection and empty-response tests.
4. Confirm deduplication and category assignment.
5. Update this inventory and the source table in `README.md`.
6. Run the report validator before publishing generated output.
