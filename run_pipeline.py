#!/usr/bin/env python3
"""
<<<<<<< HEAD
AI News Aggregation Pipeline - Multi-Agent Architecture

Main entry point that orchestrates the multi-agent pipeline:
1. Parallel Gathering (4 gatherers: news, papers, social, reddit)
2. Parallel Analysis (4 analyzers with adaptive/manual thinking profiles)
3. Cross-Category Topic Detection (ULTRATHINK)
4. Executive Summary Generation
5. Deduplication & QC
6. JSON Data Generation (for SPA frontend)
7. Search Index Update (Lunr.js compatible)
"""

import asyncio
import os
import sys
import logging
import re
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from agents import MainOrchestrator
from agents.config import load_config, ProviderConfig
from agents.config.prompts import load_prompts, PromptAccessor
from generators.json_generator import JSONGenerator
from generators.search_indexer import SearchIndexer
from generators.feed_generator import FeedGenerator
from generators.llms_generator import generate_ai_index_json, generate_llms_txt
from generators.markdown_export import generate_digest_markdown
from agents.delivery.telegram import format_daily_report, send_report
from agents.delivery.push_modes import build_push_payload, update_push_state
from pathlib import Path

=======
AI News Aggregation Pipeline
Main orchestration script that runs the complete workflow.
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Add project directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'collectors'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'processors'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'generators'))

from rss_collector import RSSCollector, load_feed_list
from arxiv_collector import ArxivCollector
from social_collector import SocialMediaCollector, load_list_from_file
from data_processor import DataProcessor
from llm_analyzer import LLMAnalyzer
from html_generator import HTMLGenerator, create_default_templates

>>>>>>> 731b30d (Initial commit: AI News Aggregator pipeline)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
<<<<<<< HEAD
logging.getLogger('httpx').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def parse_date(date_str: str) -> str:
    """
    Parse date string in YYYY-MM-DD or MM-DD-YYYY format.

    Returns date in YYYY-MM-DD format.
    Raises ValueError if format is invalid.
    """
    # Try YYYY-MM-DD format
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        datetime.strptime(date_str, '%Y-%m-%d')  # Validate
        return date_str

    # Try MM-DD-YYYY format
    if re.match(r'^\d{2}-\d{2}-\d{4}$', date_str):
        dt = datetime.strptime(date_str, '%m-%d-%Y')
        return dt.strftime('%Y-%m-%d')

    raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD or MM-DD-YYYY")


