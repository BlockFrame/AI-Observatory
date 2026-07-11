"""
GitHub trending repositories gatherer.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests

from ..base import BaseGatherer, CollectedItem

logger = logging.getLogger(__name__)

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
TRENDING_TOPICS = [
    "artificial-intelligence",
    "machine-learning",
    "large-language-models",
    "llm",
    "generative-ai",
    "ai-agents",
    "transformers",
    "diffusion-models",
    "rag",
    "mcp",
]


class GitHubTrendingGatherer(BaseGatherer):
    def __init__(
        self,
        config_dir: str = "./config",
        data_dir: str = "./data",
        lookback_hours: int = 24,
        target_date: Optional[str] = None,
        token: Optional[str] = None,
    ):
        super().__init__(config_dir, data_dir, lookback_hours, target_date)
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/vnd.github+json"})
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

    @property
    def category(self) -> str:
        return "news"

    def fetch_trending_repos(
        self,
        days: int = 1,
        min_stars: int = 50,
        per_topic: int = 5,
        token: Optional[str] = None,
    ) -> List[Dict]:
        if token and token != self.token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        dedup_full_names = set()
        repos: List[Dict] = []
        for topic in TRENDING_TOPICS:
            params = {
                "q": f"topic:{topic} stars:>{min_stars} pushed:>{since}",
                "sort": "stars",
                "order": "desc",
                "per_page": per_topic,
            }
            try:
                response = self.session.get(GITHUB_SEARCH_URL, params=params, timeout=30)
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                logger.warning(f"GitHub topic query failed for {topic}: {exc}")
                continue
            for repo in payload.get("items", []):
                full_name = str(repo.get("full_name") or "").strip()
                if not full_name or full_name in dedup_full_names:
                    continue
                dedup_full_names.add(full_name)
                repos.append(
                    {
                        "source": "github_trending",
                        "title": full_name,
                        "url": str(repo.get("html_url") or ""),
                        "description": str(repo.get("description") or ""),
                        "stars": int(repo.get("stargazers_count") or 0),
                        "language": str(repo.get("language") or ""),
                        "topics": repo.get("topics") or [],
                        "created": str(repo.get("created_at") or ""),
                        "updated": str(repo.get("updated_at") or ""),
                        "hn_score": int(repo.get("stargazers_count") or 0),
                    }
                )
        return repos

    def _to_collected_item(self, repo: Dict) -> CollectedItem:
        title = repo.get("title", "")
        url = repo.get("url", "")
        description = repo.get("description", "")
        updated = repo.get("updated", "") or datetime.now(timezone.utc).isoformat()
        published = datetime.now(timezone.utc)
        try:
            if updated:
                published = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        except Exception:
            pass
        return CollectedItem(
            id=self.generate_id("github_trending", title, url),
            title=title,
            content=description,
            url=url,
            author=title.split("/")[0] if "/" in title else "github",
            published=published.isoformat(),
            source="github_trending",
            source_type="github_trending",
            tags=repo.get("topics", []),
            metadata={
                "stars": repo.get("stars", 0),
                "language": repo.get("language", ""),
                "topics": repo.get("topics", []),
                "created": repo.get("created", ""),
                "updated": repo.get("updated", ""),
                "hn_score": repo.get("hn_score", 0),
            },
            keywords=self.extract_keywords(f"{title} {description} {' '.join(repo.get('topics', []))}"),
        )

    async def gather(
        self,
        days: int = 1,
        min_stars: int = 50,
        per_topic: int = 5,
    ) -> List[CollectedItem]:
        repos = await asyncio.to_thread(
            self.fetch_trending_repos,
            days,
            min_stars,
            per_topic,
            self.token,
        )
        items = [self._to_collected_item(repo) for repo in repos]
        logger.info(f"GitHub trending gatherer collected {len(items)} repos")
        return items
