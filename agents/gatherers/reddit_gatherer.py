"""
Reddit Gatherer - Collects posts from Reddit subreddits via the official PRAW API.

Requires REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET.
"""

import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional

import praw
from prawcore.exceptions import RequestException, ResponseException

from ..base import BaseGatherer, CollectedItem, deduplicate_items

logger = logging.getLogger(__name__)

def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "AI-News-Aggregator/1.0")

REDDIT_MAX_ITEMS = _env_int("REDDIT_MAX_ITEMS", 500, minimum=10)
REDDIT_BODY_TOP_N = _env_int("REDDIT_BODY_TOP_N", 12, minimum=0)
REDDIT_MIN_COMMENTS_FOR_DIGEST = _env_int("REDDIT_MIN_COMMENTS_FOR_DIGEST", 8, minimum=0)
REDDIT_FETCH_WORKERS = _env_int("REDDIT_FETCH_WORKERS", 6, minimum=1)
REDDIT_OLDER_STOP_THRESHOLD = _env_int("REDDIT_OLDER_STOP_THRESHOLD", 3, minimum=1)

class RedditGatherer(BaseGatherer):
    """Gathers posts from Reddit subreddits via PRAW."""

    def __init__(
        self,
        config_dir: str = './config',
        data_dir: str = './data',
        lookback_hours: int = 24,
        target_date: Optional[str] = None
    ):
        super().__init__(config_dir, data_dir, lookback_hours, target_date)
        self.subreddits = self.load_config_list('reddit_subreddits.txt')

        if not self.subreddits:
            self.subreddits = [
                'MachineLearning',
                'artificial',
                'LocalLLaMA',
                'ChatGPT',
                'OpenAI'
            ]
            
        self._lock = Lock()
        self._stop_calls = False

    @property
    def category(self) -> str:
        return 'reddit'

    async def gather(self) -> List[CollectedItem]:
        if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
            logger.error("REDDIT_CLIENT_ID or REDDIT_CLIENT_SECRET not set - Reddit collection disabled.")
            self.save_to_file([], f'reddit_{self.target_date}.json')
            return []

        logger.info(f"Starting Reddit collection from {len(self.subreddits)} subreddits via PRAW")

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix='reddit-driver') as driver:
            all_posts = await loop.run_in_executor(driver, self._gather_sync)

        logger.info(f"Collected {len(all_posts)} posts from Reddit")
        self.save_to_file(all_posts, f'reddit_{self.target_date}.json')
        return all_posts

    def _gather_sync(self) -> List[CollectedItem]:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT
        )

        all_posts: List[CollectedItem] = []
        with ThreadPoolExecutor(max_workers=REDDIT_FETCH_WORKERS, thread_name_prefix='reddit-sub') as ex:
            future_to_sub = {ex.submit(self._fetch_subreddit, reddit, sub): sub for sub in self.subreddits}
            for future in as_completed(future_to_sub):
                sub = future_to_sub[future]
                try:
                    all_posts.extend(future.result())
                except Exception as e:
                    logger.error(f"r/{sub} worker failed: {e}")

        all_posts = deduplicate_items(all_posts)
        return all_posts

    def _fetch_subreddit(self, reddit: praw.Reddit, subreddit: str) -> List[CollectedItem]:
        pairs: List[tuple] = []
        seen_ids = set()
        consecutive_older = 0
        
        try:
            sub = reddit.subreddit(subreddit)
            for submission in sub.new(limit=REDDIT_MAX_ITEMS):
                if self._stop_calls:
                    break
                    
                post_id = submission.id
                if not post_id or post_id in seen_ids:
                    continue
                seen_ids.add(post_id)
                
                if submission.stickied:
                    continue
                    
                try:
                    pub_dt = datetime.fromtimestamp(submission.created_utc)
                except (ValueError, OSError, OverflowError):
                    continue

                if pub_dt > self.end_time:
                    consecutive_older = 0
                    continue
                if pub_dt < self.start_time:
                    consecutive_older += 1
                    if consecutive_older >= REDDIT_OLDER_STOP_THRESHOLD:
                        break
                    continue
                    
                consecutive_older = 0
                pairs.append((self._build_item(subreddit, submission, pub_dt), submission))

            logger.info(f"r/{subreddit}: collected {len(pairs)} in-window posts")

            if pairs and not self._stop_calls:
                self._enrich_pairs(subreddit, pairs)

        except (RequestException, ResponseException) as e:
            logger.error(f"PRAW Request Error fetching r/{subreddit}: {e}")
        except Exception as e:
            logger.error(f"Error fetching r/{subreddit}: {e}")

        return [item for item, _ in pairs]

    def _build_item(self, subreddit: str, submission: Any, pub_dt: datetime) -> CollectedItem:
        post_id = submission.id
        title = submission.title or ""
        
        return CollectedItem(
            id=self.generate_id('reddit', post_id),
            title=title,
            content="",  # enriched later
            url=f"https://reddit.com{submission.permalink}",
            author=f"u/{submission.author.name if submission.author else '[deleted]'}",
            published=pub_dt.isoformat(),
            source=f"r/{subreddit}",
            source_type='reddit',
            tags=[], 
            metadata={
                'platform_id': post_id,
                'subreddit': subreddit,
                'external_url': submission.url,
                'is_self': submission.is_self,
                'engagement': {
                    'score': submission.score,
                    'upvote_ratio': submission.upvote_ratio,
                    'num_comments': submission.num_comments,
                },
            },
            keywords=self.extract_keywords(title),
        )

    def _enrich_pairs(self, subreddit: str, pairs: List[tuple]) -> None:
        ranked = sorted(pairs, key=lambda p: p[1].score or 0, reverse=True)
        for item, submission in ranked[:REDDIT_BODY_TOP_N]:
            if self._stop_calls:
                break
            try:
                self._enrich_one(item, submission)
            except Exception as e:
                logger.warning(f"Enrichment failed for {item.url}: {e}")

    def _enrich_one(self, item: CollectedItem, submission: Any) -> None:
        is_self = submission.is_self
        num_comments = submission.num_comments or 0

        if not is_self and num_comments < REDDIT_MIN_COMMENTS_FOR_DIGEST:
            return

        content = ""
        if is_self:
            content = (submission.selftext or "").strip()
            
        if not content:
            content = self._build_comment_digest(submission)

        if content:
            item.content = content
            item.keywords = self.extract_keywords(f"{item.title} {content}")

    def _build_comment_digest(self, submission: Any, max_comments: int = 6, max_len: int = 220) -> str:
        try:
            submission.comment_sort = 'best'
            submission.comments.replace_more(limit=0)
            comments = submission.comments.list()
        except Exception:
            return ""
            
        cleaned = []
        for c in comments:
            try:
                body = (c.body or "").strip()
                if not body:
                    continue
                author = (c.author.name.lower() if c.author else "[deleted]")
                if author in ("automoderator", "[deleted]"):
                    continue
                low = body.lower()
                if "i am a bot" in low or "performed automatically" in low:
                    continue
                body = " ".join(body.split()) 
                if len(body) > max_len:
                    body = body[:max_len].rstrip() + "…"
                cleaned.append((c.score or 0, body))
            except AttributeError:
                continue

        if not cleaned:
            return ""

        cleaned.sort(key=lambda x: x[0], reverse=True)
        lines = ["**Top community comments:**", ""]
        for score, body in cleaned[:max_comments]:
            lines.append(f"- (▲{score}) {body}")
        return "\n".join(lines)
