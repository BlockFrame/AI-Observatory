"""
Generate digest markdown per day.
"""

from pathlib import Path
from typing import Dict, List


def _section_lines(report: Dict, source_label: bool = False) -> List[str]:
    lines: List[str] = []
    for idx, item in enumerate(report.get("top_items", [])[:10], start=1):
        base = item.get("item", item)
        title = base.get("title", "Untitled")
        url = base.get("url", "")
        sentiment = item.get("sentiment") or base.get("metadata", {}).get("sentiment", "neutral")
        summary = item.get("summary", "")
        source = base.get("source", "")
        if url:
            heading = f"{idx}. **[{title}]({url})** — {sentiment}"
        else:
            heading = f"{idx}. **{title}** — {sentiment}"
        if source_label and source:
            heading += f" — *via {source}*"
        lines.append(heading)
        if summary:
            lines.append(f"   {summary}")
    if not lines:
        lines.append("1. _No items_")
    return lines


def generate_digest_markdown(result: Dict, web_dir: str = "web") -> str:
    date = result.get("date", "")
    reports = result.get("category_reports", {})
    executive_summary = result.get("executive_summary", "")
    lines = [
        f"# AI Digest — {date}",
        "",
        "## Executive Summary",
        executive_summary,
        "",
        "## 🔬 Research Papers",
        *_section_lines(reports.get("research", {})),
        "",
        "## 📰 Industry News",
        *_section_lines(reports.get("news", {}), source_label=True),
        "",
        "## 📦 Trending Repos",
        *_section_lines(
            {
                "top_items": [
                    item
                    for item in reports.get("news", {}).get("top_items", [])
                    if "github.com" in (item.get("item", item).get("url", ""))
                ]
            }
        ),
        "",
        "## 🐦 Social Signals",
        *_section_lines(reports.get("social", {})),
        "",
        "---",
        f"_{result.get('total_items_analyzed', 0)} items • {result.get('date', '')}_",
    ]
    content = "\n".join(lines).strip() + "\n"
    out_path = Path(web_dir) / "data" / date / "digest.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return content
