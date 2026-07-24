"""
Hacker News gatherer using the public Firebase API.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

from ..base import BaseGatherer, CollectedItem

logger = logging.getLogger(__name__)

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"


class HackerNewsGatherer(BaseGatherer):
    def __init__(
        self,
        config_dir: str = "./config",
        data_dir: str = "./data",
        lookback_hours: int = 24,
        target_date: Optional[str] = None,
        top_limit: int = 30,
        top_min_score: int = 50,
        best_limit: int = 20,
        best_min_score: int = 100,
    ):
        super().__init__(config_dir, data_dir, lookback_hours, target_date)
        self.top_limit = top_limit
        self.top_min_score = top_min_score
        self.best_limit = best_limit
        self.best_min_score = best_min_score
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "AI-News-Aggregator/1.0"})

    @property
    def category(self) -> str:
        return "news"

    def _fetch_json(self, endpoint: str):
        url = f"{HN_API_BASE}/{endpoint}"
        response = self.session.get(url, timeout=20)
        response.raise_for_status()
        return response.json()

    def _fetch_story(self, story_id: int) -> Optional[Dict]:
        try:
            payload = self._fetch_json(f"item/{story_id}.json")
        except Exception as exc:
            logger.warning(f"HN item fetch failed for id={story_id}: {exc}")
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _collect_story_set(self, endpoint: str, limit: int, min_score: int) -> List[Dict]:
        ids = self._fetch_json(f"{endpoint}.json")
        if not isinstance(ids, list):
            return []
        stories: List[Dict] = []
        for sid in ids[: max(limit * 4, limit)]:
            story = self._fetch_story(int(sid))
            if not story:
                continue
            if story.get("type") != "story":
                continue
            score = int(story.get("score") or 0)
            if score < min_score:
                continue
            stories.append(story)
            if len(stories) >= limit:
                break
        return stories

    def fetch_top_stories(self, limit: int = 30, min_score: int = 50) -> List[Dict]:
        return self._collect_story_set("topstories", limit, min_score)

    def fetch_best_stories(self, limit: int = 20, min_score: int = 100) -> List[Dict]:
        return self._collect_story_set("beststories", limit, min_score)

    def _to_collected_item(self, story: Dict) -> CollectedItem:
        story_id = int(story.get("id"))
        title = str(story.get("title") or "").strip()
        url = str(story.get("url") or "").strip()
        if not url:
            url = f"https://news.ycombinator.com/item?id={story_id}"
        author = str(story.get("by") or "unknown")
        unix_ts = int(story.get("time") or 0)
        published = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
        text_raw = str(story.get("text") or "")
        text = re.sub(r"<[^>]+>", "", text_raw)
        score = int(story.get("score") or 0)
        comments = int(story.get("descendants") or 0)
        hn_url = f"https://news.ycombinator.com/item?id={story_id}"
        return CollectedItem(
            id=self.generate_id("hackernews", str(story_id), title),
            title=title,
            content=text or title,
            url=url,
            author=author,
            published=published.isoformat(),
            source="hackernews",
            source_type="hackernews",
            tags=["hackernews"],
            metadata={
                "hn_score": score,
                "hn_comments": comments,
                "hn_url": hn_url,
                "type": str(story.get("type") or "story"),
            },
            keywords=self.extract_keywords(f"{title} {text}"),
        )

    async def gather(self) -> List[CollectedItem]:
        top_stories = await asyncio.to_thread(
            self.fetch_top_stories, self.top_limit, self.top_min_score
        )
        best_stories = await asyncio.to_thread(
            self.fetch_best_stories, self.best_limit, self.best_min_score
        )
        all_stories = top_stories + best_stories
        dedup: Dict[int, Dict] = {}
        for story in all_stories:
            sid = int(story.get("id") or 0)
            if not sid:
                continue
            existing = dedup.get(sid)
            if not existing or int(story.get("score") or 0) > int(existing.get("score") or 0):
                dedup[sid] = story
        items = [self._to_collected_item(story) for story in dedup.values()]
        items = [item for item in items if self.is_in_date_range(datetime.fromisoformat(item.published).replace(tzinfo=None))]
        logger.info(f"HackerNews gatherer collected {len(items)} items")
        return items
