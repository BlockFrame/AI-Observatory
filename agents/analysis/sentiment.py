"""
Sentiment tagging for analyzed items.
"""

import asyncio
from typing import Dict

from agents.base import CategoryReport
from agents.llm_client import ThinkingLevel

VALID_SENTIMENTS = {"positive", "negative", "controversial", "concerned", "neutral"}


async def _score_item(async_client, title: str, summary: str) -> str:
    if async_client is None:
        return "neutral"
    prompt = (
        "Classify sentiment as one of: positive, negative, controversial, concerned, neutral.\n"
        "Return only one label.\n"
        f"Title: {title}\nSummary: {summary}"
    )
    try:
        response = await async_client.call_with_thinking(
            messages=[{"role": "user", "content": prompt}],
            profile=ThinkingLevel.QUICK,
            caller="analysis.sentiment",
            max_tokens=16,
        )
    except Exception:
        return "neutral"
    label = (response.content or "").strip().lower().split()[0]
    return label if label in VALID_SENTIMENTS else "neutral"


async def classify_sentiments(category_reports: Dict[str, CategoryReport], async_client=None) -> None:
    semaphore = asyncio.Semaphore(8)
    tasks = []
    owners = []
    for report in category_reports.values():
        for item in report.all_items:
            owners.append(item)
            tasks.append(item)

    async def classify(item):
        async with semaphore:
            sentiment = await _score_item(async_client, item.item.title, item.summary)
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
