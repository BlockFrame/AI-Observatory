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
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
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

    async def _extract_news_with_llm(self, url: str, text: str) -> Optional[CollectedItem]:
        """Use LLM to extract the most recent news article from text."""
        
        system_prompt = """You are an expert web scraper. You will be given the raw text content of a company's news/blog webpage.
Your job is to identify the SINGLE most recent and important news article, announcement, or blog post listed on the page.

Return ONLY a JSON object with the following keys:
- "title": The title of the article.
- "url": The FULL absolute URL to the article (resolve relative paths if necessary based on the base domain).
- "date": The publication date in YYYY-MM-DD format (if visible, otherwise output "").
- "summary": A brief 1-sentence summary of what it's about.

Do not include any other text, markdown formatting, or preamble. Just the JSON object."""

        user_message = f"Base URL: {url}\n\nWebpage Text:\n{text}"

        try:
            response = self.llm_client.call(
                messages=[{"role": "user", "content": user_message}],
                system=system_prompt,
                temperature=0.0,
                max_tokens=300
            )
            
            json_str = extract_json_str(response.content)
            data = json.loads(json_str)
            
            if not data.get("title") or not data.get("url"):
                return None
                
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
                logger.warning(f"Could not parse date {pub_date} for {url}")
                return None
                
            # Filter by date range (ensure it matches the run's coverage date)
            # self.start_time and self.end_time are timezone-naive in the orchestrator,
            # so we compare naive datetimes (assuming UTC for simplicity in this context)
            dt_naive = dt.replace(tzinfo=None)
            if not (self.start_time <= dt_naive <= self.end_time):
                logger.info(f"Skipping {url}: article date {dt_naive} is outside coverage window ({self.start_time} to {self.end_time})")
                return None
            
            return CollectedItem(
                id=item_id,
                source=url,
                title=data["title"],
                url=article_url,
                content=data.get("summary", ""),
                pub_date=pub_date,
                category=self.category,
                metadata={"scraper_type": "llm_html"}
            )
            
        except Exception as e:
            logger.error(f"LLM extraction failed for {url}: {e}")
            return None

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
                    
                item = await self._extract_news_with_llm(url, clean_text)
                if item:
                    logger.info(f"Found article: {item.title}")
                    all_items.append(item)
                    self.collection_status[original_url]['status'] = 'success'
                    self.collection_status[original_url]['count'] = 1
                else:
                    logger.warning(f"Could not extract article from {url}")
                    self.collection_status[original_url]['status'] = 'failed'
                    self.collection_status[original_url]['error'] = 'Could not extract article or outside date range'
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