async def run_pipeline(config_dir: str, data_dir: str, web_dir: str, target_date: str = None, resume_from=None) -> bool:
    """
    Run the complete multi-agent pipeline.

    Args:
        config_dir: Directory containing configuration files
        data_dir: Directory for data storage
        web_dir: Directory for generated website
        target_date: Report date (YYYY-MM-DD). Coverage is day before.
        resume_from: Phase number (float) to resume from, or 'auto' for auto-detection.

    Returns:
        True if successful, False otherwise.
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("AI NEWS AGGREGATION PIPELINE - MULTI-AGENT ARCHITECTURE")
    logger.info(f"Start time: {start_time}")
    logger.info("=" * 60)

    # Load and validate configuration FIRST
    # This will auto-migrate from env vars if needed, or exit with clear error
    logger.info("Loading provider configuration...")
    provider_config = load_config(config_dir)

    # Load prompt configuration
    logger.info("Loading prompt configuration...")
    prompt_config = load_prompts(config_dir)
    prompt_accessor = PromptAccessor(prompt_config)
    logger.info(f"Loaded prompts from {config_dir}/prompts.yaml")

    # Get additional configuration from environment (CLI args override env vars)
    lookback_hours = int(os.getenv('LOOKBACK_HOURS', '24'))
    if not target_date:
        target_date = os.getenv('TARGET_DATE', '')

    orchestrator = None

    try:
        # Initialize orchestrator with provider config and prompt accessor
        orchestrator = MainOrchestrator(
            config_dir=config_dir,
            data_dir=data_dir,
            web_dir=web_dir,
            lookback_hours=lookback_hours,
            target_date=target_date if target_date else None,
            provider_config=provider_config,
            prompt_accessor=prompt_accessor
        )

        # Handle resume modes
        actual_resume_from = None
        if resume_from == 'auto':
            actual_resume_from = orchestrator._detect_resume_point()
            if actual_resume_from is None:
                logger.info("No checkpoints found - running full pipeline")
            else:
                logger.info(f"Auto-resume: will resume from phase {actual_resume_from}")
        elif resume_from is not None:
            actual_resume_from = float(resume_from)

        # Run the multi-agent pipeline
        result = await orchestrator.run(resume_from=actual_resume_from)

        # Generate JSON data for SPA frontend
        logger.info("=" * 60)
        logger.info("PHASE 6: JSON DATA GENERATION")
        logger.info("=" * 60)

        result_dict = result.to_dict()
        json_generator = JSONGenerator(web_dir)
        json_generator.generate_from_orchestrator_result(result_dict)

        # Generate RSS/Atom feeds
        logger.info("=" * 60)
        logger.info("PHASE 6.5: RSS FEED GENERATION")
        logger.info("=" * 60)

        pipeline_config = provider_config.get_pipeline_config()
        feed_generator = FeedGenerator(
            web_dir,
            rolling_window_days=7,
            base_url=pipeline_config.base_url
        )
        feed_generator.generate_feeds()

        # Update search index
        logger.info("=" * 60)
        logger.info("PHASE 7: SEARCH INDEX UPDATE")
        logger.info("=" * 60)

        search_indexer = SearchIndexer(web_dir, rolling_window_days=30)
        search_indexer.update_index(result_dict)

        logger.info("=" * 60)
        logger.info("PHASE 7.1: EXPORTS (llms.txt, ai-index.json, digest.md)")
        logger.info("=" * 60)
        generate_llms_txt(Path(web_dir) / "data")
        generate_ai_index_json(Path(web_dir) / "data")
        generate_digest_markdown(result_dict, web_dir=web_dir)

        logger.info("=" * 60)
        logger.info("PHASE 7.2: TELEGRAM DELIVERY")
        logger.info("=" * 60)
        push_mode = "daily"
        if provider_config.push:
            push_mode = str(provider_config.push.get("mode", "daily"))
        state_path = Path(data_dir) / "state" / "last_push.json"
        payload, should_send = build_push_payload(push_mode, result_dict, state_path)
        if should_send:
            report = format_daily_report(payload)
            delivered = send_report(report)
            if delivered:
                update_push_state(state_path, payload)
                logger.info("Telegram delivery complete")
            else:
                logger.warning("Telegram delivery skipped or failed")
        else:
            logger.info("Telegram delivery skipped (incremental mode with no new items)")

        # Complete
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETED SUCCESSFULLY")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Total items collected: {result.total_items_collected}")
        logger.info(f"Total items analyzed: {result.total_items_analyzed}")
        logger.info(f"Top topics: {len(result.top_topics)}")
        logger.info(f"Data output: {web_dir}/data/")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return False

    finally:
        if orchestrator:
            await orchestrator.close()
=======
logger = logging.getLogger(__name__)


class Pipeline:
    """Main pipeline orchestrator."""

    def __init__(self, config_dir: str, data_dir: str, web_dir: str):
        """
        Initialize pipeline.

        Args:
            config_dir: Directory containing configuration files
            data_dir: Directory for data storage
            web_dir: Directory for generated website
        """
        self.config_dir = config_dir
        self.data_dir = data_dir
        self.web_dir = web_dir
        self.lookback_hours = int(os.getenv('LOOKBACK_HOURS', '24'))
        self.target_date = os.getenv('TARGET_DATE', '')  # Format: YYYY-MM-DD
        
        # Create directories
        for dir_path in [config_dir, data_dir, web_dir]:
            os.makedirs(dir_path, exist_ok=True)
        
        # Create subdirectories
        self.raw_data_dir = os.path.join(data_dir, 'raw')
        self.processed_data_dir = os.path.join(data_dir, 'processed')
        os.makedirs(self.raw_data_dir, exist_ok=True)
        os.makedirs(self.processed_data_dir, exist_ok=True)
        
        # Template directory
        self.template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        
        logger.info("Pipeline initialized")
    
    def run_collection(self) -> dict:
        """Run data collection phase."""
        logger.info("=" * 60)
        logger.info("PHASE 1: DATA COLLECTION")
        logger.info("=" * 60)
        
        collection_stats = {}
        
        # Collect RSS feeds
        try:
            rss_feeds_file = os.path.join(self.config_dir, 'rss_feeds.txt')
            if os.path.exists(rss_feeds_file):
                logger.info("Collecting RSS feeds...")
                feeds = load_feed_list(rss_feeds_file)
                collector = RSSCollector(
                    feeds,
                    lookback_hours=self.lookback_hours,
                    target_date=self.target_date if self.target_date else None
                )
                articles = collector.collect()
                output_file = os.path.join(self.raw_data_dir, 'rss.json')
                collector.save_to_file(articles, output_file)
                collection_stats['rss'] = len(articles)
            else:
                logger.warning(f"RSS feeds file not found: {rss_feeds_file}")
                collection_stats['rss'] = 0
        except Exception as e:
            logger.error(f"RSS collection failed: {e}")
            collection_stats['rss'] = 0
        
        # Collect arXiv papers
        try:
            logger.info("Collecting arXiv papers...")
            collector = ArxivCollector(
                lookback_hours=self.lookback_hours,
                target_date=self.target_date if self.target_date else None
            )
            papers = collector.collect()
            output_file = os.path.join(self.raw_data_dir, 'arxiv.json')
            collector.save_to_file(papers, output_file)
            collection_stats['arxiv'] = len(papers)
        except Exception as e:
            logger.error(f"arXiv collection failed: {e}")
            collection_stats['arxiv'] = 0
        
        # Collect social media
        try:
            logger.info("Collecting social media...")
            collector = SocialMediaCollector(
                lookback_hours=self.lookback_hours,
                target_date=self.target_date if self.target_date else None
            )

            # Twitter (using TwitterAPI.io batch search - more efficient)
            twitter_file = os.path.join(self.config_dir, 'twitter_accounts.txt')
            if os.path.exists(twitter_file):
                usernames = load_list_from_file(twitter_file)
                if usernames:
                    # Use batch search for efficiency (fewer API calls)
                    tweets = collector.collect_twitter_search(usernames)
                    if tweets:
                        output_file = os.path.join(self.raw_data_dir, 'twitter.json')
                        collector.save_to_file(tweets, output_file, 'twitter')
                        collection_stats['twitter'] = len(tweets)
                    else:
                        logger.warning("No tweets collected (check TWITTERAPI_IO_KEY)")

            # Reddit (using free JSON endpoint)
            reddit_file = os.path.join(self.config_dir, 'reddit_subreddits.txt')
            if os.path.exists(reddit_file):
                subreddits = load_list_from_file(reddit_file)
                if subreddits:
                    posts = collector.collect_reddit_json(subreddits)
                    if posts:
                        output_file = os.path.join(self.raw_data_dir, 'reddit.json')
                        collector.save_to_file(posts, output_file, 'reddit')
                        collection_stats['reddit'] = len(posts)

            # Bluesky (public API)
            bluesky_file = os.path.join(self.config_dir, 'bluesky_accounts.txt')
            if os.path.exists(bluesky_file):
                handles = load_list_from_file(bluesky_file)
                if handles:
                    posts = collector.collect_bluesky(handles)
                    output_file = os.path.join(self.raw_data_dir, 'bluesky.json')
                    collector.save_to_file(posts, output_file, 'bluesky')
                    collection_stats['bluesky'] = len(posts)

            # Mastodon (public API)
            mastodon_file = os.path.join(self.config_dir, 'mastodon_accounts.txt')
            if os.path.exists(mastodon_file):
                accounts = load_list_from_file(mastodon_file)
                if accounts:
                    posts = collector.collect_mastodon(accounts)
                    output_file = os.path.join(self.raw_data_dir, 'mastodon.json')
                    collector.save_to_file(posts, output_file, 'mastodon')
                    collection_stats['mastodon'] = len(posts)
        except Exception as e:
            logger.error(f"Social media collection failed: {e}")
        
        logger.info(f"Collection complete. Stats: {collection_stats}")
        return collection_stats
    
    def run_processing(self) -> str:
        """Run data processing phase."""
        logger.info("=" * 60)
        logger.info("PHASE 2: DATA PROCESSING")
        logger.info("=" * 60)
        
        # Find all raw data files
        import glob
        data_files = glob.glob(os.path.join(self.raw_data_dir, '*.json'))
        logger.info(f"Found {len(data_files)} raw data files")
        
        # Process data
        processor = DataProcessor()
        items = processor.process(data_files)
        
        # Save processed data
        output_file = os.path.join(self.processed_data_dir, 'processed.json')
        processor.save_to_file(items, output_file)
        
        logger.info(f"Processing complete. {len(items)} unique items")
        return output_file
    
    def run_analysis(self, processed_file: str) -> str:
        """Run LLM analysis phase."""
        logger.info("=" * 60)
        logger.info("PHASE 3: LLM ANALYSIS")
        logger.info("=" * 60)
        
        # Load processed data
        with open(processed_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        items = data.get('items', [])
        logger.info(f"Analyzing {len(items)} items")
        
        # Run analysis
        analyzer = LLMAnalyzer()
        analysis = analyzer.analyze_all(items)
        
        # Save analysis
        output_file = os.path.join(self.processed_data_dir, 'analyzed.json')
        analyzer.save_analysis(analysis, output_file)
        
        logger.info("Analysis complete")
        return output_file
    
    def run_generation(self, analysis_file: str):
        """Run HTML generation phase."""
        logger.info("=" * 60)
        logger.info("PHASE 4: HTML GENERATION")
        logger.info("=" * 60)
        
        # Create templates if they don't exist
        if not os.path.exists(self.template_dir):
            logger.info("Creating default templates")
            create_default_templates(self.template_dir)
        
        # Load analysis
        with open(analysis_file, 'r', encoding='utf-8') as f:
            analysis = json.load(f)
        
        # Generate HTML
        generator = HTMLGenerator(self.template_dir, self.web_dir)
        generator.generate_all(analysis)
        
        logger.info(f"HTML generation complete. Website available at: {self.web_dir}")
    
    def run(self):
        """Run the complete pipeline."""
        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info("AI NEWS AGGREGATION PIPELINE STARTED")
        logger.info(f"Start time: {start_time}")
        logger.info("=" * 60)
        
        try:
            # Phase 1: Collection
            collection_stats = self.run_collection()
            
            # Phase 2: Processing
            processed_file = self.run_processing()
            
            # Phase 3: Analysis
            analysis_file = self.run_analysis(processed_file)
            
            # Phase 4: Generation
            self.run_generation(analysis_file)
            
            # Complete
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info("=" * 60)
            logger.info("PIPELINE COMPLETED SUCCESSFULLY")
            logger.info(f"Duration: {duration:.2f} seconds")
            logger.info(f"Website: {self.web_dir}/index.html")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            return False
>>>>>>> 731b30d (Initial commit: AI News Aggregator pipeline)


def create_default_config_files(config_dir: str):
    """Create default configuration files."""
<<<<<<< HEAD

    # RSS feeds
    rss_feeds = """# AI News RSS/Atom Feeds (one per line)
