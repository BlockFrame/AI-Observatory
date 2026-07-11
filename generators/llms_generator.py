"""
Generate llms.txt and ai-index.json at repository root.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def get_available_dates(data_dir: Path) -> List[str]:
    if not data_dir.exists():
        return []
    dates = []
    for child in data_dir.iterdir():
        if child.is_dir() and len(child.name) == 10 and child.name[4] == "-" and child.name[7] == "-":
            dates.append(child.name)
    return sorted(dates, reverse=True)


def _base_url() -> str:
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if repo:
        return f"https://raw.githubusercontent.com/{repo}/main"
    return "https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main"


def generate_llms_txt(data_dir: Path = Path("web/data")) -> str:
    base_url = _base_url()
    dates = get_available_dates(data_dir)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    date_lines = [f"- {d}: {base_url}/web/data/{d}/summary.json" for d in dates[:60]]
    content = "\n".join(
        [
            "# AI News Aggregator — Daily Intelligence Digest",
            "",
            "> Daily AI intelligence digest: news, papers, repos, HN, social signals.",
            "> Multi-agent analysis with adaptive thinking (MAP-REDUCE).",
            f"> Generated: {today}",
            "",
            "## Data structure",
            "All daily data is available as JSON at /web/data/{YYYY-MM-DD}/{category}.json",
            f"Base URL: {base_url}/web/data/",
            "",
            "### Categories",
            "- summary.json — Executive summary + top items (500-800 words)",
            "- research.json — Paper arXiv (cs.AI, cs.LG, cs.CL, cs.CV, cs.NE, cs.RO, stat.ML)",
            "- news.json — News AI from RSS feeds + Hacker News + GitHub Trending",
            "- social.json — Posts from Twitter/X, Bluesky, Mastodon",
            "- reddit.json — Threads from AI subreddits",
            "",
            f"## Available dates ({len(dates)} total)",
            *date_lines,
            "",
            "## Quick query patterns",
            '- "What happened today?" → fetch /web/data/{today}/summary.json',
            '- "Recent RAG papers" → fetch /web/data/{date}/research.json, search for "RAG"',
            '- "What\'s trending on HN?" → fetch /web/data/{date}/news.json, filter source=hackernews',
            '- "New AI repos on GitHub" → fetch /web/data/{date}/news.json, filter source=github_trending',
            '- "Cross-day story tracking" → fetch summary.json for last 7 days, compare topics',
            "",
            "## Machine-readable index",
            f"For structured access, fetch: {base_url}/ai-index.json",
        ]
    )
    Path("llms.txt").write_text(content + "\n", encoding="utf-8")
    return content


def generate_ai_index_json(data_dir: Path = Path("web/data")) -> str:
    base_url = _base_url()
    dates = get_available_dates(data_dir)
    payload: Dict = {
        "project": "AI News Aggregator",
        "description": "Daily AI intelligence digest with multi-agent analysis",
        "base_url": f"{base_url}/web/data",
        "categories": {
            "summary": "summary.json",
            "research": "research.json",
            "news": "news.json",
            "social": "social.json",
            "reddit": "reddit.json",
        },
        "total_dates": len(dates),
        "dates": dates,
        "latest": dates[0] if dates else "",
        "url_pattern": "{base_url}/{date}/{category}.json",
        "query_examples": [
            "What happened today?",
            "Recent RAG papers",
            "What's trending on HN?",
            "New AI repos on GitHub",
            "Cross-day story tracking",
        ],
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    Path("ai-index.json").write_text(text + "\n", encoding="utf-8")
    return text
