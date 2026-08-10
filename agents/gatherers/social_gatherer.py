"""
Social Gatherer - Collects posts from Twitter/X.

Twitter uses GetXAPI (paid, $0.001/call ≈ $0.05/1,000 tweets).
"""

import asyncio
import logging
import os
import re
import time
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from ..base import BaseGatherer, CollectedItem

logger = logging.getLogger(__name__)

# GetXAPI configuration
GETXAPI_KEY = os.getenv('GETXAPI_KEY', '')
GETXAPI_BASE = "https://api.getxapi.com"


class SocialGatherer(BaseGatherer):
    """Gathers posts from Twitter/X."""

    def __init__(
        self,
        config_dir: str = './config',
        data_dir: str = './data',
        lookback_hours: int = 24,
        target_date: Optional[str] = None
    ):
        super().__init__(config_dir, data_dir, lookback_hours, target_date)

        # Load configured accounts
        self.twitter_users = self.load_config_list('twitter_accounts.txt')

        # Track collection status per platform
        self.collection_status: Dict[str, Dict[str, Any]] = {
            'twitter': {'status': 'pending', 'count': 0, 'error': None},
        }

        # GetXAPI usage accounting (surfaced in the end-of-run cost summary)
        self._twitter_calls = 0          # billable API calls issued ($0.001 each)
        self._twitter_tweets_billed = 0  # raw tweets returned (~20 per call)

        logger.info(f"Loaded {len(self.twitter_users)} Twitter accounts")

    @property
    def category(self) -> str:
        return 'social'

    async def gather(self) -> List[CollectedItem]:
        """Gather posts from Twitter."""
        logger.info("Starting social media collection")

        all_items = []
        loop = asyncio.get_event_loop()

        # Mark skipped platforms
        if not self.twitter_users or not GETXAPI_KEY:
            self.collection_status['twitter']['status'] = 'skipped'
            self.collection_status['twitter']['error'] = 'No API key' if not GETXAPI_KEY else 'No accounts configured'

        # Collect from Twitter in parallel
        with ThreadPoolExecutor(max_workers=6) as executor:
            tasks = []

            # Twitter collection
            if self.twitter_users and GETXAPI_KEY:
                tasks.append(loop.run_in_executor(executor, self._collect_twitter))

            if tasks:
                results = await asyncio.gather(*tasks)
                for result in results:
                    all_items.extend(result)

        logger.info(f"Collected {len(all_items)} total social posts")

        # Log collection status summary
        self._log_collection_summary()

        # Save to file
        self.save_to_file(all_items, f'social_{self.target_date}.json')

        return all_items

    def _log_collection_summary(self):
        """Log a summary of collection status for all platforms."""
        logger.info("Social collection summary:")
        for platform, status in self.collection_status.items():
            if status['status'] == 'success':
                logger.info(f"  ✓ {platform.capitalize()}: {status['count']} posts")
            elif status['status'] == 'partial':
                logger.warning(f"  ⚠ {platform.capitalize()}: {status['count']} posts (partial - {status['error']})")
            elif status['status'] == 'failed':
                logger.error(f"  ✗ {platform.capitalize()}: FAILED - {status['error']}")
            elif status['status'] == 'skipped':
                logger.info(f"  - {platform.capitalize()}: skipped ({status['error']})")
            else:
                logger.warning(f"  ? {platform.capitalize()}: unknown status")

    def get_collection_status(self) -> Dict[str, Dict[str, Any]]:
        """Get collection status for all platforms."""
        return self.collection_status

    # ========== TWITTER COLLECTION ==========

    def _collect_twitter(self) -> List[CollectedItem]:
        """Collect tweets from configured users via GetXAPI."""
        if not GETXAPI_KEY:
            logger.warning("GetXAPI key not configured - skipping Twitter")
            self.collection_status['twitter']['status'] = 'skipped'
            self.collection_status['twitter']['error'] = 'No API key'
            return []

        all_tweets = []

        try:
            # Use search endpoint for efficiency
            tweets = self._twitter_search(self.twitter_users)
            all_tweets.extend(tweets)

            if all_tweets:
                self.collection_status['twitter']['status'] = 'success'
                self.collection_status['twitter']['count'] = len(all_tweets)
            else:
                # Got 0 tweets - might be an API issue or just no recent tweets
                self.collection_status['twitter']['status'] = 'success'
                self.collection_status['twitter']['count'] = 0

            logger.info(f"Collected {len(all_tweets)} tweets from Twitter")
        except Exception as e:
            self.collection_status['twitter']['status'] = 'failed'
            self.collection_status['twitter']['error'] = str(e)
            logger.error(f"Twitter collection failed: {e}")

        # Surface GetXAPI usage + balance in the end-of-run cost summary.
        try:
            from ..cost_tracker import get_tracker
            balance_usd = self._fetch_twitter_balance()
            # GetXAPI bills $0.001 per call (~20 tweets/call → ~$0.05 per 1,000 tweets).
            est_cost = round(self._twitter_calls * 0.001, 4)
            logger.info(
                f"GetXAPI usage: {self._twitter_calls} calls, "
                f"{self._twitter_tweets_billed} tweets collected; "
                f"balance=${balance_usd}; est_cost=${est_cost}"
            )
            get_tracker().record_external_api(
                "GetXAPI (Twitter)",
                calls=self._twitter_calls,
                items=self._twitter_tweets_billed,
                balance=None,
                balance_usd=balance_usd,
                est_cost_usd=est_cost,
            )
        except Exception as e:  # never let reporting break collection
            logger.debug(f"Could not record GetXAPI usage: {e}")

        return all_tweets

    def _fetch_twitter_balance(self) -> Optional[float]:
        """Best-effort GetXAPI credit balance via GET /account/me endpoint."""
        if not GETXAPI_KEY:
            return None
        try:
            resp = requests.get(
                f"{GETXAPI_BASE}/account/me",
                headers={"Authorization": f"Bearer {GETXAPI_KEY}"},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                # GetXAPI returns credits_usd or balance field depending on API version
                return data.get("credits_usd") or data.get("balance") or data.get("credits")
            logger.warning(f"GetXAPI balance probe returned HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"Could not fetch GetXAPI balance: {e}")
        return None

    def _twitter_search(self, usernames: List[str]) -> List[CollectedItem]:
        """Use Twitter advanced search to collect from multiple users."""
        all_tweets = []
        failed_chunks = 0

        if not usernames:
            return []

        # X silently returns an empty result set when a query exceeds its
        # approximately 22-23 operator limit. Reserve two operators for the
        # date range, leaving at most 20 `from:` clauses per request.
        max_users = 20
        chunks = [usernames[i:i + max_users] for i in range(0, len(usernames), max_users)]

        # Format dates for search
        since_date = self.start_time.strftime('%Y-%m-%d')
        until_date = (self.end_time + timedelta(days=1)).strftime('%Y-%m-%d')

        headers = {
            "Authorization": f"Bearer {GETXAPI_KEY}",
        }

        for chunk_idx, chunk in enumerate(chunks):
            from_clauses = [f"from:{u}" for u in chunk]
            query = f"({' OR '.join(from_clauses)}) since:{since_date} until:{until_date}"
            logger.info(f"Twitter search query (chunk {chunk_idx + 1}/{len(chunks)})")
            chunk_error = None

            cursor = ""
            page = 0
            max_pages = 10

            while page < max_pages:
                try:
                    # GetXAPI: query param is 'q', type param is 'product'
                    params = {"q": query, "product": "Latest"}
                    if cursor:
                        params["cursor"] = cursor

                    response = requests.get(
                        f"{GETXAPI_BASE}/twitter/tweet/advanced_search",
                        params=params,
                        headers=headers,
                        timeout=30
                    )
                    response.raise_for_status()
                    self._twitter_calls += 1
                    data = response.json()

                    tweets_data = data.get('tweets', [])
                    if not tweets_data:
                        tweets_data = data.get('data', {}).get('tweets', [])

                    if not tweets_data:
                        logger.warning(
                            "GetXAPI returned no tweets for Twitter search chunk "
                            f"{chunk_idx + 1}/{len(chunks)} "
                            f"({len(chunk)} accounts, page {page + 1})"
                        )
                        break

                    # GetXAPI bills per call; track tweet count for metrics.
                    self._twitter_tweets_billed += len(tweets_data)

                    for tweet_data in tweets_data:
                        try:
                            item = self._parse_twitter_tweet(tweet_data)
                            if item and self.is_in_date_range(datetime.fromisoformat(item.published)):
                                all_tweets.append(item)
                        except Exception as e:
                            logger.error(f"Error parsing tweet: {e}")

                    # Pagination
                    has_next = data.get('has_next_page') or data.get('has_next') or bool(data.get('next_cursor') or data.get('cursor'))
                    next_cursor = data.get('next_cursor') or data.get('cursor') or ''

                    if not has_next or not next_cursor:
                        break

                    cursor = next_cursor
                    page += 1
                    time.sleep(0.3)

                except Exception as e:
                    logger.error(f"Error in Twitter search: {e}")
                    chunk_error = str(e)
                    failed_chunks += 1
                    break

            if chunk_idx < len(chunks) - 1:
                time.sleep(0.5)

        # Track partial failures
        if failed_chunks > 0:
            if failed_chunks == len(chunks):
                self.collection_status['twitter']['status'] = 'failed'
                self.collection_status['twitter']['error'] = f"All {failed_chunks} API requests failed"
            else:
                self.collection_status['twitter']['status'] = 'partial'
                self.collection_status['twitter']['error'] = f"{failed_chunks}/{len(chunks)} API requests failed"

        return all_tweets

    def _parse_twitter_tweet(self, tweet_data: Dict[str, Any]) -> Optional[CollectedItem]:
        """Parse a tweet into CollectedItem."""
        tweet_id = tweet_data.get('id', '')
        text = tweet_data.get('text', '')
        created_at = tweet_data.get('createdAt', '')
        author = tweet_data.get('author', {})
        username = author.get('userName', author.get('username', 'unknown'))
        external_urls = self._extract_tweet_urls(tweet_data)

        # Parse date
        try:
            pub_date = parsedate_to_datetime(created_at)
            if pub_date.tzinfo:
                pub_date = pub_date.replace(tzinfo=None)
        except (ValueError, TypeError, OverflowError):
            try:
                pub_date = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%S.%fZ')
            except (ValueError, TypeError):
                # Never substitute the current time: a malformed timestamp on
                # an old tweet could otherwise make it pass today's date gate.
                logger.warning("Discarding tweet %s with invalid createdAt=%r", tweet_id, created_at)
                return None

        return CollectedItem(
            id=self.generate_id('twitter', tweet_id),
            title=text[:100] + '...' if len(text) > 100 else text,
            content=text,
            url=f"https://twitter.com/{username}/status/{tweet_id}",
            author=f"@{username}",
            published=pub_date.isoformat(),
            source='Twitter',
            source_type='twitter',
            tags=[],
            metadata={
                'platform_id': tweet_id,
                'author_display_name': author.get('name', username),
                # GetXAPI commonly keeps expanded links in entities while the
                # visible tweet text contains no URL. Preserve them so the news
                # link follower can discover the referenced articles.
                'external_urls': external_urls,
                'engagement': {
                    'likes': tweet_data.get('likeCount', 0),
                    'retweets': tweet_data.get('retweetCount', 0),
                    'replies': tweet_data.get('replyCount', 0),
                    'quotes': tweet_data.get('quoteCount', 0),
                    'views': tweet_data.get('viewCount', 0)
                }
            },
            keywords=self.extract_keywords(text)
        )

    @staticmethod
    def _extract_tweet_urls(tweet_data: Dict[str, Any]) -> List[str]:
        """Extract expanded article URLs from common GetX/Twitter entity shapes."""
        urls: List[str] = []
        seen = set()

        def add(candidate: Any) -> None:
            if not isinstance(candidate, str) or not candidate.startswith(('http://', 'https://')):
                return
            if candidate not in seen:
                seen.add(candidate)
                urls.append(candidate)

        def visit(value: Any) -> None:
            if isinstance(value, list):
                for child in value:
                    visit(child)
                return
            if not isinstance(value, dict):
                return

            expanded = (
                value.get('expanded_url')
                or value.get('expandedUrl')
                or value.get('unwound_url')
                or value.get('unwoundUrl')
            )
            if expanded:
                add(expanded)
            elif any(key in value for key in ('display_url', 'displayUrl')):
                add(value.get('url'))

            for key in ('urls', 'urlEntities', 'entities', 'extended_entities', 'extendedEntities'):
                if key in value:
                    visit(value[key])

        for container in (
            tweet_data.get('entities'),
            tweet_data.get('urlEntities'),
            tweet_data.get('extendedEntities'),
            (tweet_data.get('legacy') or {}).get('entities')
            if isinstance(tweet_data.get('legacy'), dict) else None,
        ):
            visit(container)

        return urls

    def get_urls_from_posts(self) -> List[Dict[str, Any]]:
        """
        Extract URLs from collected posts for link following.

        Returns list of dicts with url, post_url, platform, author.
        """
        # This would be called after gather() to get URLs for the link follower
        # Implementation depends on when this is called in the pipeline
        return []