# Optional per-feed routing directive (default = proxied when a proxy is set):
#   <url>  proxy=off -> fetch direct, bypass the Mullvad/pipeline proxy
#   <url>  proxy=on  -> force routing through the proxy
=======
    
    # RSS feeds
    rss_feeds = """# AI News RSS Feeds (one per line)
>>>>>>> 731b30d (Initial commit: AI News Aggregator pipeline)
# Major news sites
https://feeds.arstechnica.com/arstechnica/index
https://www.wired.com/feed/tag/ai/latest/rss
https://venturebeat.com/category/ai/feed/
https://www.theguardian.com/technology/artificialintelligenceai/rss
https://www.artificialintelligence-news.com/feed/rss/
<<<<<<< HEAD
https://techcrunch.com/category/artificial-intelligence/feed/
https://www.theverge.com/rss/ai-artificial-intelligence/index.xml
https://www.technologyreview.com/topic/artificial-intelligence/feed/
https://spectrum.ieee.org/rss/artificial-intelligence/fulltext
https://the-decoder.com/feed/
https://www.theregister.com/software/ai_ml/headlines.atom
https://www.newscientist.com/subject/artificial-intelligence/feed/

# AI-specific sites
https://aibusiness.com/rss.xml
https://www.marktechpost.com/feed
https://openai.com/news/rss.xml
https://blog.google/technology/ai/rss/
https://blogs.microsoft.com/ai/feed/
https://aws.amazon.com/blogs/machine-learning/feed/
https://blogs.nvidia.com/blog/tag/generative-ai/feed/
https://github.blog/tag/github-copilot/feed/
=======

# AI-specific sites
https://aibusiness.com/rss.xml
https://analyticsindiamag.com/feed/
https://www.marktechpost.com/feed
>>>>>>> 731b30d (Initial commit: AI News Aggregator pipeline)

# Research blogs
https://deepmind.com/blog/feed/basic/
https://huggingface.co/blog/feed.xml
<<<<<<< HEAD
=======
https://blog.langchain.dev/rss/
>>>>>>> 731b30d (Initial commit: AI News Aggregator pipeline)

# Industry analysis
https://every.to/chain-of-thought/feed.xml
https://lastweekin.ai/feed
https://www.latent.space/feed
<<<<<<< HEAD
https://semianalysis.com/feed/
"""

    research_feeds = """# AI research RSS/Atom feeds and technical blogs (one per line)
# Optional per-feed routing directive (default = proxied when a proxy is set):
#   <url>  proxy=off -> fetch direct, bypass the Mullvad/pipeline proxy
#   <url>  proxy=on  -> force routing through the proxy
https://www.lesswrong.com/feed.xml?view=frontpage-rss&karmaThreshold=2
https://research.google/blog/rss/
https://www.microsoft.com/en-us/research/blog/category/artificial-intelligence/feed/
# Meta blocks datacenter/VPN exits (400 via Mullvad), so fetch this one direct.
https://research.facebook.com/feed/  proxy=off
https://www.amazon.science/index.rss
https://allenai.org/rss.xml
https://bair.berkeley.edu/blog/feed.xml
https://metr.org/feed.xml
https://www.alignmentforum.org/feed.xml?view=frontpage-rss&karmaThreshold=2
https://news.mit.edu/rss/topic/artificial-intelligence2
https://blog.ml.cmu.edu/feed/
https://thegradient.pub/rss/
https://importai.substack.com/feed
https://www.interconnects.ai/feed
https://lilianweng.github.io/index.xml
https://huyenchip.com/feed.xml
https://www.nature.com/subjects/machine-learning.rss
https://www.nature.com/natmachintell.rss
http://feeds.trendmicro.com/TrendMicroSimplySecurity
"""

