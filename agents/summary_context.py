"""Shared, explicitly partitioned context for executive-summary generation.

Historical summaries are useful only as anti-repetition context. Current
topics and item records are the sole factual evidence for the new report.
Keeping this assembly in one module prevents the live pipeline and offline
regeneration script from drifting apart.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Mapping, Sequence, Tuple

logger = logging.getLogger(__name__)

PREVIOUS_COVERAGE_OPEN = (
    "=== PREVIOUS DAYS' COVERAGE (HISTORICAL; DO NOT REPORT AS CURRENT) ==="
)
PREVIOUS_COVERAGE_CLOSE = "=== END PREVIOUS DAYS' COVERAGE ==="
TODAYS_DATA_OPEN = "=== TODAY'S DATA (CURRENT EVIDENCE) ==="
TODAYS_DATA_CLOSE = "=== END TODAY'S DATA ==="


def load_previous_summaries(
    web_dir: str,
    target_date: str,
    lookback_days: int = 3,
) -> List[Tuple[str, str]]:
    """Return available prior executive summaries, newest first."""
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    summaries: List[Tuple[str, str]] = []

    for days_ago in range(1, lookback_days + 1):
        date_str = (target_dt - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        summary_path = Path(web_dir) / "data" / date_str / "summary.json"
        if not summary_path.exists():
            continue

        try:
            data = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load previous summary for %s: %s", date_str, exc)
            continue

        executive_summary = data.get("executive_summary", "")
        if isinstance(executive_summary, str) and executive_summary.strip():
            summaries.append((date_str, executive_summary.strip()))

    return summaries


def format_previous_coverage(
    dated_summaries: Sequence[Tuple[str, str]],
) -> str:
    """Wrap historical prose in an unambiguous, explicitly closed section."""
    if not dated_summaries:
        return ""

    blocks = [
        f"--- HISTORICAL REPORT {date_str} ---\n{summary}"
        for date_str, summary in dated_summaries
    ]
    return "\n\n".join(
        [PREVIOUS_COVERAGE_OPEN, *blocks, PREVIOUS_COVERAGE_CLOSE]
    )


def build_executive_context(
    target_date: str,
    previous_coverage: str,
    topics: Sequence[Tuple[str, str]],
    categories: Sequence[Tuple[str, str, Sequence[Mapping[str, Any]]]],
) -> str:
    """Build the executive-summary context with strict history/current bounds.

    ``categories`` contains ``(name, summary, current_items)`` tuples. Each
    current item may provide ``id``, ``title`` and ``summary`` fields.
    """
    parts = [f"Report date: {target_date}", ""]

    if previous_coverage:
        parts.extend([previous_coverage, ""])

    parts.extend([TODAYS_DATA_OPEN, "", "TOP TOPICS (CURRENT):"])
    if topics:
        for index, (name, description) in enumerate(topics, 1):
            parts.append(f"{index}. {name}: {description}")
    else:
        parts.append("None detected.")
    parts.append("")

    for category, category_summary, current_items in categories:
        parts.append(f"--- CURRENT CATEGORY: {category.upper()} ---")
        parts.append(f"Current category summary: {category_summary}")
        if current_items:
            parts.append("CURRENT ITEMS (the only valid factual evidence):")
            for item in current_items:
                parts.append(
                    "- ID: {id} | Title: {title} | Summary: {summary}".format(
                        id=item.get("id", ""),
                        title=item.get("title", ""),
                        summary=item.get("summary", ""),
                    )
                )
        else:
            parts.append("CURRENT ITEMS: none.")
        parts.append("")

    parts.append(TODAYS_DATA_CLOSE)
    return "\n".join(parts)
