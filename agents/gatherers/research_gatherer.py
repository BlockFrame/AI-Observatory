"""
Research Gatherer - Collects trending papers and research blog posts.

Paper discovery uses the exact report coverage date:
- Hugging Face Daily Papers provides date-addressable historical selections.
- AlphaXiv contributes recent trending papers when its rolling ranking windows
  include the coverage date.
- Research blog posts continue to come from the configured RSS/GraphQL sources.
"""

import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from urllib.parse import urljoin, urlparse

from ..base import BaseGatherer, CollectedItem, deduplicate_items
from ..url_utils import hostname_matches

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / 'scripts'
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from lesswrong_cookie_fetch import DEFAULT_USER_AGENT as LESSWRONG_USER_AGENT
    from lesswrong_cookie_fetch import LessWrongClient
except ImportError:
    LESSWRONG_USER_AGENT = "Wiredframe-Radar/1.0"
    LessWrongClient = None

logger = logging.getLogger(__name__)

# Network timeout (seconds) for research blog feed fetches. feedparser.parse(url) has no
# network timeout, so a single unresponsive feed would hang the whole gatherer (and Phase 1).
RESEARCH_FEED_TIMEOUT = float(os.getenv('RESEARCH_FEED_TIMEOUT', '20'))

RESEARCH_FEED_SOURCE_METADATA = {
    'https://engineering.fb.com/category/ai-research/feed/': {
        'source': 'Meta AI Research',
        'source_index_url': 'https://ai.meta.com/research/',
    },
}


