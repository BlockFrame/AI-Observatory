"""
Cross-platform semantic deduplication.
"""

import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set, Tuple

from agents.base import CategoryReport
from agents.llm_client import ThinkingLevel

logger = logging.getLogger(__name__)

SIGNIFICANT_WORD_RE = re.compile(r"[a-zA-Z0-9]{4,}")


@dataclass
class CandidatePair:
    left_category: str
    left_index: int
    right_category: str
    right_index: int


class SemanticDeduplicator:
    async def _llm_same_event(self, async_client, title_a: str, title_b: str) -> bool:
        if async_client is None:
            return False
        prompt = (
            "Are these two items about the same event? Reply only YES or NO.\n"
            f"Item A: {title_a}\n"
            f"Item B: {title_b}"
        )
        try:
            response = await async_client.call_with_thinking(
                messages=[{"role": "user", "content": prompt}],
                profile=ThinkingLevel.QUICK,
                caller="filters.semantic_dedup",
                max_tokens=256,
            )
        except Exception:
            return False
        return (response.content or "").strip().upper().startswith("YES")

    @staticmethod
    def _has_common_significant_words(title_a: str, title_b: str) -> bool:
        words_a = set(SIGNIFICANT_WORD_RE.findall(title_a.lower()))
        words_b = set(SIGNIFICANT_WORD_RE.findall(title_b.lower()))
        return bool(words_a & words_b)

    @staticmethod
    def _title_similarity(title_a: str, title_b: str) -> float:
        return SequenceMatcher(None, title_a.lower(), title_b.lower()).ratio()

    async def deduplicate_reports(
        self,
        category_reports: Dict[str, CategoryReport],
        async_client=None,
    ) -> Dict[str, CategoryReport]:
        target_categories = [c for c in ("news", "social", "reddit") if c in category_reports]
        if len(target_categories) < 2:
            return category_reports

        drop_ids: Dict[str, Set[str]] = {category: set() for category in target_categories}
        for i, left_category in enumerate(target_categories):
            left_report = category_reports[left_category]
            for right_category in target_categories[i + 1 :]:
                right_report = category_reports[right_category]
                for left_item in left_report.all_items:
                    for right_item in right_report.all_items:
                        if left_item.item.url == right_item.item.url:
                            continue
                        if not self._has_common_significant_words(left_item.item.title, right_item.item.title):
                            continue
                        similarity = self._title_similarity(left_item.item.title, right_item.item.title)
                        if similarity <= 0.30:
                            continue
                        same_event = similarity > 0.82
                        if not same_event:
                            same_event = await self._llm_same_event(
                                async_client, left_item.item.title, right_item.item.title
                            )
                        if not same_event:
                            continue
                        winner = left_item if left_item.importance_score >= right_item.importance_score else right_item
                        loser = right_item if winner is left_item else left_item
                        loser_category = right_category if winner is left_item else left_category
                        winner_sources = winner.item.metadata.setdefault("related_sources", [])
                        winner_sources.append(
                            {
                                "source": loser.item.source,
                                "url": loser.item.url,
                            }
                        )
                        drop_ids[loser_category].add(loser.item.id)

        for category in target_categories:
            report = category_reports[category]
            if not drop_ids[category]:
                continue
            report.all_items = [item for item in report.all_items if item.item.id not in drop_ids[category]]
            report.top_items = [item for item in report.top_items if item.item.id not in drop_ids[category]]
            logger.info(f"Semantic dedup removed {len(drop_ids[category])} {category} duplicates")
        return category_reports
