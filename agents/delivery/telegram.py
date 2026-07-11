"""
Telegram delivery for daily report.
"""

import os
from typing import Dict, List

import requests

TELEGRAM_MAX_LEN = 4096


def _chunks(text: str, max_len: int = TELEGRAM_MAX_LEN) -> List[str]:
    if len(text) <= max_len:
        return [text]
    parts: List[str] = []
    remaining = text
    while len(remaining) > max_len:
        split_at = remaining.rfind("\n", 0, max_len)
        if split_at < 0:
            split_at = max_len
        parts.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        parts.append(remaining)
    return parts


def format_daily_report(summary_data: Dict) -> str:
    date = summary_data.get("date", "")
    executive = (summary_data.get("executive_summary", "") or "").strip()
    reports = summary_data.get("category_reports", {})

    def top_lines(category: str, max_items: int = 3) -> List[str]:
        report = reports.get(category, {})
        lines = []
        for item in report.get("top_items", [])[:max_items]:
            base = item.get("item", item)
            title = base.get("title", "Untitled")
            url = base.get("url", "")
            sentiment = item.get("sentiment") or base.get("metadata", {}).get("sentiment", "neutral")
            if url:
                lines.append(f"• [{title}]({url}) — {sentiment}")
            else:
                lines.append(f"• {title} — {sentiment}")
        return lines or ["• No items"]

    news_lines = top_lines("news")
    research_lines = top_lines("research")
    social_lines = top_lines("social")
    repos = [
        line
        for line in top_lines("news", 8)
        if "github.com/" in line or "github_trending" in line.lower()
    ][:3]
    if not repos:
        repos = ["• No trending repos"]

    total_items = summary_data.get("total_items_analyzed", 0)
    tokens_used = 0
    orchestrator_thinking = summary_data.get("orchestrator_thinking", "") or ""
    if orchestrator_thinking:
        tokens_used = len(orchestrator_thinking.split())

    executive_short = executive[:200] + ("..." if len(executive) > 200 else "")
    lines = [
        f"🤖 *AI Daily Digest — {date}*",
        "",
        f"_{executive_short}_",
        "",
        "🔬 *Top Papers*",
        *research_lines,
        "",
        "📰 *Industry News*",
        *news_lines,
        "",
        "📦 *Trending Repos*",
        *repos,
        "",
        "🐦 *Social Signals*",
        *social_lines,
        "",
        f"_{total_items} items analyzed • {tokens_used} tokens consumed_",
    ]
    return "\n".join(lines)


def send_report(report_markdown: str, bot_token: str = None, chat_id: str = None) -> bool:
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
    target_chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not target_chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    message_chunks = _chunks(report_markdown, TELEGRAM_MAX_LEN)
    ok = True
    for index, chunk in enumerate(message_chunks):
        payload = {
            "chat_id": target_chat_id,
            "text": chunk,
            "disable_web_page_preview": index != 0,
            "parse_mode": "Markdown",
        }
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 400:
            payload["parse_mode"] = ""
            response = requests.post(url, json=payload, timeout=30)
        if not response.ok:
            ok = False
            break
    return ok
