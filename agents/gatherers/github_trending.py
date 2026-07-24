"""
GitHub trending repositories gatherer.
Scrapes github.com/trending directly to capture actual daily breakout repositories.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Dict, List, Optional
import urllib.request

import requests

from ..base import BaseGatherer, CollectedItem

logger = logging.getLogger(__name__)

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
TRENDING_URLS = [
    "https://github.com/trending?since=daily",
    "https://github.com/trending/python?since=daily",
    "https://github.com/trending/typescript?since=daily",
]
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

    def _scrape_github_trending_html(self) -> List[Dict]:
        """Scrape github.com/trending pages directly for real daily trending repositories."""
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        dedup_names = set()
        repos: List[Dict] = []

        for url in TRENDING_URLS:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                articles = re.findall(r'<article class="Box-row">(.*?)</article>', html, re.DOTALL)
                for a in articles:
                    h2_match = re.search(r'<h2[^>]*>\s*<a[^>]*href="/([^"]+)"[^>]*>', a)
                    if not h2_match:
                        continue
                    repo_path = h2_match.group(1).strip()
                    if "/" not in repo_path or repo_path in dedup_names:
                        continue
                    dedup_names.add(repo_path)

                    p_match = re.search(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', a, re.DOTALL)
                    desc = re.sub(r"<[^>]+>", "", p_match.group(1)).strip() if p_match else ""
                    desc = unescape(desc)

                    lang_match = re.search(r'itemprop="programmingLanguage">(.*?)</span>', a)
                    lang = lang_match.group(1).strip() if lang_match else ""

                    stars_today_match = re.search(r'([\d,]+)\s+stars\s+(?:today|this week|this month)', a, re.IGNORECASE)
                    stars_today = stars_today_match.group(1) if stars_today_match else "0"
                    score_num = stars_today.replace(",", "")
                    score = int(score_num) if score_num.isdigit() else 100

                    repos.append({
                        "source": "github_trending",
                        "title": repo_path,
                        "url": f"https://github.com/{repo_path}",
                        "description": desc,
                        "stars": 0,
                        "stars_today": stars_today,
                        "language": lang,
                        "topics": ["github-trending"],
                        "created": "",
                        "updated": datetime.now(timezone.utc).isoformat(),
                        "hn_score": score,
                    })
            except Exception as exc:
                logger.warning(f"Failed to scrape GitHub trending URL {url}: {exc}")

        return repos

    def fetch_trending_repos(
        self,
        days: int = 1,
        min_stars: int = 50,
        per_topic: int = 5,
        token: Optional[str] = None,
    ) -> List[Dict]:
        scraped_repos = self._scrape_github_trending_html()
        if len(scraped_repos) >= 10:
            logger.info(f"Scraped {len(scraped_repos)} trending repositories directly from github.com/trending")
            return scraped_repos

        # Fallback / augmentation via GitHub Search API
        if token and token != self.token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        dedup_full_names = {r["title"] for r in scraped_repos}
        repos: List[Dict] = list(scraped_repos)

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
        item_title = f"[GitHub Trending] {title}: {description}" if description else f"[GitHub Trending] {title}"
        return CollectedItem(
            id=self.generate_id("github_trending", title, url),
            title=item_title,
            content=f"GitHub Repository: {title}\nDescription: {description}\nLanguage: {repo.get('language', '')}\nStars Today: {repo.get('stars_today', '')}",
            url=url,
            author=title.split("/")[0] if "/" in title else "github",
            published=published.isoformat(),
            source="github_trending",
            source_type="github_trending",
            tags=repo.get("topics", []),
            metadata={
                "stars": repo.get("stars", 0),
                "stars_today": repo.get("stars_today", ""),
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
