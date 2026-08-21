"""Dependency-free read model for the local R[AI]DAR MCP server."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def available_dates(data_dir: Path) -> list[str]:
    if not data_dir.exists():
        raise FileNotFoundError("Data directory not found.")
    return sorted(
        (
            item.name
            for item in data_dir.iterdir()
            if item.is_dir() and DATE_PATTERN.fullmatch(item.name)
        ),
        reverse=True,
    )


def daily_summary(data_dir: Path, date: str) -> dict[str, Any]:
    if not DATE_PATTERN.fullmatch(str(date)):
        raise ValueError("Invalid date format. Use YYYY-MM-DD.")
    summary_file = data_dir / str(date) / "summary.json"
    if not summary_file.exists():
        raise FileNotFoundError(f"No summary found for date {date}.")
    with summary_file.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Summary for date {date} is not a JSON object.")
    return payload


def search_summaries(data_dir: Path, query: str) -> list[dict[str, Any]]:
    normalized_query = str(query or "").strip().lower()
    if not normalized_query:
        raise ValueError("Query must be a non-empty string.")

    results: list[dict[str, Any]] = []
    for date in available_dates(data_dir):
        try:
            data = daily_summary(data_dir, date)
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError):
            continue

        summary = data.get("executive_summary", "")
        summary_text = summary if isinstance(summary, str) else json.dumps(summary)
        if normalized_query in summary_text.lower():
            results.append(
                {
                    "date": date,
                    "match": "executive_summary",
                    "snippet": summary_text[:200] + ("..." if len(summary_text) > 200 else ""),
                }
            )
            continue

        for topic in data.get("top_topics", []):
            if not isinstance(topic, dict):
                continue
            topic_text = f"{topic.get('name', '')} {topic.get('description', '')}"
            if normalized_query in topic_text.lower():
                results.append(
                    {"date": date, "match": "top_topic", "topic": topic.get("name")}
                )
                break
    return results
