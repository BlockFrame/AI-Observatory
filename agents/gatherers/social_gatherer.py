"""
Social Gatherer - Collects posts from Twitter/X.

Twitter uses TwitterAPI.io (paid).
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

# TwitterAPI.io configuration
TWITTERAPI_IO_KEY = os.getenv('TWITTERAPI_IO_KEY', '')
TWITTERAPI_IO_BASE = "https://api.twitterapi.io"


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

        # TwitterAPI.io usage accounting (surfaced in the end-of-run cost summary)
        self._twitter_calls = 0          # billable API requests issued
        self._twitter_tweets_billed = 0  # raw tweets returned (TwitterAPI.io bills per tweet)

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
        if not self.twitter_users or not TWITTERAPI_IO_KEY:
            self.collection_status['twitter']['status'] = 'skipped'
            self.collection_status['twitter']['error'] = 'No API key' if not TWITTERAPI_IO_KEY else 'No accounts configured'

        # Collect from Twitter in parallel
        with ThreadPoolExecutor(max_workers=6) as executor:
            tasks = []

            # Twitter collection
            if self.twitter_users and TWITTERAPI_IO_KEY:
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
        """Collect tweets from configured users via TwitterAPI.io."""
        if not TWITTERAPI_IO_KEY:
            logger.warning("TwitterAPI.io key not configured - skipping Twitter")
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

        # Surface TwitterAPI.io usage + balance in the end-of-run cost summary.
        try:
            from ..cost_tracker import get_tracker
            balance = self._fetch_twitter_balance()
            # TwitterAPI.io bills ~$0.15 / 1000 tweets; credits are $1 / 100,000 units.
            logger.info(
                f"TwitterAPI.io usage: {self._twitter_calls} calls, "
                f"{self._twitter_tweets_billed} tweets billed; recharge_credits={balance}"
            )
            get_tracker().record_external_api(
                "TwitterAPI.io (Twitter)",
                calls=self._twitter_calls,
                items=self._twitter_tweets_billed,
                balance=balance,
                balance_usd=(balance / 100000) if balance is not None else None,
                est_cost_usd=round(self._twitter_tweets_billed * 0.15 / 1000, 4),
            )
        except Exception as e:  # never let reporting break collection
            logger.debug(f"Could not record TwitterAPI.io usage: {e}")

        return all_tweets

    def _fetch_twitter_balance(self) -> Optional[int]:
        """Best-effort TwitterAPI.io recharge-credit balance (free /oapi/my/info endpoint)."""
        if not TWITTERAPI_IO_KEY:
            return None
        try:
            resp = requests.get(
                f"{TWITTERAPI_IO_BASE}/oapi/my/info",
                headers={"X-API-Key": TWITTERAPI_IO_KEY},
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json().get("recharge_credits")
            logger.warning(f"TwitterAPI.io balance probe returned HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"Could not fetch TwitterAPI.io balance: {e}")
        return None

    def _twitter_search(self, usernames: List[str]) -> List[CollectedItem]:
        """Use Twitter advanced search to collect from multiple users."""
        all_tweets = []
        failed_chunks = 0

        if not usernames:
            return []

        # Build search query chunks (max ~25 users per query)
        max_users = 25
        chunks = [usernames[i:i + max_users] for i in range(0, len(usernames), max_users)]

        # Format dates for search
        since_date = self.start_time.strftime('%Y-%m-%d')
        until_date = (self.end_time + timedelta(days=1)).strftime('%Y-%m-%d')

        headers = {
            "X-API-Key": TWITTERAPI_IO_KEY,
            "Content-Type": "application/json"
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
                    params = {"query": query, "queryType": "Latest"}
                    if cursor:
                        params["cursor"] = cursor

                    response = requests.get(
                        f"{TWITTERAPI_IO_BASE}/twitter/tweet/advanced_search",
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
                        break

                    # TwitterAPI.io bills per tweet returned.
                    self._twitter_tweets_billed += len(tweets_data)

                    for tweet_data in tweets_data:
                        try:
                            item = self._parse_twitter_tweet(tweet_data)
                            if item and self.is_in_date_range(datetime.fromisoformat(item.published)):
                                all_tweets.append(item)
                        except Exception as e:
                            logger.error(f"Error parsing tweet: {e}")

                    # Pagination
                    if not data.get('has_next_page', False) or not data.get('next_cursor', ''):
                        break

                    cursor = data['next_cursor']
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

        # Parse date
        try:
            pub_date = parsedate_to_datetime(created_at)
            if pub_date.tzinfo:
                pub_date = pub_date.replace(tzinfo=None)
        except:
            try:
                pub_date = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%S.%fZ')
            except:
                pub_date = datetime.now()

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

    def get_urls_from_posts(self) -> List[Dict[str, Any]]:
        """
        Extract URLs from collected posts for link following.

        Returns list of dicts with url, post_url, platform, author.
        """
        # This would be called after gather() to get URLs for the link follower
        # Implementation depends on when this is called in the pipeline
        pass
