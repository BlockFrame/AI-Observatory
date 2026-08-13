import os
import json
import logging
import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..base import BaseGatherer, CollectedItem, deduplicate_items, extract_json_str
from ..llm_client import AnthropicClient

logger = logging.getLogger(__name__)

class WebScraperGatherer(BaseGatherer):
    """
    Gatherer that uses LLMs to scrape modern, JS-heavy web pages for the latest announcements.
    Used for sites that lack RSS feeds (e.g., Anthropic, Meta AI, Cursor, etc.).
    """

    def __init__(self, *args, llm_client: Optional[AnthropicClient] = None, prompt_accessor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.sources_file = Path(self.config_dir) / 'web_scraper_sources.txt'
        self.llm_client = llm_client or AnthropicClient()
        self.prompt_accessor = prompt_accessor
        self.collection_status: Dict[str, Dict[str, Any]] = {}
        
        # We only want one latest article per site per run
        self.max_articles_per_site = 1
        # Deterministic parsers can safely retain every dated publication in
        # the coverage window without multiplying LLM cost.
        self.max_deterministic_articles_per_site = 5
        self._last_extract_candidates = 0
        self._last_date_parse_failures = 0
        self._last_out_of_window = 0
        self._last_extract_error: Optional[str] = None
        self._last_extract_completed = False

    @property
    def category(self) -> str:
        # We inject these as "news" items so they flow through the same pipeline
        return "news"

    def _clean_html(self, html: str) -> str:
        """Strip unnecessary tags to save LLM tokens."""
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove script and style elements
        for script in soup(["script", "style", "noscript", "svg", "path", "nav", "footer"]):
            script.decompose()
            
        text = soup.get_text(separator=' ', strip=True)
        # Collapse multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Truncate to reasonable length (e.g., first 50,000 characters)
        return text[:50000]

    async def _fetch_html(self, url: str) -> Optional[str]:
        """Fetch raw HTML using requests (run in a thread)."""
        import requests
        import asyncio
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }
        try:
            def fetch():
                response = requests.get(url, headers=headers, timeout=15.0)
                response.raise_for_status()
                return response.text
                
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    async def _extract_news_with_llm(self, url: str, text: str) -> List[CollectedItem]:
        """Use LLM to extract all relevant news articles from text."""
        
        system_prompt = """You are an expert web scraper. You will be given the raw text content of a company's news/blog webpage or a newsletter.
Your job is to identify at most the 5 most recent news articles, announcements, or blog posts listed on the page.

Return ONLY a JSON array of objects. Each object must have the following keys:
- "title": The title of the article.
- "url": The FULL absolute URL to the article (resolve relative paths if necessary based on the base domain).
- "date": The publication date in YYYY-MM-DD format (if visible, otherwise output "").
- "summary": A brief 1-sentence summary of what it's about.

Do not include any other text, markdown formatting, or preamble. Just the JSON array of objects. If no articles are found, return []"""

        user_message = f"Base URL: {url}\n\nWebpage Text:\n{text}"
        self._last_extract_candidates = 0
        self._last_date_parse_failures = 0
        self._last_out_of_window = 0
        self._last_extract_error = None
        self._last_extract_completed = False

        try:
            response = self.llm_client.call(
                messages=[{"role": "user", "content": user_message}],
                system=system_prompt,
                temperature=0.0,
                max_tokens=4096
            )
            
            json_str = extract_json_str(response.content)
            try:
                data_list = json.loads(json_str)
            except json.JSONDecodeError as parse_error:
                # Preserve complete objects when the provider truncates the
                # final array element. Dropping the whole page turned several
                # otherwise useful scrapes into zero results in CI.
                data_list = self._recover_complete_json_objects(json_str)
                if not data_list:
                    raise parse_error
                logger.warning(
                    f"Recovered {len(data_list)} complete article objects from "
                    f"truncated JSON for {url}"
                )
            
            if not isinstance(data_list, list):
                # Fallback if it returned a single object
                if isinstance(data_list, dict):
                    data_list = [data_list]
                else:
                    logger.error(f"LLM returned unexpected JSON format for {url}: {data_list}")
                    self._last_extract_error = 'LLM returned an unexpected JSON shape'
                    return []

            self._last_extract_candidates = len(data_list)
            self._last_extract_completed = True
                    
            extracted_items = []
            
            for data in data_list:
                if not data.get("title") or not data.get("url"):
                    continue
                    
                article_url = data["url"]
                if article_url.startswith('/'):
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    article_url = f"{parsed.scheme}://{parsed.netloc}{article_url}"
                    
                item_id = self.generate_id(article_url)
                
                pub_date = data.get("date", "")
                try:
                    dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    if dt.tzinfo is None:
                        # Assume UTC if no timezone provided
                        from datetime import timezone
                        dt = dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    # If parsing fails, skip this item as we can't verify its date
                    self._last_date_parse_failures += 1
                    logger.warning(f"Could not parse date {pub_date} for {article_url}")
                    continue
                    
                # Filter by date range (ensure it matches the run's coverage date)
                # self.start_time and self.end_time are timezone-naive in the orchestrator,
                # so we compare naive datetimes (assuming UTC for simplicity in this context)
                dt_naive = dt.replace(tzinfo=None)
                if not (self.start_time <= dt_naive <= self.end_time):
                    self._last_out_of_window += 1
                    logger.info(f"Skipping {article_url}: article date {dt_naive} is outside coverage window ({self.start_time} to {self.end_time})")
                    continue
                
                extracted_items.append(CollectedItem(
                    id=item_id,
                    title=data["title"],
                    content=data.get("summary", ""),
                    url=article_url,
                    author="",
                    published=dt.isoformat(),
                    source=url,
                    source_type="web_scraper",
                    metadata={"scraper_type": "llm_html"}
                ))
                
            return extracted_items[:self.max_articles_per_site]
            
        except Exception as e:
            self._last_extract_error = f"{type(e).__name__}: {e}"
            logger.error(f"LLM extraction failed for {url}: {e}")
            return []

    def _build_deterministic_item(
        self,
        *,
        source: str,
        title: str,
        article_url: str,
        published: datetime,
        summary: str,
    ) -> CollectedItem:
        """Normalize a dated article extracted without an LLM."""
        return CollectedItem(
            id=self.generate_id(article_url),
            title=title,
            content=summary,
            url=article_url,
            author="",
            published=published.isoformat(),
            source=source,
            source_type="web_scraper",
            metadata={
                "scraper_type": "deterministic_html",
                "source_group": "Tech & Media",
            },
            keywords=self.extract_keywords(f"{title} {summary}"),
        )

    def _extract_artificial_analysis(self, url: str, html: str) -> List[CollectedItem]:
        """Extract dated cards from Artificial Analysis' server-rendered index."""
        soup = BeautifulSoup(html, "html.parser")
        items: List[CollectedItem] = []
        seen_urls = set()
        for anchor in soup.select('a[href^="/articles/"]'):
            heading = anchor.find(["h2", "h3"])
            if not heading:
                continue
            article_url = urljoin(url, anchor.get("href", ""))
            if not article_url or article_url in seen_urls:
                continue
            text = anchor.get_text(" ", strip=True)
            date_match = re.search(
                r"\b(January|February|March|April|May|June|July|August|"
                r"September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
                text,
            )
            if not date_match:
                self._last_date_parse_failures += 1
                continue
            published = datetime.strptime(date_match.group(0), "%B %d, %Y")
            seen_urls.add(article_url)
            self._last_extract_candidates += 1
            if not self.is_in_date_range(published):
                self._last_out_of_window += 1
                continue
            title = heading.get_text(" ", strip=True)
            summary = text.replace(title, "", 1).replace(date_match.group(0), "", 1).strip()
            items.append(self._build_deterministic_item(
                source="Artificial Analysis",
                title=title,
                article_url=article_url,
                published=published,
                summary=summary,
            ))
        return items[:self.max_deterministic_articles_per_site]

    async def _extract_aleph_alpha(self, url: str, html: str) -> List[CollectedItem]:
        """Follow Aleph Alpha cards and validate each article's canonical date."""
        soup = BeautifulSoup(html, "html.parser")
        candidate_urls = []
        for anchor in soup.select('a[href*="/en/blog/"]'):
            article_url = urljoin(url, anchor.get("href", ""))
            if article_url.rstrip("/") == url.rstrip("/") or article_url in candidate_urls:
                continue
            candidate_urls.append(article_url)
            if len(candidate_urls) >= 5:
                break

        items: List[CollectedItem] = []
        for article_url in candidate_urls:
            article_html = await self._fetch_html(article_url)
            if not article_html:
                continue
            article = BeautifulSoup(article_html, "html.parser")
            heading = article.find("h1")
            time_element = article.find("time", attrs={"datetime": True})
            if not heading or not time_element:
                self._last_date_parse_failures += 1
                continue
            try:
                published = datetime.fromisoformat(time_element["datetime"][:10])
            except (TypeError, ValueError):
                self._last_date_parse_failures += 1
                continue
            self._last_extract_candidates += 1
            if not self.is_in_date_range(published):
                self._last_out_of_window += 1
                continue
            description = article.find("meta", attrs={"name": "description"})
            summary = description.get("content", "").strip() if description else ""
            items.append(self._build_deterministic_item(
                source="Aleph Alpha",
                title=heading.get_text(" ", strip=True),
                article_url=article_url,
                published=published,
                summary=summary,
            ))
            if len(items) >= self.max_deterministic_articles_per_site:
                break
        return items

    async def _extract_deterministic_news(
        self, url: str, html: str,
    ) -> Optional[List[CollectedItem]]:
        """Return None for generic pages, or deterministically parsed items."""
        self._last_extract_candidates = 0
        self._last_date_parse_failures = 0
        self._last_out_of_window = 0
        self._last_extract_error = None
        self._last_extract_completed = True
        if url.rstrip("/") == "https://artificialanalysis.ai/articles":
            return self._extract_artificial_analysis(url, html)
        if url.rstrip("/") == "https://aleph-alpha.com/en/blog":
            return await self._extract_aleph_alpha(url, html)
        self._last_extract_completed = False
        return None

    @staticmethod
    def _recover_complete_json_objects(content: str) -> List[Dict[str, Any]]:
        """Recover complete top-level objects from a truncated JSON array."""
        decoder = json.JSONDecoder()
        recovered: List[Dict[str, Any]] = []
        cursor = content.find('[')
        if cursor < 0:
            return recovered
        cursor += 1
        while cursor < len(content):
            object_start = content.find('{', cursor)
            if object_start < 0:
                break
            try:
                value, object_end = decoder.raw_decode(content, object_start)
            except json.JSONDecodeError:
                break
            if isinstance(value, dict):
                recovered.append(value)
            cursor = object_end
        return recovered

    async def gather(self) -> List[CollectedItem]:
        """Main gather method."""
        if not self.sources_file.exists():
            logger.warning(f"Sources file not found: {self.sources_file}")
            return []

        with open(self.sources_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        logger.info(f"Starting WebScraperGatherer for {len(urls)} URLs")
        all_items = []
        self.collection_status = {url: {'status': 'pending', 'count': 0, 'error': None} for url in urls}

        # Process sequentially to respect rate limits and not overload LLM
        for url in urls:
            original_url = url
            # Interpolate date if needed (e.g. for TLDR AI: https://ai.tldr.tech/p/{DATE}-tldr-ai)
            if "{DATE}" in url:
                url = url.replace("{DATE}", self.coverage_date)
                
            logger.info(f"Scraping {original_url}...")
            
            try:
                html = await self._fetch_html(url)
                
                if not html:
                    self.collection_status[original_url]['status'] = 'failed'
                    self.collection_status[original_url]['error'] = 'Failed to fetch HTML'
                    continue
                    
                deterministic_items = await self._extract_deterministic_news(url, html)
                if deterministic_items is not None:
                    items = deterministic_items
                else:
                    clean_text = self._clean_html(html)
                    if len(clean_text) < 100:
                        self.collection_status[original_url]['status'] = 'failed'
                        self.collection_status[original_url]['error'] = 'Text too short after cleaning'
                        logger.warning(f"Text too short after cleaning for {url}")
                        continue
                    items = await self._extract_news_with_llm(url, clean_text)
                if items:
                    logger.info(f"Found {len(items)} articles from {url}")
                    all_items.extend(items)
                    self.collection_status[original_url]['status'] = (
                        'partial' if self._last_date_parse_failures else 'success'
                    )
                    self.collection_status[original_url]['count'] = len(items)
                    if self._last_date_parse_failures:
                        self.collection_status[original_url]['reason_code'] = 'date_parse_failed'
                        self.collection_status[original_url]['error'] = (
                            f'{self._last_date_parse_failures}/{self._last_extract_candidates} '
                            'article candidates had no parseable date'
                        )
                else:
                    if self._last_extract_completed and not self._last_extract_error:
                        if self._last_date_parse_failures:
                            logger.warning(
                                f"Could not validate article dates from {url}: "
                                f"{self._last_date_parse_failures}/"
                                f"{self._last_extract_candidates} parse failures"
                            )
                            self.collection_status[original_url].update({
                                'status': 'partial',
                                'reason_code': 'date_parse_failed',
                                'error': (
                                    f'{self._last_date_parse_failures}/'
                                    f'{self._last_extract_candidates} article candidates '
                                    'had no parseable date'
                                ),
                            })
                        elif self._last_extract_candidates > 0:
                            logger.info(f"No articles in coverage window for {url}")
                            self.collection_status[original_url].update({
                                'status': 'success',
                                'reason_code': 'no_items_in_window',
                                'error': 'No dated articles in coverage window',
                            })
                        else:
                            logger.info(f"No article candidates found on {url}")
                            self.collection_status[original_url].update({
                                'status': 'success',
                                'reason_code': 'no_candidates',
                                'error': 'No article candidates found on page',
                            })
                    else:
                        logger.warning(f"Could not extract any valid articles from {url}")
                        self.collection_status[original_url]['status'] = 'failed'
                        self.collection_status[original_url]['reason_code'] = 'extraction_failed'
                        self.collection_status[original_url]['error'] = (
                            self._last_extract_error or 'No article candidates extracted'
                        )
            except Exception as e:
                logger.error(f"Error scraping {original_url}: {e}")
                self.collection_status[original_url]['status'] = 'failed'
                self.collection_status[original_url]['error'] = str(e)
                
            # Sleep briefly to avoid aggressive scraping
            await asyncio.sleep(1)

        # Deduplicate
        unique_items = deduplicate_items(all_items)
        logger.info(f"WebScraperGatherer completed: {len(unique_items)} items found")
        return unique_items

    def get_collection_status(self) -> Dict[str, Dict[str, Any]]:
        """Return the per-url status of the collection."""
        return self.collection_status
