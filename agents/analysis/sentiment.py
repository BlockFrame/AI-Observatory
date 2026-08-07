"""
Sentiment tagging for analyzed items.
"""

import asyncio
import os
import re
from typing import Dict

from agents.base import CategoryReport

VALID_SENTIMENTS = {"positive", "negative", "controversial", "concerned", "neutral"}

SENTIMENT_PATTERNS = {
    "controversial": ("controvers", "backlash", "debate", "dispute", "criticized"),
    "concerned": ("risk", "safety", "warning", "concern", "threat", "lawsuit", "ban"),
    "negative": ("fail", "decline", "loss", "outage", "breach", "layoff"),
    "positive": ("breakthrough", "improve", "growth", "launch", "release", "milestone"),
}


def _deterministic_sentiment(title: str, summary: str) -> str:
    """Cheap default sentiment signal for free-tier runs."""
    text = re.sub(r"\s+", " ", f"{title} {summary}").lower()
    for label, patterns in SENTIMENT_PATTERNS.items():
        if any(re.search(rf"\b{re.escape(pattern)}\w*\b", text) for pattern in patterns):
            return label
    return "neutral"


async def _score_item(async_client, title: str, summary: str) -> str:
    if async_client is None:
        return "neutral"
    prompt = (
        "Classify sentiment as one of: positive, negative, controversial, concerned, neutral.\n"
        "Return only one label.\n"
        f"Title: {title}\nSummary: {summary}"
    )
    try:
        response = await async_client.call(
            messages=[{"role": "user", "content": prompt}],
            caller="analysis.sentiment",
            max_tokens=512,
        )
    except Exception:
        return "neutral"
    words = (response.content or "").strip().lower().split()
    label = words[0] if words else "neutral"
    return label if label in VALID_SENTIMENTS else "neutral"


async def classify_sentiments(category_reports: Dict[str, CategoryReport], async_client=None) -> None:
    use_llm = os.getenv("SENTIMENT_USE_LLM", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }
    semaphore = asyncio.Semaphore(1)
    tasks = []
    for report in category_reports.values():
        for item in report.all_items:
            tasks.append(item)

    async def classify(item):
        if use_llm and async_client is not None:
            async with semaphore:
                sentiment = await _score_item(async_client, item.item.title, item.summary)
        else:
            sentiment = _deterministic_sentiment(item.item.title, item.summary)
        item.sentiment = sentiment
        item.item.metadata["sentiment"] = sentiment

    await asyncio.gather(*[classify(item) for item in tasks])


def append_sentiment_section(executive_summary: str, category_reports: Dict[str, CategoryReport]) -> str:
    flagged = []
    for report in category_reports.values():
        for item in report.top_items[:5]:
            if item.sentiment in {"controversial", "concerned"}:
                flagged.append(f"- **{item.item.title}** ({item.sentiment})")
    if not flagged:
        return executive_summary
    section = "\n\n#### Sentiment & Controversy\n" + "\n".join(flagged[:8])
    return (executive_summary or "").rstrip() + section
