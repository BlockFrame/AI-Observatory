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
    CategoryReport, CategoryTheme
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
            repo_name = item.metadata.get("title") or item.title.replace("[GitHub Trending] ", "")
            stars_today = item.metadata.get("stars_today") or "0"
            lang = item.metadata.get("language") or "Code"
            desc = item.content or item.title

            # Basic deterministic scoring based on velocity and relevance
            hn_score = item.metadata.get("hn_score", 100)
            score = min(98, max(50, int(hn_score / 20) + 60))

            summary_text = f"Trending open-source {lang} repository ({stars_today} stars today): {desc}"
            reasoning_text = f"High community velocity on GitHub Trending ({stars_today} stars today)."

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
        """Generate strategic QuantumBlack briefing for GitHub Trending."""
        if not top_items:
            return "No trending GitHub repositories available for analysis."

        items_text = "\n".join(
            f"- **{item.item.title.replace('[GitHub Trending] ', '')}**: {item.item.content}"
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
            prompt = f"""You are a Senior Partner at QuantumBlack, AI by McKinsey, analyzing today's breakout open-source AI repositories from GitHub Trending for enterprise C-level executives.

Top Trending Repositories Today:
{items_text}

Write a cohesive, narrative-driven executive summary (1-2 flowing paragraphs) that synthesizes the most strategically significant open-source trends visible in today's GitHub Trending data.

CATEGORY SUMMARY FORMATTING RULES:
- Target audience: Senior Partner at QuantumBlack, AI by McKinsey.
- You may use bullet points if they improve readability. However, a bullet point MUST NOT be just a simple link or a single repository name. Each bullet point must be a rich, fully developed executive insight synthesizing the trend.
- Use **bold** for repository names, languages, framework names, and key metrics.
- Synthesize related repositories into themes explaining what they signal for enterprise AI adoption, developer tooling, and competitive dynamics.
- Keep sentences analytical and authoritative.
- Do NOT include markdown links or URLs. Links will be added automatically in a post-processing step."""

        try:
            if self.async_client:
                response = await self.async_client.call_with_thinking(
                    messages=[{"role": "user", "content": prompt}],
                    profile=ThinkingLevel.STANDARD,
                    caller="analysis.github_trending",
                    max_tokens=800,
                )
                return response.content.strip()
        except Exception as e:
            logger.warning(f"Failed to generate LLM summary for GitHub trending: {e}")

        # Deterministic fallback summary
        repo_highlights = [f"- **{i.item.title.replace('[GitHub Trending] ', '')}**: {i.summary}" for i in top_items[:5]]
        return (
            "**GitHub Trending Executive Insights:** Today's open-source developer landscape shows strong momentum "
            "around agentic automation frameworks, local model execution, and specialized developer tooling.\n\n"
            + "\n".join(repo_highlights)
        )