class ResearchGatherer(BaseGatherer):
    """Gathers trending AI papers and research blog posts."""

    # AlphaXiv topic filters relevant to AI.
    CATEGORIES = {
        'cs.AI': 'Artificial Intelligence',
        'cs.LG': 'Machine Learning',
        'cs.CL': 'Computation and Language',
        'cs.CV': 'Computer Vision',
        'cs.NE': 'Neural and Evolutionary Computing',
        'cs.RO': 'Robotics',
        'stat.ML': 'Machine Learning (Statistics)'
    }

    HUGGINGFACE_DAILY_PAPERS_URL = "https://huggingface.co/api/daily_papers"
    ALPHAXIV_FEED_URL = "https://api.alphaxiv.org/papers/v3/feed"
    TREND_RESEARCH_FEED_MARKERS = (
        'feeds.trendmicro.com/trendmicrosimplysecurity',
        'trend micro research'
    )
    OPENAI_RESEARCH_FEED_MARKER = 'openai.com/news/rss.xml'
    OPENAI_RESEARCH_TAGS = {
        'research', 'publication', 'safety', 'safety & alignment', 'security',
    }
    TREND_AI_RELEVANCE_PATTERNS = (
        r'\btrendai\b',
        r'\bai\b',
        r'\bai[- ](?:enabled|augmented|powered|driven|scaled|first)\b',
        r'\bartificial intelligence\b',
        r'\bmachine learning\b',
        r'\bml\b',
        r'\bllm\b',
        r'\bllms\b',
        r'\blarge language model',
        r'\bgenerative ai\b',
        r'\bagentic\b',
        r'\bprompt injection\b',
        r'\bjailbreak',
        r'\bmcp\b',
        r'\bmodel context protocol\b',
        r'\bdeepfake',
        r'\bvibe hacking\b',
    )

    def __init__(
        self,
        config_dir: str = './config',
        data_dir: str = './data',
        lookback_hours: int = 24,
        target_date: Optional[str] = None,
        categories: Optional[List[str]] = None
    ):
        super().__init__(config_dir, data_dir, lookback_hours, target_date)
        self.categories = categories or list(self.CATEGORIES.keys())

        # Load research blog feeds (with optional per-feed routing directives)
        self.research_feed_specs = self.load_config_feeds('research_feeds.txt')
        self.research_feeds = [spec.url for spec in self.research_feed_specs]
        self.research_web_sources = self.load_config_list('research_web_sources.txt')
        self.collection_status: Dict[str, Dict[str, Any]] = {}
        if self.research_feeds:
            logger.info(f"Loaded {len(self.research_feeds)} research blog feeds")
        # Direct session for feeds tagged proxy=off. trust_env=False makes requests
        # ignore ALL_PROXY/HTTPS_PROXY/HTTP_PROXY so these feeds truly bypass the
        # Mullvad tunnel. (An empty proxies={} dict is insufficient: requests still
        # merges env proxies via setdefault.) Default feeds use bare requests.get
        # below and continue to inherit the env proxy, preserving prior behavior.
        self.direct_session = requests.Session()
        self.direct_session.trust_env = False

    @property
    def category(self) -> str:
        return 'research'

    async def gather(self) -> List[CollectedItem]:
        """Gather trending papers and research blogs in parallel."""
        logger.info(f"Starting research collection")
        logger.info(f"Report date: {self.report_date}, Coverage date: {self.coverage_date}")

        # Paper APIs and research blogs are independent, so collect them together.
        paper_task = self._collect_trending_papers()
        research_blog_task = self._collect_research_blogs()
        research_web_task = self._collect_research_web_sources()

        papers, blog_posts, web_posts = await asyncio.gather(
            paper_task, research_blog_task, research_web_task
        )

        all_items = deduplicate_items(papers + blog_posts + web_posts)

        logger.info(
            "Total research items: %s (%s trending papers, %s feed posts, %s web posts)",
            len(all_items),
            len(papers),
            len(blog_posts),
            len(web_posts),
        )

        # Save to file
        self.save_to_file(all_items, f'research_{self.target_date}.json')

        return all_items

    def get_collection_status(self) -> Dict[str, Dict[str, Any]]:
        """Return status for deterministic Research web sources."""
        return self.collection_status

    async def _collect_research_web_sources(self) -> List[CollectedItem]:
        """Collect date-verifiable Research hubs that do not publish feeds."""
        if not self.research_web_sources:
            return []
        self.collection_status = {
            url: {'status': 'pending', 'count': 0, 'error': None}
            for url in self.research_web_sources
        }
        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(None, self._fetch_research_web_source, url)
            for url in self.research_web_sources
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        posts: List[CollectedItem] = []
        for url, result in zip(self.research_web_sources, results):
            if isinstance(result, Exception):
                self.collection_status[url].update({
                    'status': 'failed',
                    'error': f'{type(result).__name__}: {result}',
                })
                logger.error("Research web source failed %s: %s", url, result)
                continue
            posts.extend(result)
        return deduplicate_items(posts)

    def _fetch_research_web_source(self, url: str) -> List[CollectedItem]:
        """Fetch one known Research hub and parse only explicit publication dates."""
        headers = {
            'Accept': 'text/html,application/xhtml+xml',
            'User-Agent': os.environ.get('NEWS_USER_AGENT') or LESSWRONG_USER_AGENT,
        }
        response = requests.get(url, headers=headers, timeout=RESEARCH_FEED_TIMEOUT)
        response.raise_for_status()
        items, candidates = self._extract_research_web_source(url, response.text)
        self.collection_status[url].update({
            'status': 'success',
            'count': len(items),
            'reason_code': 'no_items_in_window' if candidates and not items else None,
            'error': None,
        })
        logger.info(
            "Research web source %s retained %s/%s dated candidates",
            url, len(items), candidates,
        )
        return items

    def _extract_research_web_source(
        self, url: str, html: str,
    ) -> tuple[List[CollectedItem], int]:
        """Route a configured Research hub to its deterministic HTML parser."""
        host = urlparse(url).netloc.lower()
        if host == 'www.anthropic.com':
            return self._extract_anthropic_research(url, html)
        if host == 'arena.ai':
            return self._extract_arena_research(url, html)
        if host == 'epoch.ai':
            return self._extract_epoch_research(url, html)
        raise ValueError(f'No deterministic Research parser registered for {url}')

    def _research_web_item(
        self,
        *,
        source: str,
        source_index_url: str,
        title: str,
        article_url: str,
        published: datetime,
        summary: str = '',
        tags: Optional[List[str]] = None,
    ) -> CollectedItem:
        return CollectedItem(
            id=self.generate_id(article_url, title),
            title=title.strip(),
            content=summary.strip(),
            url=article_url,
            author=source,
            published=published.isoformat(),
            source=source,
            source_type='research_blog',
            tags=tags or [],
            metadata={
                'source_index_url': source_index_url,
                'scraper_type': 'deterministic_html',
            },
            keywords=self.extract_keywords(f'{title} {summary}'),
        )

    @staticmethod
    def _parse_visible_date(value: str) -> Optional[datetime]:
        cleaned = re.sub(r'^Updated\s+', '', (value or '').strip(), flags=re.I)
        if not cleaned:
            return None
        try:
            return date_parser.parse(cleaned, fuzzy=False).replace(tzinfo=None)
        except (ValueError, TypeError, OverflowError):
            return None

    def _retain_web_item(self, item: CollectedItem, items: List[CollectedItem]) -> None:
        published = datetime.fromisoformat(item.published)
        if self.is_in_date_range(published):
            items.append(item)

    def _extract_anthropic_research(
        self, url: str, html: str,
    ) -> tuple[List[CollectedItem], int]:
        soup = BeautifulSoup(html, 'html.parser')
        items: List[CollectedItem] = []
        seen = set()
        candidates = 0
        for anchor in soup.select('a[href]'):
            article_url = urljoin(url, anchor.get('href', '')).split('#')[0]
            path = urlparse(article_url).path
            if article_url in seen or '/research/team/' in path:
                continue
            if not (path.startswith('/research/') or (
                urlparse(url).path.rstrip('/') == '/economic-futures'
                and path.startswith('/news/')
            )):
                continue
            time_element = anchor.find('time')
            published = self._parse_visible_date(
                time_element.get_text(' ', strip=True) if time_element else ''
            )
            if not published:
                continue
            title_element = anchor.select_one(
                '[class*="title"], h1, h2, h3, h4'
            )
            title = title_element.get_text(' ', strip=True) if title_element else ''
            if not title:
                continue
            seen.add(article_url)
            candidates += 1
            subject = anchor.select_one('[class*="subject"]')
            item = self._research_web_item(
                source=(
                    'Anthropic Economic Futures'
                    if urlparse(url).path.rstrip('/') == '/economic-futures'
                    else 'Anthropic Research'
                ),
                source_index_url=url,
                title=title,
                article_url=article_url,
                published=published,
                tags=[subject.get_text(' ', strip=True)] if subject else [],
            )
            self._retain_web_item(item, items)
        return items, candidates

    def _extract_arena_research(
        self, url: str, html: str,
    ) -> tuple[List[CollectedItem], int]:
        soup = BeautifulSoup(html, 'html.parser')
        items: List[CollectedItem] = []
        seen = set()
        candidates = 0
        date_pattern = re.compile(
            r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
            r'(?:uary|ruary|ch|il|e|y|ust|tember|ober|ember|ember)?\s+20\d{2})\b',
            re.I,
        )
        for anchor in soup.select('a[href^="/blog/"]'):
            heading = anchor.find('h3')
            match = date_pattern.search(anchor.get_text(' ', strip=True))
            if not heading or not match:
                continue
            article_url = urljoin(url, anchor['href']).split('#')[0]
            if article_url in seen:
                continue
            published = self._parse_visible_date(match.group(1))
            if not published:
                continue
            seen.add(article_url)
            candidates += 1
            description = anchor.find('p')
            item = self._research_web_item(
                source='Arena Research',
                source_index_url=url,
                title=heading.get_text(' ', strip=True),
                article_url=article_url,
                published=published,
                summary=description.get_text(' ', strip=True) if description else '',
            )
            self._retain_web_item(item, items)
        return items, candidates

    def _extract_epoch_research(
        self, url: str, html: str,
    ) -> tuple[List[CollectedItem], int]:
        soup = BeautifulSoup(html, 'html.parser')
        items: List[CollectedItem] = []
        candidates = 0
        for card in soup.select('.card-article-listing'):
            anchor = card.find('a', href=True)
            badges = [badge.get_text(' ', strip=True) for badge in card.select('.badge-text')]
            published = next(
                (parsed for parsed in map(self._parse_visible_date, badges) if parsed),
                None,
            )
            title_element = card.select_one('.button-text .trim')
            if not anchor or not published or not title_element:
                continue
            candidates += 1
            description = card.select_one('.body-3')
            author = card.select_one('.card-author')
            item = self._research_web_item(
                source='Epoch AI',
                source_index_url=url,
                title=title_element.get_text(' ', strip=True),
                article_url=urljoin(url, anchor['href']).split('#')[0],
                published=published,
                summary=description.get_text(' ', strip=True) if description else '',
                tags=[badges[0]] if badges else [],
            )
            if author:
                item.author = re.sub(r'^By\s+', '', author.get_text(' ', strip=True))
            self._retain_web_item(item, items)
        return items, candidates

    async def _collect_trending_papers(self) -> List[CollectedItem]:
        """Collect and merge Hugging Face Daily Papers and AlphaXiv trends."""
        loop = asyncio.get_running_loop()
        huggingface_future = loop.run_in_executor(
            None, self._fetch_huggingface_daily_papers
        )
        alphaxiv_future = loop.run_in_executor(None, self._fetch_alphaxiv_trending)
        huggingface_papers, alphaxiv_papers = await asyncio.gather(
            huggingface_future, alphaxiv_future
        )

        merged = self._merge_trending_papers(huggingface_papers, alphaxiv_papers)
        max_papers = max(1, int(os.getenv('RESEARCH_TRENDING_MAX_PAPERS', '100')))
        if len(merged) > max_papers:
            logger.info(
                "Limiting merged trending papers from %s to %s",
                len(merged),
                max_papers,
            )
            merged = merged[:max_papers]

        logger.info(
            "Collected %s unique trending papers (%s Hugging Face, %s AlphaXiv)",
            len(merged),
            len(huggingface_papers),
            len(alphaxiv_papers),
        )
        return merged

    def _fetch_huggingface_daily_papers(self) -> List[CollectedItem]:
        """Fetch Hugging Face's curated papers for the exact coverage date."""
        try:
            response = requests.get(
                self.HUGGINGFACE_DAILY_PAPERS_URL,
                params={'date': self.coverage_date},
                headers={
                    'Accept': 'application/json',
                    'User-Agent': os.environ.get('NEWS_USER_AGENT') or LESSWRONG_USER_AGENT,
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.error(
                "Hugging Face Daily Papers request failed for %s: %s",
                self.coverage_date,
                exc,
            )
            return []

        if not isinstance(payload, list):
            logger.error(
                "Hugging Face Daily Papers returned an unexpected payload type: %s",
                type(payload).__name__,
            )
            return []

        papers = []
        for entry in payload:
            item = self._huggingface_entry_to_item(entry)
            if item is not None:
                papers.append(item)

        logger.info(
            "Hugging Face Daily Papers returned %s papers for %s",
            len(papers),
            self.coverage_date,
        )
        return papers

    def _huggingface_entry_to_item(
        self, entry: Dict[str, Any]
    ) -> Optional[CollectedItem]:
        """Convert one Hugging Face daily-paper record to a collected item."""
        if not isinstance(entry, dict):
            logger.warning("Skipping malformed Hugging Face paper record")
            return None

        paper = entry.get('paper')
        if not isinstance(paper, dict):
            paper = entry

        raw_arxiv_id = paper.get('id') or paper.get('arxiv_id')
        if not raw_arxiv_id:
            logger.warning("Skipping Hugging Face paper without an arXiv ID")
            return None
        arxiv_id = self._parse_arxiv_id(str(raw_arxiv_id).strip())

        title = self._clean_text(paper.get('title'))
        if not title:
            logger.warning("Skipping Hugging Face paper %s without a title", arxiv_id)
            return None

        selected_at = (
            paper.get('submittedOnDailyAt')
            or entry.get('submittedOnDailyAt')
            or self.coverage_date
        )
        selected_date = self._source_date(selected_at)
        if selected_date and selected_date != self.coverage_date:
            logger.warning(
                "Skipping Hugging Face paper %s selected on %s, expected %s",
                arxiv_id,
                selected_date,
                self.coverage_date,
            )
            return None

        summary = self._clean_text(
            paper.get('ai_summary') or paper.get('summary') or entry.get('summary')
        )
        authors = self._format_paper_authors(paper.get('authors'))
        keywords = self._string_list(paper.get('ai_keywords'))
        paper_url = f"https://huggingface.co/papers/{arxiv_id}"
        upvotes = paper.get('upvotes', entry.get('upvotes', 0))
        published = self._published_timestamp(selected_at, self.coverage_date)

        return CollectedItem(
            id=self.generate_id(arxiv_id),
            title=title,
            content=summary,
            url=paper_url,
            author=authors,
            published=published,
            source='Hugging Face Papers',
            source_type='research_paper',
            tags=keywords,
            metadata={
                'arxiv_id': arxiv_id,
                'category_name': ', '.join(keywords[:3]),
                'discovery_sources': ['huggingface'],
                'source_urls': {'huggingface': paper_url},
                'huggingface': {
                    'upvotes': upvotes,
                    'selected_at': str(selected_at),
                    'paper_published_at': paper.get('publishedAt'),
                    'github_repo': paper.get('githubRepo'),
                },
            },
            keywords=self.extract_keywords(f"{title} {summary} {' '.join(keywords)}"),
        )

    def _fetch_alphaxiv_trending(self) -> List[CollectedItem]:
        """Fetch AlphaXiv trends whose publication date matches coverage_date."""
        interval = self._alphaxiv_interval_for_coverage()
        if interval is None:
            return []

        page_size = max(1, min(100, int(os.getenv('ALPHAXIV_PAGE_SIZE', '50'))))
        max_pages = max(1, int(os.getenv('ALPHAXIV_MAX_PAGES', '5')))
        sort = os.getenv('ALPHAXIV_SORT', 'Hot')
        papers = []

        for page_number in range(max_pages):
            try:
                response = requests.get(
                    self.ALPHAXIV_FEED_URL,
                    params={
                        'sort': sort,
                        'interval': interval,
                        'pageNum': page_number,
                        'pageSize': page_size,
                        'topics': json.dumps(self.categories),
                    },
                    headers={
                        'Accept': 'application/json',
                        'User-Agent': os.environ.get('NEWS_USER_AGENT') or LESSWRONG_USER_AGENT,
                    },
                    timeout=30,
                )
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:
                logger.error(
                    "AlphaXiv trending request failed on page %s for %s: %s",
                    page_number,
                    self.coverage_date,
                    exc,
                )
                break

            page_records = self._extract_alphaxiv_records(payload)
            if page_records is None:
                logger.error(
                    "AlphaXiv returned an unexpected payload on page %s",
                    page_number,
                )
                break

            for record in page_records:
                item = self._alphaxiv_record_to_item(record)
                if item is not None:
                    papers.append(item)

            if len(page_records) < page_size:
                break

        logger.info(
            "AlphaXiv retained %s trending papers published on %s from its %s window",
            len(papers),
            self.coverage_date,
            interval,
        )
        return papers

    def _alphaxiv_interval_for_coverage(self) -> Optional[str]:
        """Choose the smallest AlphaXiv rolling window containing coverage_date."""
        coverage = datetime.strptime(self.coverage_date, '%Y-%m-%d').date()
        age_days = (datetime.now().date() - coverage).days
        if age_days < 0:
            logger.warning(
                "Skipping AlphaXiv: coverage date %s is in the future",
                self.coverage_date,
            )
            return None
        if age_days < 3:
            return '3 Days'
        if age_days < 7:
            return '7 Days'
        if age_days < 30:
            return '30 Days'
        if age_days < 90:
            return '90 Days'

        logger.warning(
            "Skipping AlphaXiv for %s: its API has no historical snapshots beyond "
            "the 90-day ranking window; Hugging Face remains available for backfill",
            self.coverage_date,
        )
        return None

    @staticmethod
    def _extract_alphaxiv_records(payload: Any) -> Optional[List[Dict[str, Any]]]:
        """Return paper records from the known AlphaXiv response envelopes."""
        if isinstance(payload, list):
            return [record for record in payload if isinstance(record, dict)]
        if not isinstance(payload, dict):
            return None

        for key in ('papers', 'results', 'data'):
            records = payload.get(key)
            if isinstance(records, list):
                return [record for record in records if isinstance(record, dict)]
            if isinstance(records, dict):
                nested = records.get('papers') or records.get('results')
                if isinstance(nested, list):
                    return [record for record in nested if isinstance(record, dict)]
        return None

    def _alphaxiv_record_to_item(
        self, paper: Dict[str, Any]
    ) -> Optional[CollectedItem]:
        """Convert and date-filter one AlphaXiv feed record."""
        raw_arxiv_id = paper.get('universal_paper_id') or paper.get('arxiv_id')
        if not raw_arxiv_id:
            logger.warning("Skipping AlphaXiv paper without an arXiv ID")
            return None
        arxiv_id = self._parse_arxiv_id(str(raw_arxiv_id).strip())

        publication_value = (
            paper.get('publication_date') or paper.get('first_publication_date')
        )
        publication_date = self._source_date(publication_value)
        if publication_date != self.coverage_date:
            return None

        title = self._clean_text(paper.get('title'))
        if not title:
            logger.warning("Skipping AlphaXiv paper %s without a title", arxiv_id)
            return None

        raw_summary = paper.get('paper_summary')
        if isinstance(raw_summary, dict):
            raw_summary = raw_summary.get('summary')
        summary = self._clean_text(raw_summary or paper.get('abstract'))
        authors = self._format_paper_authors(paper.get('authors'))
        topics = self._string_list(paper.get('topics'))
        metrics = paper.get('metrics')
        if not isinstance(metrics, dict):
            metrics = {}
        paper_url = f"https://www.alphaxiv.org/abs/{arxiv_id}"

        return CollectedItem(
            id=self.generate_id(arxiv_id),
            title=title,
            content=summary,
            url=paper_url,
            author=authors,
            published=self._published_timestamp(
                publication_value, self.coverage_date
            ),
            source='AlphaXiv Trending',
            source_type='research_paper',
            tags=topics,
            metadata={
                'arxiv_id': arxiv_id,
                'category_name': ', '.join(topics[:3]),
                'discovery_sources': ['alphaxiv'],
                'source_urls': {'alphaxiv': paper_url},
                'alphaxiv': {
                    'public_total_votes': metrics.get('public_total_votes', 0),
                    'visits_count': metrics.get('visits_count', 0),
                    'github_url': paper.get('github_url'),
                    'github_stars': paper.get('github_stars'),
                    'ranking_interval': self._alphaxiv_interval_for_coverage(),
                },
            },
            keywords=self.extract_keywords(f"{title} {summary} {' '.join(topics)}"),
        )

    def _merge_trending_papers(
        self,
        huggingface_papers: List[CollectedItem],
        alphaxiv_papers: List[CollectedItem],
    ) -> List[CollectedItem]:
        """Deduplicate cross-platform papers by arXiv ID and merge provenance."""
        merged = []
        by_arxiv_id = {}

        for item in huggingface_papers + alphaxiv_papers:
            arxiv_id = str(item.metadata.get('arxiv_id', '')).lower()
            if not arxiv_id:
                logger.warning("Skipping research paper without deduplication ID")
                continue

            existing = by_arxiv_id.get(arxiv_id)
            if existing is None:
                by_arxiv_id[arxiv_id] = item
                merged.append(item)
                continue

            existing_sources = existing.metadata.setdefault('discovery_sources', [])
            for source in item.metadata.get('discovery_sources', []):
                if source not in existing_sources:
                    existing_sources.append(source)
            existing.metadata.setdefault('source_urls', {}).update(
                item.metadata.get('source_urls', {})
            )
            for source_key in ('huggingface', 'alphaxiv'):
                if source_key in item.metadata:
                    existing.metadata[source_key] = item.metadata[source_key]

            existing.tags = list(dict.fromkeys(existing.tags + item.tags))
            existing.keywords = list(dict.fromkeys(existing.keywords + item.keywords))
            if len(item.content) > len(existing.content):
                existing.content = item.content
            if existing.author in ('', 'Unknown') and item.author:
                existing.author = item.author
            if len(existing_sources) > 1:
                existing.source = 'Hugging Face Papers + AlphaXiv'

        return merged

    @staticmethod
    def _clean_text(value: Any) -> str:
        """Normalize plain or HTML-bearing API text fields."""
        if not isinstance(value, str):
            return ''
        text = re.sub(r'<[^>]+>', ' ', value)
        return ' '.join(text.split())

    @classmethod
    def _format_paper_authors(cls, value: Any) -> str:
        """Normalize author strings and common API author-object shapes."""
        if isinstance(value, str):
            return cls._clean_text(value) or 'Unknown'
        if not isinstance(value, list):
            return 'Unknown'

        names = []
        for author in value:
            if isinstance(author, str):
                name = cls._clean_text(author)
            elif isinstance(author, dict):
                name = cls._clean_text(
                    author.get('name')
                    or author.get('full_name')
                    or ' '.join(
                        part
                        for part in (
                            author.get('first_name'),
                            author.get('last_name'),
                        )
                        if isinstance(part, str)
                    )
                )
            else:
                name = ''
            if name:
                names.append(name)
        return ', '.join(names) or 'Unknown'

    @classmethod
    def _string_list(cls, value: Any) -> List[str]:
        """Normalize tags/topics from strings or API objects."""
        if isinstance(value, str):
            cleaned = cls._clean_text(value)
            return [cleaned] if cleaned else []
        if not isinstance(value, list):
            return []

        values = []
        for entry in value:
            if isinstance(entry, str):
                cleaned = cls._clean_text(entry)
            elif isinstance(entry, dict):
                cleaned = cls._clean_text(
                    entry.get('name') or entry.get('id') or entry.get('label')
                )
            else:
                cleaned = ''
            if cleaned and cleaned not in values:
                values.append(cleaned)
        return values

    @staticmethod
    def _source_date(value: Any) -> Optional[str]:
        """Extract a YYYY-MM-DD source date from ISO-compatible API values."""
        if not isinstance(value, str) or not value.strip():
            return None
        normalized = value.strip().replace('Z', '+00:00')
        try:
            return datetime.fromisoformat(normalized).date().isoformat()
        except ValueError:
            logger.warning("Unable to parse paper source date: %r", value)
            return None

    @classmethod
    def _published_timestamp(cls, value: Any, fallback_date: str) -> str:
        """Return an ISO timestamp while preserving the source date semantics."""
        if isinstance(value, str) and value.strip():
            normalized = value.strip().replace('Z', '+00:00')
            try:
                return datetime.fromisoformat(normalized).isoformat()
            except ValueError:
                logger.warning("Unable to parse paper timestamp: %r", value)
        return f"{fallback_date}T12:00:00"

    async def _collect_research_blogs(self) -> List[CollectedItem]:
        """Collect posts from research blog RSS feeds.

        Routes LessWrong to GraphQL API (for date-range queries) while using
        RSS for other research feeds.
        """
        if not self.research_feeds:
            logger.info("No research blog feeds configured")
            return []

        logger.info(f"Collecting from {len(self.research_feeds)} research blog feeds")

        loop = asyncio.get_event_loop()

        # Separate LessWrong from other feeds (LessWrong needs GraphQL for date-range queries)
        lesswrong_feeds = [
            spec for spec in self.research_feed_specs
            if hostname_matches(spec.url, "lesswrong.com")
        ]
        other_feeds = [
            spec for spec in self.research_feed_specs
            if not hostname_matches(spec.url, "lesswrong.com")
        ]

        all_posts = []
        seen_urls = set()

        # Fetch LessWrong via GraphQL API (only need to call once, not per-feed)
        if lesswrong_feeds:
            logger.info("Using GraphQL API for LessWrong (RSS doesn't support date-range queries)")
            try:
                lesswrong_posts = await loop.run_in_executor(None, self._fetch_lesswrong_graphql)
                for post in lesswrong_posts:
                    if post.url not in seen_urls:
                        seen_urls.add(post.url)
                        all_posts.append(post)
            except Exception as e:
                logger.error(f"Failed to fetch LessWrong via GraphQL: {e}")

        # Fetch other feeds via RSS (existing behavior)
        if other_feeds:
            tasks = [
                loop.run_in_executor(None, self._fetch_research_feed, spec)
                for spec in other_feeds
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for spec, result in zip(other_feeds, results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to fetch research feed {spec.url}: {result}")
                    continue

                for post in result:
                    if post.url not in seen_urls:
                        seen_urls.add(post.url)
                        all_posts.append(post)

        logger.info(f"Collected {len(all_posts)} posts from research blogs")
        return all_posts

    def _fetch_research_feed(self, feed) -> List[CollectedItem]:
        """Fetch and parse a research blog RSS feed.

        Accepts a FeedSpec (preferred) or a bare URL string. Feeds tagged
        proxy=off bypass any ambient *_PROXY env (e.g. the Mullvad tunnel) by
        using a trust_env=False session that fetches direct.
        """
        posts = []

        # Accept either a FeedSpec or a plain URL for backward compatibility.
        feed_url = getattr(feed, 'url', feed)
        use_proxy = getattr(feed, 'use_proxy', None)

        try:
            logger.debug(
                f"Fetching research feed: {feed_url} "
                f"(proxy={'direct' if use_proxy is False else 'default'})"
            )
            # Fetch with an explicit timeout (feedparser.parse(url) has none) so one
            # unresponsive feed can't hang the gatherer. A browser-ish UA avoids
            # 403s from feeds like Nature.
            headers = {'User-Agent': os.environ.get('NEWS_USER_AGENT') or LESSWRONG_USER_AGENT}
            # proxy=off -> use the trust_env=False session so requests ignores all
            # ambient *_PROXY env vars (incl. ALL_PROXY) and fetches direct.
            # Otherwise use the module-level requests (inherits env, default behavior).
            requester = self.direct_session if use_proxy is False else requests
            response = requester.get(
                feed_url, headers=headers, timeout=RESEARCH_FEED_TIMEOUT,
                allow_redirects=True
            )
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            if feed.bozo:
                # CharacterEncodingOverride is benign - feedparser handles it correctly
                exc = feed.bozo_exception
                if exc and 'CharacterEncodingOverride' in type(exc).__name__:
                    logger.debug(f"Feed encoding override for {feed_url}: {exc}")
                else:
                    logger.warning(f"Feed warning for {feed_url}: {exc}")

            feed_title = feed.feed.get('title', 'Research Blog')
            source_metadata = RESEARCH_FEED_SOURCE_METADATA.get(
                feed_url.rstrip('/') + '/', {}
            )
            is_trend_feed = self._is_trend_research_feed(feed_url, feed_title)
            is_openai_research_feed = self.OPENAI_RESEARCH_FEED_MARKER in feed_url.lower()
            trend_filtered = 0
            trend_retained = 0

            for entry in feed.entries:
                try:
                    # Parse publication date
                    pub_date = self._parse_feed_date(
                        entry.get('published_parsed') or entry.get('updated_parsed')
                    )

                    # An undated/unparseable entry can't be placed in a specific
                    # day's coverage window; skip it visibly rather than silently.
                    if pub_date is None:
                        logger.warning(
                            f"Skipping entry with missing/unparseable date from "
                            f"{feed_url}: {entry.get('title', 'No Title')!r}"
                        )
                        continue

                    # Skip if outside date range
                    if not self.is_in_date_range(pub_date):
                        continue

                    # Extract content
                    content = ''
                    if hasattr(entry, 'content'):
                        content = entry.content[0].value
                    elif hasattr(entry, 'summary'):
                        content = entry.summary
                    elif hasattr(entry, 'description'):
                        content = entry.description

                    # Strip HTML tags from content
                    content_text = re.sub(r'<[^>]+>', '', content)
                    # Normalize whitespace
                    content_text = ' '.join(content_text.split())

                    title = entry.get('title', 'No Title')
                    url = entry.get('link', '')
                    author = entry.get('author', entry.get('dc_creator', 'Unknown'))
                    tags = [tag.term for tag in entry.get('tags', []) if getattr(tag, 'term', None)]

                    if (
                        is_openai_research_feed
                        and not self._is_openai_research_entry(tags)
                    ):
                        continue

                    if is_trend_feed and not self._is_trend_ai_relevant(title, content_text, tags):
                        trend_filtered += 1
                        continue

                    # Handle author as list (some feeds)
                    if isinstance(author, list):
                        author = ', '.join(author)

                    post = CollectedItem(
                        id=self.generate_id(url, title),
                        title=title,
                        content=content_text,
                        url=url,
                        author=author,
                        published=pub_date.isoformat(),
                        source=(
                            'OpenAI Research'
                            if is_openai_research_feed
                            else source_metadata.get('source', feed_title)
                        ),
                        source_type='research_blog',
                        tags=tags,
                        metadata={
                            'feed_url': feed_url,
                            'source_index_url': (
                                'https://openai.com/it-IT/research/'
                                if is_openai_research_feed
                                else source_metadata.get('source_index_url', '')
                            ),
                            'raw_summary': entry.get('summary', '')[:500]
                        },
                        keywords=self.extract_keywords(f"{title} {content_text}")
                    )

                    posts.append(post)
                    if is_trend_feed:
                        trend_retained += 1

                except Exception as e:
                    logger.error(f"Error processing entry from {feed_url}: {e}")

            if is_trend_feed:
                logger.info(
                    "Trend Micro AI/security filter retained %s posts and filtered %s posts",
                    trend_retained,
                    trend_filtered
                )
            logger.info(f"Collected {len(posts)} posts from {feed_title}")

        except Exception as e:
            logger.error(f"Error fetching research feed {feed_url}: {e}")

        return posts

    def _is_trend_research_feed(self, feed_url: str, feed_title: str = '') -> bool:
        """Identify Trend Micro's broad threat-research feed for source-specific filtering."""
        marker_text = f"{feed_url} {feed_title}".lower()
        return any(marker in marker_text for marker in self.TREND_RESEARCH_FEED_MARKERS)

    def _is_openai_research_entry(self, tags: List[str]) -> bool:
        """Keep only the research-relevant subset of OpenAI's canonical feed."""
        return bool({tag.strip().lower() for tag in tags} & self.OPENAI_RESEARCH_TAGS)

    def _is_trend_ai_relevant(self, title: str, content: str, tags: List[str]) -> bool:
        """Keep Trend threat research only when it intersects AI/security topics."""
        text = f"{title} {content} {' '.join(tags)}".lower()
        return any(re.search(pattern, text) for pattern in self.TREND_AI_RELEVANCE_PATTERNS)

    def _fetch_lesswrong_graphql(self) -> List[CollectedItem]:
        """Fetch posts from LessWrong using GraphQL API for date-range queries.

        The RSS feed only contains the ~10-20 most recent posts, which scroll off
        within hours. The GraphQL API allows date-range queries to fetch historical
        posts that are no longer in the RSS feed.
        """
        posts = []

        # GraphQL query for posts within date range
        # LessWrong uses 'after' and 'before' as date strings (YYYY-MM-DD)
        query = '''
        query GetPosts($after: Date, $before: Date) {
          posts(input: {
            terms: {
              view: "new",
              after: $after,
              before: $before,
              limit: 100
            }
          }) {
            results {
              _id
              title
              slug
              postedAt
              contents {
                html
              }
              user {
                displayName
                username
              }
              baseScore
              voteCount
            }
          }
        }
        '''

        # Use coverage_date as 'after' and report_date as 'before' (exclusive)
        variables = {
            "after": self.coverage_date,
            "before": self.report_date
        }

        try:
            logger.info(f"Fetching LessWrong posts via GraphQL (coverage: {self.coverage_date})")
            data = self._execute_lesswrong_graphql(query, variables)

            if 'errors' in data:
                logger.error(f"LessWrong GraphQL errors: {data['errors']}")
                return posts

            results = data.get('data', {}).get('posts', {}).get('results', [])
            logger.info(f"LessWrong GraphQL returned {len(results)} posts")

            for post_data in results:
                try:
                    post_id = post_data.get('_id', '')
                    slug = post_data.get('slug', '')
                    title = post_data.get('title', 'No Title')

                    # Build URL: https://www.lesswrong.com/posts/{_id}/{slug}
                    url = f"https://www.lesswrong.com/posts/{post_id}/{slug}"

                    # Parse posted date
                    posted_at = post_data.get('postedAt', '')
                    if posted_at:
                        # Parse ISO format datetime
                        pub_date = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
                        # Convert to local time for consistency
                        pub_date = pub_date.astimezone().replace(tzinfo=None)
                    else:
                        pub_date = datetime.now()

                    # Extract content from HTML
                    content_html = ''
                    contents = post_data.get('contents')
                    if contents and isinstance(contents, dict):
                        content_html = contents.get('html', '')

                    # Strip HTML tags from content
                    content_text = re.sub(r'<[^>]+>', '', content_html)
                    content_text = ' '.join(content_text.split())
                    # Truncate for storage
                    if len(content_text) > 2000:
                        content_text = content_text[:2000] + '...'

                    # Extract author
                    user = post_data.get('user', {})
                    if user:
                        author = user.get('displayName', user.get('username', 'Unknown'))
                    else:
                        author = 'Unknown'

                    post = CollectedItem(
                        id=self.generate_id(url, title),
                        title=title,
                        content=content_text,
                        url=url,
                        author=author,
                        published=pub_date.isoformat(),
                        source='LessWrong',
                        source_type='research_blog',
                        tags=[],
                        metadata={
                            'lesswrong_id': post_id,
                            'slug': slug,
                            'base_score': post_data.get('baseScore', 0),
                            'vote_count': post_data.get('voteCount', 0)
                        },
                        keywords=self.extract_keywords(f"{title} {content_text}")
                    )

                    posts.append(post)

                except Exception as e:
                    logger.error(f"Error processing LessWrong post: {e}")

            logger.info(f"Collected {len(posts)} posts from LessWrong (GraphQL)")

        except requests.exceptions.RequestException as e:
            logger.error(f"LessWrong GraphQL request failed: {e}")
        except Exception as e:
            logger.error(f"Error fetching LessWrong GraphQL: {e}")

        return posts

    def _execute_lesswrong_graphql(self, query: str, variables: dict) -> dict:
        """Prefer the cookie-aware client, but keep direct GraphQL as a fallback."""
        if LessWrongClient is not None:
            try:
                logger.info("Using LessWrongClient cookie bypass for LessWrong GraphQL")
                return LessWrongClient().graphql(query, variables)
            except Exception as e:
                logger.warning(
                    "LessWrongClient failed (%s); falling back to direct GraphQL request",
                    e,
                )
        else:
            logger.warning("LessWrongClient unavailable; falling back to direct GraphQL request")

        response = requests.post(
            'https://www.lesswrong.com/graphql',
            json={'query': query, 'variables': variables},
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Origin': 'https://www.lesswrong.com',
                'Referer': 'https://www.lesswrong.com/',
                'User-Agent': os.environ.get('NEWS_USER_AGENT') or LESSWRONG_USER_AGENT,
            },
            timeout=45
        )
        response.raise_for_status()
        return response.json()

    def _parse_feed_date(self, date_struct) -> Optional[datetime]:
        """Parse date from feedparser date structure.

        feedparser returns time.struct_time in UTC. We convert to local time
        for comparison with our local-time coverage window.

        Returns None when the date is missing or unparseable, so the caller can
        log and skip the entry explicitly. (A fallback to datetime.now() would
        land on the report day, outside the coverage window — the day before —
        and silently drop the entry with no signal.)
        """
        if not date_struct:
            return None

        try:
            # feedparser returns time.struct_time in UTC
            if hasattr(date_struct, 'tm_year'):
                from datetime import timezone
                # Create UTC datetime
                utc_dt = datetime(*date_struct[:6], tzinfo=timezone.utc)
                # Convert to local time (naive datetime for comparison)
                local_dt = utc_dt.astimezone().replace(tzinfo=None)
                return local_dt
        except Exception as e:
            logger.warning(f"Failed to parse feed date: {e}")

        return None

    def _parse_arxiv_id(self, link: str) -> str:
        """Extract arXiv ID from link or OAI identifier.

        Handles both formats:
        - API/URL format: http://arxiv.org/abs/2601.02514v1 -> 2601.02514
        - RSS OAI format: oai:arXiv.org:2601.02514v1 -> 2601.02514
        """
        try:
            if '/abs/' in link:
                # API format: http://arxiv.org/abs/2601.02514v1
                arxiv_id = link.split('/abs/')[-1]
            elif 'arXiv.org:' in link:
                # RSS OAI format: oai:arXiv.org:2601.02514v1
                arxiv_id = link.split('arXiv.org:')[-1]
            else:
                arxiv_id = link
            # Remove version suffix (v1, v2, etc.)
            if 'v' in arxiv_id and arxiv_id.split('v')[-1].isdigit():
                arxiv_id = arxiv_id.rsplit('v', 1)[0]
            return arxiv_id
        except:
            return link