=======
"""
    
>>>>>>> 731b30d (Initial commit: AI News Aggregator pipeline)
    # Twitter accounts
    twitter_accounts = """# Twitter accounts to monitor (one per line, without @)
# AI Lab Leaders
sama
demishassabis
ylecun
karpathy

# AI Companies
OpenAI
AnthropicAI
GoogleDeepMind
StabilityAI

# Researchers
emollick
hardmaru
"""
<<<<<<< HEAD

=======
    
>>>>>>> 731b30d (Initial commit: AI News Aggregator pipeline)
    # Reddit subreddits
    reddit_subs = """# Reddit subreddits to monitor (one per line, without r/)
MachineLearning
artificial
LocalLLaMA
OpenAI
singularity
"""

    # Bluesky accounts
    bluesky_accounts = """# Bluesky accounts to monitor (one per line)
# Format: handle or handle.bsky.social
# AI researchers and leaders
karpathy.bsky.social
ylecun.bsky.social
emollick.bsky.social

# AI companies and labs
anthropic.bsky.social
openai.bsky.social

# AI news and commentary
simonwillison.net
"""

    # Mastodon accounts
    mastodon_accounts = """# Mastodon accounts to monitor (one per line)
# Format: username@instance.social
# Note: Must be a real Mastodon instance (mastodon.social, fosstodon.org, etc.)

