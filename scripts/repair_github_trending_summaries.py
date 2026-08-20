#!/usr/bin/env python3
"""Rebuild repository-specific GitHub Trending item summaries offline."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.analyzers.github_trending_analyzer import (
    build_repository_summary,
    extract_repository_description,
)
from generators.json_generator import JSONGenerator


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def repair(report_date: str, web_dir: Path) -> int:
    date_dir = web_dir / "data" / report_date
    category_path = date_dir / "github_trending.json"
    summary_path = date_dir / "summary.json"
    if not category_path.exists() or not summary_path.exists():
        raise FileNotFoundError(f"Missing GitHub Trending report data under {date_dir}")

    category_payload = _read_json(category_path)
    summary_payload = _read_json(summary_path)
    renderer = JSONGenerator(str(web_dir))
    repaired_by_id: Dict[str, Dict[str, str]] = {}

    for item in category_payload.get("items", []):
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        description = extract_repository_description(item.get("content", ""), metadata)
        rebuilt = build_repository_summary(
            str(item.get("title") or metadata.get("title") or ""),
            description,
            str(metadata.get("stars_today") or "0"),
            str(metadata.get("language") or "Code"),
        )
        item["summary"] = rebuilt
        item["summary_html"] = renderer._markdown_to_html(rebuilt)
        if item.get("id"):
            repaired_by_id[str(item["id"])] = {
                "summary": item["summary"],
                "summary_html": item["summary_html"],
            }

    github_summary = (
        summary_payload.get("categories", {}).get("github_trending", {})
    )
    for item in github_summary.get("top_items", []):
        repaired = repaired_by_id.get(str(item.get("id") or ""))
        if repaired:
            item.update(repaired)

    _write_json(category_path, category_payload)
    _write_json(summary_path, summary_payload)
    return len(repaired_by_id)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair GitHub Trending item summaries without provider calls."
    )
    parser.add_argument("--date", required=True, help="Report date (YYYY-MM-DD)")
    parser.add_argument(
        "--web-dir",
        type=Path,
        default=ROOT / "web",
        help="Published web directory",
    )
    args = parser.parse_args()
    count = repair(args.date, args.web_dir.resolve())
    print(f"Repaired {count} GitHub Trending summaries for {args.date}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
