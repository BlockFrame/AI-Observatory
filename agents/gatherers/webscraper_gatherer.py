import os
import json
import logging
import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

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
        self._last_extract_candidates = 0
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
                    logger.warning(f"Could not parse date {pub_date} for {article_url}")
                    continue
                    
                # Filter by date range (ensure it matches the run's coverage date)
                # self.start_time and self.end_time are timezone-naive in the orchestrator,
                # so we compare naive datetimes (assuming UTC for simplicity in this context)
                dt_naive = dt.replace(tzinfo=None)
                if not (self.start_time <= dt_naive <= self.end_time):
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
                    self.collection_status[original_url]['status'] = 'success'
                    self.collection_status[original_url]['count'] = len(items)
                else:
                    logger.warning(f"Could not extract any valid articles from {url}")
                    if self._last_extract_completed and not self._last_extract_error:
                        self.collection_status[original_url]['status'] = 'success'
                        self.collection_status[original_url]['error'] = (
                            'No dated articles in coverage window'
                            if self._last_extract_candidates > 0
                            else 'No article candidates found on page'
                        )
                    else:
                        self.collection_status[original_url]['status'] = 'failed'
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
