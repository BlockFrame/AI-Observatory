"""
GitHub Trending Analyzer - Analyzes trending open-source AI/ML repositories for AI Directors.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import List, Optional

from ..base import (
    BaseAnalyzer, CollectedItem, AnalyzedItem,
    CategoryReport, CategoryTheme,
    is_scan_first_category_summary,
)
from ..llm_client import AnthropicClient, AsyncAnthropicClient, ThinkingLevel

logger = logging.getLogger(__name__)


def extract_repository_description(content: str, metadata: dict) -> str:
    """Return the repository description from structured or legacy input."""
    description = str(metadata.get("description") or "").strip()
    if description:
        return re.sub(r"\s+", " ", description)
    match = re.search(
        r"^Description:\s*(.*?)(?=^Language:|^Stars Today:|\Z)",
        str(content or ""),
        flags=re.MULTILINE | re.DOTALL,
    )
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def build_repository_summary(
    repo_name: str,
    description: str,
    stars_today: str,
    language: str,
) -> str:
    """Build a concise, repository-specific adoption and value assessment."""
    star_digits = re.sub(r"[^0-9]", "", str(stars_today or ""))
    star_count = int(star_digits) if star_digits else 0
    if star_count >= 1000:
        momentum = "breakout developer momentum"
    elif star_count >= 250:
        momentum = "strong developer attention"
    elif star_count >= 50:
        momentum = "emerging developer interest"
    else:
        momentum = "early developer interest"

    normalized = re.sub(r"\s+", " ", str(description or "")).strip(" .")
    signal = str(stars_today or "0")
    corpus = f"{repo_name} {normalized}".lower()

    if any(term in corpus for term in ("cybersecurity", "penetration", "vulnerab", "mitre", "nist")):
        lens = (
            "Its security automation can make testing and control mapping more repeatable "
            "across AI workflows, provided teams validate coverage and benchmark quality."
        )
    elif any(term in corpus for term in ("memory", "context database", "knowledge rag", "retrieval")):
        lens = (
            "It consolidates agent context, memory, and retrieval into a shared layer, "
            "which can reduce duplicated infrastructure in multi-agent systems."
        )
    elif any(term in corpus for term in ("multi-agent", "agent harness", "orchestrat", "agent framework")):
        lens = (
            "It targets the coordination layer around agents, making it relevant for teams "
            "that need repeatable execution, isolation, and workflow control."
        )
    elif any(term in corpus for term in ("skill", "agents directory", "agent capability")):
        lens = (
            "It packages reusable agent capabilities instead of another model layer, "
            "signaling a shift toward portable, governed workflow components."
        )
    elif any(term in corpus for term in ("video", "image", "media", "content generation")):
        lens = (
            "It compresses AI-assisted media production into a repeatable workflow, "
            "making content throughput and human review the key adoption questions."
        )
    elif any(term in corpus for term in ("inference", "local model", "llm", "moe", "model serving")):
        lens = (
            "It can lower the friction of deploying or operating models, so its value depends "
            "on measured gains in latency, cost, and hardware efficiency."
        )
    elif "download manager" in corpus:
        lens = (
            "Its relevance to enterprise AI is indirect; the momentum is more useful as a "
            "signal of demand for polished developer and data-transfer tooling."
        )
    elif normalized:
        excerpt = normalized if len(normalized) <= 180 else normalized[:177].rsplit(" ", 1)[0] + "…"
        lens = (
            f"It is attracting attention for {excerpt[0].lower() + excerpt[1:]}; teams should "
            "verify that this capability removes a concrete workflow bottleneck before adoption."
        )
    else:
        language_label = language or "software"
        lens = (
            f"The missing project description leaves its enterprise value unverified; treat the "
            f"{language_label} repository as a discovery signal until its use case and operating model are clear."
        )

    return (
        f"**Adoption signal:** {signal} stars today indicate {momentum}. "
        f"**Why it matters:** {lens}"
    )


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
            description = extract_repository_description(item.content, item.metadata)

            # Basic deterministic scoring based on velocity and relevance
            hn_score = item.metadata.get("hn_score", 100)
            score = min(98, max(50, int(hn_score / 20) + 60))

            summary_text = build_repository_summary(
                repo_name,
                description,
                stars_today,
                lang,
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
        category_summary, category_summary_evidence = await self._generate_executive_summary(top_items)

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
            category_summary_evidence=category_summary_evidence,
            analysis_timestamp=datetime.now().isoformat(),
        )

    async def _generate_executive_summary(self, top_items: List[AnalyzedItem]) -> tuple:
        """Generate a strategic briefing for GitHub Trending."""
        if not top_items:
            return "No trending GitHub repositories available for analysis.", []

        items_text = "\n".join(
            f"- [{item.item.id}] **{item.item.title}**: {item.item.content}"
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
- Do NOT include markdown links or URLs. Links will be added automatically in a post-processing step.
- Return JSON only: {{"category_summary": "complete Markdown summary", "category_summary_evidence": [["id for bullet 1"], ["id 1 for bullet 2", "id 2 for bullet 2"]]}}.
- `category_summary_evidence` must contain one ordered array per bullet, with 1-3 exact repository IDs."""

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
                result = self._parse_json_response(response.content or "")
                content = str(result.get("category_summary") or "").strip()
                evidence = self._validated_summary_evidence(
                    content,
                    result.get("category_summary_evidence", []),
                    {item.item.id for item in top_items},
                )
                if response.stop_reason == "max_tokens":
                    logger.warning("GitHub Trending summary exhausted its output budget")
                elif is_scan_first_category_summary(content):
                    return content, evidence
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
        return "Analysis complete. GitHub Trending summary generation failed quality checks.", []
