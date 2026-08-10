"""
GitHub Trending Analyzer - Analyzes trending open-source AI/ML repositories for AI Directors.
"""

import json
import logging
import os
from datetime import datetime
from typing import List, Optional

from ..base import (
    BaseAnalyzer, CollectedItem, AnalyzedItem,
    CategoryReport, CategoryTheme,
    is_scan_first_category_summary,
)
from ..llm_client import AnthropicClient, AsyncAnthropicClient, ThinkingLevel

logger = logging.getLogger(__name__)


class GitHubTrendingAnalyzer(BaseAnalyzer):
    """Analyzes GitHub Trending repositories and generates strategic AI Director insights."""

    @property
    def category(self) -> str:
        return 'github_trending'

    async def analyze(self, items: List[CollectedItem]) -> CategoryReport:
        if not items:
            return CategoryReport(
                category=self.category,
                top_items=[],
                all_items=[],
                category_summary="No GitHub trending repositories collected today.",
                themes=[],
                cross_signals=[],
                total_collected=0,
            )

        logger.info(f"Analyzing {len(items)} GitHub trending repositories...")
        analyzed_items: List[AnalyzedItem] = []

        for item in items:
            repo_name = item.metadata.get("title") or ""
            if not repo_name and item.content.startswith("GitHub Repository: "):
                repo_name = item.content.splitlines()[0].removeprefix("GitHub Repository: ").strip()
            if not repo_name:
                repo_name = item.title.replace("[GitHub Trending] ", "").split(": ", 1)[0]
            item.title = repo_name
            stars_today = item.metadata.get("stars_today") or "0"
            lang = item.metadata.get("language") or "Code"

            # Basic deterministic scoring based on velocity and relevance
            hn_score = item.metadata.get("hn_score", 100)
            score = min(98, max(50, int(hn_score / 20) + 60))

            summary_text = (
                f"**Adoption signal:** {stars_today} stars today indicate strong developer attention. "
                f"**Enterprise lens:** evaluate the {lang} project's maturity, governance, "
                "integration surface, and operating cost before production adoption."
            )
            reasoning_text = (
                f"Ranked on current community velocity ({stars_today} stars today) and "
                "potential relevance to enterprise AI delivery."
            )

            analyzed_item = AnalyzedItem(
                item=item,
                summary=summary_text,
                importance_score=score,
                reasoning=reasoning_text,
                themes=["Open Source", "Developer Tools", lang] if lang else ["Open Source"],
            )
            analyzed_items.append(analyzed_item)

        # Sort by importance score descending
        analyzed_items.sort(key=lambda x: x.importance_score, reverse=True)
        top_items = analyzed_items[:10]

        # Generate AI Director Category Summary for GitHub Trending
        category_summary = await self._generate_executive_summary(top_items)

        # Extract themes
        themes = [
            CategoryTheme(
                name="Agentic Automation & Web Tools",
                description="Repositories focusing on autonomous agent workflows, browser automation, and MCP integrations.",
                item_count=len([i for i in analyzed_items if "agent" in i.item.content.lower() or "browser" in i.item.content.lower()]),
                example_items=[i.item.id for i in analyzed_items[:3]],
                importance=88.0,
            ),
            CategoryTheme(
                name="Local LLM & Inference Infrastructure",
                description="High-performance open-source runtimes, local model tooling, and quantization engines.",
                item_count=len([i for i in analyzed_items if "local" in i.item.content.lower() or "model" in i.item.content.lower()]),
                example_items=[i.item.id for i in analyzed_items[:3]],
                importance=85.0,
            ),
        ]

        return CategoryReport(
            category=self.category,
            top_items=top_items,
            all_items=analyzed_items,
            category_summary=category_summary,
            themes=themes,
            cross_signals=["High open-source developer velocity around agentic workflows and local tooling"],
            total_collected=len(items),
            analysis_timestamp=datetime.now().isoformat(),
        )

    async def _generate_executive_summary(self, top_items: List[AnalyzedItem]) -> str:
        """Generate a strategic briefing for GitHub Trending."""
        if not top_items:
            return "No trending GitHub repositories available for analysis."

        items_text = "\n".join(
            f"- **{item.item.title}**: {item.item.content}"
            for item in top_items
        )

        # Try loading prompt from prompts.yaml via prompt_accessor
        if self.prompt_accessor:
            try:
                prompt = self.prompt_accessor.get_analyzer_prompt(
                    self.category, 'summary',
                    {'items_text': items_text}
                )
            except Exception as e:
                logger.warning(f"Failed to load prompt from prompts.yaml for github_trending: {e}")
                prompt = None
        else:
            prompt = None

        if not prompt:
            # Fallback inline prompt (aligned with prompts.yaml style)
            prompt = f"""You are an enterprise AI strategy advisor analyzing today's breakout open-source AI repositories from GitHub Trending for C-level executives.

Top Trending Repositories Today:
{items_text}

Use exactly this compact Markdown structure:
### Executive Signal
- One decision-relevant synthesis bullet, maximum 45 words.
### Priority Developments
- 3-5 bullets, maximum 40 words each. Group related repositories and state why the pattern matters.
### Leadership Implications
- 1-2 action-oriented bullets, maximum 35 words each.

CATEGORY SUMMARY FORMATTING RULES:
- Target audience: enterprise C-level executives and AI leaders.
- Use a rigorous, decision-oriented, top-tier strategy-consulting style, but never mention a consulting firm or internal writing persona in the output.
- Every section body must use bullets. Do not write prose paragraphs.
- Keep the complete summary below 350 words.
- A bullet must synthesize a signal or implication, not merely repeat a repository description.
- Use **bold** for repository names, languages, framework names, and key metrics.
- Synthesize related repositories into themes explaining what they signal for enterprise AI adoption, developer tooling, and competitive dynamics.
- Keep sentences analytical and authoritative.
- Do NOT include markdown links or URLs. Links will be added automatically in a post-processing step."""

        try:
            if self.async_client:
                response = await self.async_client.call_with_thinking(
                    messages=[{"role": "user", "content": prompt}],
                    profile=ThinkingLevel.STANDARD,
                    # Match the dedicated Gemini quality route used by the
                    # other category-summary regeneration calls.
                    caller="analysis.github_trending_summary",
                    max_tokens=4096,
                )
                content = (response.content or "").strip()
                if response.stop_reason == "max_tokens":
                    logger.warning("GitHub Trending summary exhausted its output budget")
                elif is_scan_first_category_summary(content):
                    return content
                if content:
                    logger.warning(
                        "GitHub Trending summary failed the minimum quality check "
                        f"({len(content)} chars)"
                    )
        except Exception as e:
            logger.warning(f"Failed to generate LLM summary for GitHub trending: {e}")

        # Make the failure explicit so the publication quality gate rejects it
        # instead of silently publishing a deterministic repository list as an
        # LLM-generated executive briefing.
        return "Analysis complete. GitHub Trending summary generation failed quality checks."