# AI/ML researchers
Geoffreylitt@mas.to
hardmaru@mas.to

# Tech community
Gargron@mastodon.social
"""

    os.makedirs(config_dir, exist_ok=True)

    with open(os.path.join(config_dir, 'rss_feeds.txt'), 'w') as f:
        f.write(rss_feeds)

<<<<<<< HEAD
    with open(os.path.join(config_dir, 'research_feeds.txt'), 'w') as f:
        f.write(research_feeds)

=======
>>>>>>> 731b30d (Initial commit: AI News Aggregator pipeline)
    with open(os.path.join(config_dir, 'twitter_accounts.txt'), 'w') as f:
        f.write(twitter_accounts)

    with open(os.path.join(config_dir, 'reddit_subreddits.txt'), 'w') as f:
        f.write(reddit_subs)

    with open(os.path.join(config_dir, 'bluesky_accounts.txt'), 'w') as f:
        f.write(bluesky_accounts)

    with open(os.path.join(config_dir, 'mastodon_accounts.txt'), 'w') as f:
        f.write(mastodon_accounts)

    logger.info(f"Created default configuration files in {config_dir}")


<<<<<<< HEAD
def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='AI News Aggregation Pipeline - Multi-Agent Architecture'
    )
    parser.add_argument(
        '--config-dir', default='./config',
        help='Configuration directory'
    )
    parser.add_argument(
        '--data-dir', default='./data',
        help='Data directory'
    )
    parser.add_argument(
        '--web-dir', default='./web',
        help='Web output directory'
    )
    parser.add_argument(
        '--create-config', action='store_true',
        help='Create default config files'
    )
    parser.add_argument(
        '--date', '-d',
        help='Report date (YYYY-MM-DD or MM-DD-YYYY). Coverage is day before.'
    )
    parser.add_argument(
        '--resume', action='store_true',
        help='Auto-resume from latest checkpoint (for crash recovery)'
    )
    parser.add_argument(
        '--resume-from', type=float, metavar='PHASE',
        help='Resume from phase N (e.g., 3, 4.5, 4.7). Loads earlier phases from checkpoint.'
    )

    args = parser.parse_args()

=======
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='AI News Aggregation Pipeline')
    parser.add_argument('--config-dir', default='./config', help='Configuration directory')
    parser.add_argument('--data-dir', default='./data', help='Data directory')
    parser.add_argument('--web-dir', default='./web', help='Web output directory')
    parser.add_argument('--create-config', action='store_true', help='Create default config files')
    
    args = parser.parse_args()
    
>>>>>>> 731b30d (Initial commit: AI News Aggregator pipeline)
    # Create default config if requested
    if args.create_config:
        create_default_config_files(args.config_dir)
        logger.info("Default configuration files created. Edit them and run again.")
        sys.exit(0)
<<<<<<< HEAD

    # Parse date if provided
    target_date = None
    if args.date:
        try:
            target_date = parse_date(args.date)
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)

    # Determine resume mode
    resume_from = None
    if args.resume and args.resume_from is not None:
        logger.error("Cannot use both --resume and --resume-from. Use one or the other.")
        sys.exit(1)
    elif args.resume:
        resume_from = 'auto'  # Auto-detect inside run_pipeline
    elif args.resume_from is not None:
        resume_from = args.resume_from

    # Run async pipeline
    success = asyncio.run(run_pipeline(
        args.config_dir,
        args.data_dir,
        args.web_dir,
        target_date,
        resume_from=resume_from
    ))

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
=======
    
    # Run pipeline
    pipeline = Pipeline(args.config_dir, args.data_dir, args.web_dir)
    success = pipeline.run()
    
    sys.exit(0 if success else 1)
>>>>>>> 731b30d (Initial commit: AI News Aggregator pipeline)
