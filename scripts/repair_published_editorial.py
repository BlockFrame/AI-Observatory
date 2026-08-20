#!/usr/bin/env python3
"""Repair published editorial artifacts without making provider calls.

This maintenance command reapplies deterministic source linking, strips
machine-only evidence suffixes, and regenerates the corresponding safe HTML.
It is intentionally offline: unresolved references remain plain text.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.editorial_guard import (
    sanitize_editorial_text,
)
from agents.link_enricher import LinkEnricher
from generators.json_generator import JSONGenerator


class OfflineSelectionClient:
    """Return no semantic selections; deterministic matching still runs."""

    async def call_with_thinking(self, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(content='{"selections":[]}')


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


async def repair(
    report_date: str,
    web_dir: Path,
    *,
    sanitize_only: bool = False,
) -> None:
    date_dir = web_dir / "data" / report_date
    summary_path = date_dir / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing report: {summary_path}")

    summary = _read_json(summary_path)
    category_files: Dict[str, Dict[str, Any]] = {}
    reports: Dict[str, Dict[str, Any]] = {}
    for category, category_summary in summary.get("categories", {}).items():
        category_path = date_dir / f"{category}.json"
        if not category_path.exists():
            continue
        payload = _read_json(category_path)
        category_files[category] = payload
        reports[category] = {
            "all_items": payload.get("items", []),
            "top_items": category_summary.get("top_items", []),
            "category_summary": category_summary.get("category_summary", ""),
            "category_summary_evidence": category_summary.get(
                "category_summary_evidence", []
            ),
        }

    if sanitize_only:
        executive = summary.get("executive_summary", "")
        category_copy = {
            category: report.get("category_summary", "")
            for category, report in reports.items()
        }
        topics = summary.get("top_topics", [])
    else:
        enricher = LinkEnricher(OfflineSelectionClient(), report_date)
        executive, category_copy, topics = await enricher.enrich_all(
            summary.get("executive_summary", ""),
            reports,
            summary.get("top_topics", []),
            executive_summary_evidence=summary.get("executive_summary_evidence", []),
        )

    renderer = JSONGenerator(str(web_dir))
    changed_category_files = set()
    executive = sanitize_editorial_text(executive)
    summary["executive_summary"] = executive
    summary["executive_summary_html"] = renderer._markdown_to_html(executive)

    for category, text in category_copy.items():
        text = sanitize_editorial_text(text)
        html = renderer._markdown_to_html(text)
        summary["categories"][category]["category_summary"] = text
        summary["categories"][category]["category_summary_html"] = html
        category_payload = category_files[category]
        if (
            category_payload.get("category_summary") != text
            or category_payload.get("category_summary_html") != html
        ):
            changed_category_files.add(category)
        category_payload["category_summary"] = text
        category_payload["category_summary_html"] = html

    summary["top_topics"] = renderer._sanitize_top_topics(topics)
    _write_json(summary_path, summary)
    for category in changed_category_files:
        payload = category_files[category]
        _write_json(date_dir / f"{category}.json", payload)

    digest_path = date_dir / "digest.md"
    if digest_path.exists():
        digest_path.write_text(
            sanitize_editorial_text(digest_path.read_text(encoding="utf-8")),
            encoding="utf-8",
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair one published report using offline deterministic logic."
    )
    parser.add_argument("--date", required=True, help="Report date (YYYY-MM-DD)")
    parser.add_argument(
        "--web-dir",
        type=Path,
        default=ROOT / "web",
        help="Published web directory",
    )
    parser.add_argument(
        "--sanitize-only",
        action="store_true",
        help="Preserve existing links and only remove leaked editorial metadata.",
    )
    args = parser.parse_args()
    asyncio.run(
        repair(
            args.date,
            args.web_dir.resolve(),
            sanitize_only=args.sanitize_only,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
