"""
Natural-language interest filter scored by LLM.
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional

from agents.base import CollectedItem
from agents.llm_client import ThinkingLevel

logger = logging.getLogger(__name__)

FALLBACK_KEYWORDS = (
    "ai",
    "artificial intelligence",
    "llm",
    "model",
    "agent",
    "mcp",
    "rag",
    "anthropic",
    "openai",
    "gemini",
    "gpt",
)


class AIInterestFilter:
    def __init__(self, interests_path: Path, threshold: float = 4.0):
        self.interests_path = interests_path
        self.threshold = threshold
        self.interests_text = interests_path.read_text(encoding="utf-8") if interests_path.exists() else ""

    async def _score_item(self, async_client, item: CollectedItem) -> Optional[float]:
        prompt = (
            f"Given these interests:\n{self.interests_text}\n\n"
            f"Rate this title from 1 to 10 and return only the number:\n{item.title}"
        )
        try:
            response = await async_client.call_with_thinking(
                messages=[{"role": "user", "content": prompt}],
                profile=ThinkingLevel.QUICK,
                caller="filters.ai_interest",
                max_tokens=32,
            )
        except Exception as exc:
            logger.warning(f"AI interest scoring failed for {item.id}: {exc}")
            return None
        raw = (response.content or "").strip()
        cleaned = "".join(ch for ch in raw if ch.isdigit() or ch == ".")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _fallback_match(item: CollectedItem) -> bool:
        text = f"{item.title} {item.content}".lower()
        return any(keyword in text for keyword in FALLBACK_KEYWORDS)

    async def filter_items(self, items: List[CollectedItem], async_client) -> List[CollectedItem]:
        if not items:
            return []
        if not self.interests_text.strip() or async_client is None:
            return [item for item in items if self._fallback_match(item)]

        semaphore = asyncio.Semaphore(8)

        async def score(item: CollectedItem):
            async with semaphore:
                value = await self._score_item(async_client, item)
                if value is None:
                    return item if self._fallback_match(item) else None
                item.metadata["interest_score"] = value
                return item if value >= self.threshold else None

        kept = await asyncio.gather(*[score(item) for item in items])
        return [item for item in kept if item is not None]
