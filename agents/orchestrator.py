"""
Main Orchestrator

Coordinates all gatherer and analyzer agents, detects cross-category topics,
assembles the final report, and triggers HTML generation.
"""

import asyncio
import logging
import os
import json
import re
import time
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from .llm_client import AnthropicClient, AsyncAnthropicClient, AsyncLLMRouter, ThinkingLevel, LLMResponse
from .base import (
    BaseGatherer, BaseAnalyzer, CollectedItem, AnalyzedItem,
    CategoryReport, CategoryTheme, deduplicate_items, extract_json_str
)
from .gatherers import (
    NewsGatherer,
    ResearchGatherer,
    SocialGatherer,
    LinkFollower,
    HackerNewsGatherer,
    GitHubTrendingGatherer,
    WebScraperGatherer,
)
from .analyzers import NewsAnalyzer, ResearchAnalyzer, SocialAnalyzer, GitHubTrendingAnalyzer
from .cost_tracker import get_tracker, reset_tracker
from .link_enricher import LinkEnricher
from .ecosystem_context import EcosystemContextManager
from .editorial_guard import sanitize_editorial_text
from .summary_context import (
    build_executive_context,
    format_previous_coverage,
    load_previous_summaries,
)
from .prompt_security import (
    DATA_POINTER,
    build_fenced_user_message,
    build_hardened_system,
    new_fence_nonce,
    normalize_untrusted_text,
)
from .staleness_checker import StalenessChecker
from .phase_tracker import PhaseTracker
from .config import ProviderConfig
from .filters import KeywordFilter, apply_keyword_limit, SemanticDeduplicator
from .analysis import classify_sentiments
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config.prompts import PromptAccessor

# Import hero generator (optional, may not be available in all environments)
try:
    from generators.hero_generator import HeroGenerator, initialize_hero_generator
    HERO_GENERATOR_AVAILABLE = True
except ImportError:
    HERO_GENERATOR_AVAILABLE = False
    initialize_hero_generator = None

logger = logging.getLogger(__name__)

MIN_EXECUTIVE_SUMMARY_CHARS = 400
MAX_EXECUTIVE_SUMMARY_WORDS = 650


@dataclass
class TopTopic:
    """A cross-category topic detected by the orchestrator."""
    name: str
    description: str  # Plain text description
    description_html: str  # Description with inline HTML links
    category_breakdown: Dict[str, int]  # category -> item count
    representative_items: List[str]  # Item IDs from each category
    importance: float  # 0-100
    business_implication: str = ""
    trend_velocity: str = ""


@dataclass
class OrchestratorResult:
    """Final result produced by the orchestrator."""
    date: str  # Report date (YYYY-MM-DD)
    executive_summary: str
    top_topics: List[TopTopic]
    category_reports: Dict[str, CategoryReport]  # category -> report
    total_items_collected: int
    total_items_analyzed: int
    coverage_date: str = ''  # Date of news coverage (day before report date)
    coverage_start: str = ''  # ISO datetime string for coverage start
    coverage_end: str = ''  # ISO datetime string for coverage end
    collection_status: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # source -> status
    analysis_funnel: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    executive_evidence_items: List[str] = field(default_factory=list)
    hero_image_url: Optional[str] = None  # URL path to generated hero image
    hero_image_prompt: Optional[str] = None  # Prompt used to generate hero image
    phase_status: List[Dict[str, Any]] = field(default_factory=list)  # Phase tracker records
    llm_telemetry: Dict[str, Any] = field(default_factory=dict)
    orchestrator_thinking: Optional[str] = None
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'date': self.date,
            'coverage_date': self.coverage_date,
            'coverage_start': self.coverage_start,
            'coverage_end': self.coverage_end,
            'executive_summary': self.executive_summary,
            'top_topics': [asdict(topic) for topic in self.top_topics],
            'category_reports': {k: v.to_dict() for k, v in self.category_reports.items()},
            'total_items_collected': self.total_items_collected,
            'total_items_analyzed': self.total_items_analyzed,
            'collection_status': self.collection_status,
            'analysis_funnel': self.analysis_funnel,
            'executive_evidence_items': self.executive_evidence_items,
            'hero_image_url': self.hero_image_url,
            'hero_image_prompt': self.hero_image_prompt,
            'phase_status': self.phase_status,
            'llm_telemetry': self.llm_telemetry,
            'orchestrator_thinking': self.orchestrator_thinking,
            'generated_at': self.generated_at
        }


class MainOrchestrator:
    """
    Main orchestrator that coordinates all agents.

    Flow:
    0. Ecosystem Context (fetch AI model state for grounding)
    1. Parallel Gathering (category and auxiliary gatherers)
    2. Parallel Analysis (category analyzers with grounding context)
    3. Cross-Category Topic Detection (ULTRATHINK)
    4. Main Page Assembly
    5. Deduplication & QC
    6. HTML Generation
    """

    def __init__(
        self,
        config_dir: str = './config',
        data_dir: str = './data',
        web_dir: str = './web',
        lookback_hours: int = 24,
        target_date: Optional[str] = None,
        provider_config: Optional[ProviderConfig] = None,
        prompt_accessor: Optional['PromptAccessor'] = None
    ):
        """
        Initialize orchestrator.

        Args:
            config_dir: Directory containing configuration files.
            data_dir: Directory for storing data.
            web_dir: Directory for generated HTML.
            lookback_hours: Hours to look back for items.
            target_date: Specific date to collect (YYYY-MM-DD format).
            provider_config: Provider configuration. If None, loads from env vars.
            prompt_accessor: Optional PromptAccessor for config-based prompts.
        """
        self.config_dir = config_dir
        self.data_dir = data_dir
        self.web_dir = web_dir
        self.lookback_hours = lookback_hours
        self.target_date = target_date or self._get_today()
        self.provider_config = provider_config
        self.prompt_accessor = prompt_accessor

        # Initialize LLM clients from config
        if provider_config:
            self.llm_client = AnthropicClient.from_config(provider_config.llm)
            self.async_client = AsyncLLMRouter.from_config(provider_config.llm)
        else:
            # Fallback to env vars for backwards compatibility
            self.llm_client = AnthropicClient()
            self.async_client = AsyncAnthropicClient()

        # Initialize gatherers
        self.gatherers: Dict[str, BaseGatherer] = {
            'news': NewsGatherer(
                config_dir=config_dir,
                data_dir=data_dir,
                lookback_hours=lookback_hours,
                target_date=self.target_date,
                llm_client=self.llm_client,  # For link following
                prompt_accessor=prompt_accessor
            ),
            'research': ResearchGatherer(
                config_dir=config_dir,
                data_dir=data_dir,
                lookback_hours=lookback_hours,
                target_date=self.target_date
            ),
            'social': SocialGatherer(
                config_dir=config_dir,
                data_dir=data_dir,
                lookback_hours=lookback_hours,
                target_date=self.target_date
            ),
            'web_scraper': WebScraperGatherer(
                config_dir=config_dir,
                data_dir=data_dir,
                lookback_hours=lookback_hours,
                target_date=self.target_date,
                llm_client=self.llm_client,
                prompt_accessor=prompt_accessor
            )
        }
        self.hackernews_gatherer = HackerNewsGatherer(
            config_dir=config_dir,
            data_dir=data_dir,
            lookback_hours=lookback_hours,
            target_date=self.target_date,
            top_limit=int(((provider_config.hackernews or {}).get("top_limit", 30)) if provider_config else 30),
            top_min_score=int(((provider_config.hackernews or {}).get("top_min_score", 50)) if provider_config else 50),
            best_limit=int(((provider_config.hackernews or {}).get("best_limit", 20)) if provider_config else 20),
            best_min_score=int(((provider_config.hackernews or {}).get("best_min_score", 100)) if provider_config else 100),
        )
        github_token = ""
        if provider_config and provider_config.github:
            github_token = str(provider_config.github.get("token") or "")
        self.github_trending_gatherer = GitHubTrendingGatherer(
            config_dir=config_dir,
            data_dir=data_dir,
            lookback_hours=lookback_hours,
            target_date=self.target_date,
            token=github_token or os.getenv("GITHUB_TOKEN"),
        )
        self.keyword_filter = KeywordFilter(Path(config_dir) / "keywords.txt")
        self.semantic_dedup = SemanticDeduplicator()

        # Initialize analyzers
        self.analyzers: Dict[str, BaseAnalyzer] = {
            'news': NewsAnalyzer(
                llm_client=self.llm_client,
                async_client=self.async_client,
                data_dir=data_dir,
                config_dir=config_dir,
                target_date=self.target_date,
                web_dir=web_dir,
                prompt_accessor=prompt_accessor
            ),
            'research': ResearchAnalyzer(
                llm_client=self.llm_client,
                async_client=self.async_client,
                data_dir=data_dir,
                config_dir=config_dir,
                target_date=self.target_date,
                web_dir=web_dir,
                prompt_accessor=prompt_accessor
            ),
            'social': SocialAnalyzer(
                llm_client=self.llm_client,
                async_client=self.async_client,
                data_dir=data_dir,
                config_dir=config_dir,
                target_date=self.target_date,
                web_dir=web_dir,
                prompt_accessor=prompt_accessor
            ),
            'github_trending': GitHubTrendingAnalyzer(
                llm_client=self.llm_client,
                async_client=self.async_client,
                data_dir=data_dir,
                config_dir=config_dir,
                target_date=self.target_date,
                web_dir=web_dir,
                prompt_accessor=prompt_accessor
            )
        }

        # Initialize hero generator if available AND configured
        self.hero_generator: Optional['HeroGenerator'] = None
        if HERO_GENERATOR_AVAILABLE and initialize_hero_generator:
            image_config = provider_config.image if provider_config else None
            self.hero_generator = initialize_hero_generator(image_config)

        # Initialize ecosystem context manager (Phase 0)
        self.ecosystem_manager = EcosystemContextManager(Path(config_dir), prompt_accessor=prompt_accessor)
        self.grounding_context: Optional[str] = None  # Set in run()

        logger.info(f"Orchestrator initialized for {self.target_date}")

    def _get_today(self) -> str:
        """Get today's date as YYYY-MM-DD."""
        return datetime.now().strftime('%Y-%m-%d')

    async def run(self, resume_from: Optional[float] = None) -> OrchestratorResult:
        """
        Run the full pipeline.

        Args:
            resume_from: If set, load checkpoints for phases before this number
                         and re-run phases at and after this number.
                         E.g., resume_from=3 loads gathering + analysis, re-runs topic detection onward.

        Returns:
            OrchestratorResult with all analysis.
        """
        logger.info(f"Starting orchestrator run for {self.target_date}")
        if resume_from is not None:
            logger.info(f"Resuming from phase {resume_from} (loading earlier phases from checkpoint)")
        start_time = datetime.now()

        # Initialize cost tracking
        tracker_model = (
            self.provider_config.llm.model
            if self.provider_config is not None
            else "claude-4.8-opus-aws"
        )
        cost_tracker = reset_tracker(tracker_model)
        cost_tracker.start()

        # Initialize phase tracker
        phases = PhaseTracker()

        # Phase 0: Ecosystem Context (always runs fresh - fast and stateless)
        phases.start_phase("Phase 0: Ecosystem Context")
        try:
            logger.info("Phase 0: Loading ecosystem context...")
            from datetime import date as date_type
            report_date = date_type.fromisoformat(self.target_date)
            self.grounding_context = await self.ecosystem_manager.initialize(report_date)
            ctx_len = len(self.grounding_context) if self.grounding_context else 0
            phases.end_phase('success', details=f"{ctx_len} chars")
        except Exception as e:
            logger.warning(f"Ecosystem context failed: {e}")
            self.grounding_context = None
            phases.end_phase('partial', error=str(e))

        # Phase 1: Parallel Gathering
        if resume_from is not None and resume_from > 1:
            checkpoint = self._load_checkpoint('gathering')
            if not checkpoint:
                raise RuntimeError("Cannot resume: no checkpoint for Phase 1 (gathering)")
            gathered_items = self._restore_gathered_items(checkpoint)
            collection_status = checkpoint.get('collection_status', {})
            total_items = sum(len(items) for items in gathered_items.values())
            phases.skip_phase("Phase 1: Gathering", f"loaded from checkpoint ({total_items} items)")
        else:
            phases.start_phase("Phase 1: Gathering")
            try:
                logger.info("Phase 1: Gathering from all sources...")
                gathered_items, collection_status = await self._gather_all()
                gathered_items = await self._apply_pre_analysis_filters(gathered_items)
                total_items = sum(len(items) for items in gathered_items.values())
                has_degradation = any(
                    s.get('status') in {'failed', 'partial', 'unknown'}
                    for s in collection_status.values()
                )
                status = 'partial' if has_degradation else 'success'
                phases.end_phase(status, details=f"{total_items} items")
                self._save_checkpoint('gathering', {
                    'collection_status': collection_status,
                    'categories': {cat: [item.to_dict() for item in items] for cat, items in gathered_items.items()}
                })
            except Exception as e:
                phases.end_phase('failed', error=str(e))
                raise

        # Phase 2: Parallel Analysis (with grounding context)
        if resume_from is not None and resume_from > 2:
            checkpoint = self._load_checkpoint('analysis')
            if not checkpoint:
                raise RuntimeError("Cannot resume: no checkpoint for Phase 2 (analysis)")
            category_reports = self._restore_category_reports(checkpoint)
            try:
                staleness_checker = StalenessChecker(
                    config_dir=self.config_dir,
                    target_date=self.target_date,
                    web_dir=self.web_dir,
                )
                category_reports = staleness_checker.process(category_reports)
            except Exception as e:
                logger.warning(f"Resume freshness repair failed (non-fatal): {e}")
            category_reports = await self._ensure_report_category_summaries(category_reports)
            total_analyzed = sum(len(r.all_items) for r in category_reports.values())
            phases.skip_phase("Phase 2: Analysis", f"loaded from checkpoint ({total_analyzed} items)")
            phases.skip_phase("Phase 2.5: Continuity Detection", "loaded from checkpoint")
        else:
            phases.start_phase("Phase 2: Analysis")
            try:
                logger.info("Phase 2: Analyzing all categories...")
                category_reports = await self._analyze_all(gathered_items)
                category_reports = await self.semantic_dedup.deduplicate_reports(
                    category_reports, async_client=self.async_client
                )
                await classify_sentiments(category_reports, async_client=self.async_client)
                total_analyzed = sum(len(r.all_items) for r in category_reports.values())
                phases.end_phase('success', details=f"{total_analyzed} items")
            except Exception as e:
                phases.end_phase('failed', error=str(e))
                raise

            # Phase 2.5: Continuity Detection
            phases.start_phase("Phase 2.5: Continuity Detection")
            try:
                logger.info("Phase 2.5: Detecting story continuations...")
                from .continuity import ContinuityCoordinator
                continuity_coordinator = ContinuityCoordinator(
                    async_client=self.async_client,
                    web_dir=self.web_dir,
                    target_date=self.target_date,
                    lookback_days=2
                )
                category_reports = await continuity_coordinator.process(category_reports)
                phases.end_phase('success')
            except Exception as e:
                logger.warning(f"Continuity detection failed: {e}")
                phases.end_phase('failed', error=str(e))

            # Phase 2.7: Staleness Check (deterministic, no LLM calls)
            phases.start_phase("Phase 2.7: Staleness Check")
            try:
                logger.info("Phase 2.7: Checking for stale model release coverage...")
                staleness_checker = StalenessChecker(
                    config_dir=self.config_dir,
                    target_date=self.target_date,
                    web_dir=self.web_dir,
                )
                category_reports = staleness_checker.process(category_reports)
                category_reports = await self._ensure_report_category_summaries(category_reports)
                phases.end_phase('success')
            except Exception as e:
                logger.warning(f"Staleness check failed (non-fatal): {e}")
                phases.end_phase('failed', error=str(e))

            # Save analysis checkpoint (post-continuity + staleness)
            self._save_checkpoint('analysis', {
                'category_reports': {cat: report.to_dict() for cat, report in category_reports.items()}
            })

        # Phase 3: Cross-Category Topic Detection
        if resume_from is not None and resume_from > 3:
            checkpoint = self._load_checkpoint('topics')
            if not checkpoint:
                raise RuntimeError("Cannot resume: no checkpoint for Phase 3 (topics)")
            top_topics = self._restore_top_topics(checkpoint)
            topic_thinking = checkpoint.get('thinking', '')
            if not top_topics:
                fallback_topics = self._build_fallback_topics(category_reports)
                if fallback_topics:
                    top_topics = fallback_topics
                    topic_thinking = (
                        f"{topic_thinking}\n\n"
                        "Deterministic fallback used: analyzed category output converted to top topics."
                    ).strip()
                    phases.skip_phase(
                        "Phase 3: Topic Detection",
                        f"loaded empty checkpoint; used {len(top_topics)} fallback topics",
                    )
                else:
                    phases.skip_phase("Phase 3: Topic Detection", "loaded empty checkpoint")
            else:
                phases.skip_phase("Phase 3: Topic Detection", f"loaded from checkpoint ({len(top_topics)} topics)")
        else:
            phases.start_phase("Phase 3: Topic Detection")
            try:
                logger.info("Phase 3: Detecting cross-category topics...")
                top_topics, topic_thinking = await self._detect_cross_category_topics(category_reports)
                if top_topics:
                    phases.end_phase('success', details=f"{len(top_topics)} topics")
                else:
                    fallback_topics = self._build_fallback_topics(category_reports)
                    if fallback_topics:
                        top_topics = fallback_topics
                        topic_thinking = (
                            f"{topic_thinking}\n\n"
                            "Deterministic fallback used: analyzed category output converted to top topics."
                        ).strip()
                        phases.end_phase(
                            'partial',
                            error="no cross-category topics detected",
                            details=f"used {len(top_topics)} fallback topics",
                        )
                    else:
                        phases.end_phase('failed', error="no topics detected")
            except Exception as e:
                logger.error(f"Topic detection failed: {e}")
                fallback_topics = self._build_fallback_topics(category_reports)
                if fallback_topics:
                    top_topics = fallback_topics
                    topic_thinking = (
                        f"Error: {e}\n\n"
                        "Deterministic fallback used: analyzed category output converted to top topics."
                    )
                    phases.end_phase(
                        'partial',
                        error=str(e),
                        details=f"used {len(top_topics)} fallback topics",
                    )
                else:
                    top_topics = []
                    topic_thinking = f"Error: {e}"
                    phases.end_phase('failed', error=str(e))

            self._save_checkpoint('topics', {
                'top_topics': [asdict(t) for t in top_topics],
                'thinking': topic_thinking
            })

        # Phase 4: Generate Executive Summary
        if resume_from is not None and resume_from > 4.5:
            checkpoint = self._load_checkpoint('summary')
            if not checkpoint:
                raise RuntimeError("Cannot resume: no checkpoint for Phase 4 (summary)")
            executive_summary = checkpoint.get('executive_summary', '')
            executive_evidence_items = checkpoint.get('executive_evidence_items', [])
            summary_thinking = checkpoint.get('thinking', '')
            # Restore enriched category summaries
            enriched_summaries = checkpoint.get('enriched_category_summaries', {})
            for category, enriched_summary in enriched_summaries.items():
                if category in category_reports:
                    category_reports[category].category_summary = enriched_summary
            # Restore enriched topic descriptions
            enriched_topics = checkpoint.get('enriched_topics', [])
            if enriched_topics:
                top_topics = self._restore_top_topics({'top_topics': enriched_topics})
            phases.skip_phase("Phase 4: Executive Summary", "loaded from checkpoint")
            phases.skip_phase("Phase 4.5: Link Enrichment", "loaded from checkpoint")
        else:
            phases.start_phase("Phase 4: Executive Summary")
            try:
                logger.info("Phase 4: Generating executive summary...")
                executive_summary, summary_thinking, executive_evidence_items = await self._generate_executive_summary(
                    category_reports, top_topics
                )
                phases.end_phase('success')
            except Exception as e:
                logger.error(f"Executive summary generation failed; using extractive fallback: {e}")
                executive_summary = self._build_executive_summary_fallback(
                    category_reports, top_topics
                )
                executive_evidence_items = []
                summary_thinking = (
                    "Deterministic fallback used after "
                    f"{type(e).__name__} during executive summary generation."
                )
                phases.end_phase(
                    'partial',
                    error=str(e),
                    details="used deterministic summary fallback",
                )

            # Phase 4.5: Link Enrichment
            phases.start_phase("Phase 4.5: Link Enrichment")
            try:
                logger.info("Phase 4.5: Enriching summaries with internal links...")
                enricher = LinkEnricher(self.async_client, self.target_date, prompt_accessor=self.prompt_accessor)
                executive_summary, enriched_category_summaries, top_topics = await enricher.enrich_all(
                    executive_summary, category_reports, top_topics
                )
                for category, enriched_summary in enriched_category_summaries.items():
                    if category in category_reports:
                        category_reports[category].category_summary = enriched_summary
                phases.end_phase('success')
            except Exception as e:
                logger.warning(f"Link enrichment failed: {e}")
                enriched_category_summaries = {}
                phases.end_phase('failed', error=str(e))

            # Save summary checkpoint (post-enrichment)
            self._save_checkpoint('summary', {
                'executive_summary': executive_summary,
                'executive_evidence_items': executive_evidence_items,
                'thinking': summary_thinking,
                'enriched_category_summaries': {cat: report.category_summary for cat, report in category_reports.items()},
                'enriched_topics': [asdict(t) for t in top_topics]
            })

        # Phase 4.6: Ecosystem Enrichment (detect new model releases from news)
        if resume_from is None or resume_from <= 4.6:
            if self.ecosystem_manager and 'news' in category_reports:
                phases.start_phase("Phase 4.6: Ecosystem Enrichment")
                try:
                    logger.info("Phase 4.6: Enriching ecosystem context from news...")
                    news_items = category_reports['news'].all_items
                    enrichment_result = await self.ecosystem_manager.enrich_from_news(
                        news_items, self.async_client
                    )
                    updates = enrichment_result.get('updates_made', 0)
                    if updates > 0:
                        logger.info(f"  Added {updates} new model releases")
                        phases.end_phase('success', details=f"{updates} new releases")
                    else:
                        phases.end_phase('success', details="no new releases")
                except Exception as e:
                    logger.warning(f"Ecosystem enrichment failed: {e}")
                    phases.end_phase('failed', error=str(e))
            else:
                phases.skip_phase("Phase 4.6: Ecosystem Enrichment", "no news data or manager unavailable")
        else:
            phases.skip_phase("Phase 4.6: Ecosystem Enrichment", "loaded from checkpoint")

        # Phase 4.7: Hero Image Generation
        hero_image_url = None
        hero_image_prompt = None

        # Build hero topics - use top_topics, or fall back to category themes
        hero_topics = top_topics
        hero_fallback_used = False
        if not hero_topics and category_reports:
            hero_topics = self._build_fallback_topics(category_reports)
            hero_fallback_used = bool(hero_topics)

        if resume_from is None or resume_from <= 4.7:
            if self.hero_generator and hero_topics:
                phases.start_phase("Phase 4.7: Hero Image")
                try:
                    logger.info("Phase 4.7: Generating hero image...")
                    if hero_fallback_used:
                        logger.info("  Using category themes as fallback (topic detection produced no topics)")
                    hero_result = await self.hero_generator.generate(
                        top_topics=hero_topics,
                        date=self.target_date,
                        output_dir=Path(self.web_dir)
                    )
                    if hero_result:
                        hero_image_url = hero_result['path']
                        hero_file = Path(self.web_dir) / "data" / self.target_date / "hero.webp"
                        if hero_file.exists():
                            mtime = int(hero_file.stat().st_mtime)
                            hero_image_url = f"{hero_image_url}?v={mtime}"
                        hero_image_prompt = hero_result['prompt']
                        logger.info(f"Hero image generated: {hero_image_url}")
                        if hero_fallback_used:
                            phases.end_phase('partial', details="used category themes as fallback")
                        else:
                            phases.end_phase('success')
                    else:
                        logger.warning("Hero image generation returned no result")
                        phases.end_phase('failed', error="no result returned")
                except Exception as e:
                    logger.error(f"Hero image generation failed: {e}")
                    phases.end_phase('failed', error=str(e))
            else:
                if not self.hero_generator:
                    phases.skip_phase("Phase 4.7: Hero Image", "generator not available")
                elif not hero_topics:
                    phases.skip_phase("Phase 4.7: Hero Image", "no topics")
        else:
            phases.skip_phase("Phase 4.7: Hero Image", "loaded from checkpoint")

        # Phase 5: Assemble Result
        phases.start_phase("Phase 5: Assembly")
        logger.info("Phase 5: Assembling final result...")
        total_collected = sum(len(items) for items in gathered_items.values())
        total_analyzed = sum(len(report.all_items) for report in category_reports.values())
        analysis_funnel = {}
        for category in sorted(set(gathered_items) | set(category_reports)):
            collected_count = len(gathered_items.get(category, []))
            analyzed_count = len(category_reports[category].all_items) if category in category_reports else 0
            analysis_funnel[category] = {
                'collected': collected_count,
                'analyzed': analyzed_count,
                'retention_rate': (
                    round(analyzed_count / collected_count, 4)
                    if collected_count else None
                ),
                'wipeout': collected_count > 0 and analyzed_count == 0,
            }

        # Get coverage info from any gatherer (all have the same dates)
        any_gatherer = next(iter(self.gatherers.values()))
        coverage_date = getattr(any_gatherer, 'coverage_date', '')
        coverage_start = any_gatherer.start_time.isoformat() if any_gatherer.start_time else ''
        coverage_end = any_gatherer.end_time.isoformat() if any_gatherer.end_time else ''

        result = OrchestratorResult(
            date=self.target_date,
            executive_summary=executive_summary,
            top_topics=top_topics,
            category_reports=category_reports,
            total_items_collected=total_collected,
            total_items_analyzed=total_analyzed,
            coverage_date=coverage_date,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            collection_status=collection_status,
            analysis_funnel=analysis_funnel,
            executive_evidence_items=executive_evidence_items,
            hero_image_url=hero_image_url,
            hero_image_prompt=hero_image_prompt,
            phase_status=phases.to_dict(),
            llm_telemetry=cost_tracker.get_llm_telemetry(),
            orchestrator_thinking=f"Topic Detection:\n{topic_thinking}\n\nSummary:\n{summary_thinking}"
        )

        # Save result
        self._save_result(result)
        phases.end_phase('success')

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"Orchestrator run completed in {elapsed:.1f}s")
        logger.info(f"  - Total collected: {total_collected}")
        logger.info(f"  - Total analyzed: {total_analyzed}")
        logger.info(f"  - Top topics: {len(top_topics)}")

        # Log collection status summary
        self._log_collection_status(collection_status)

        # Print phase summary before returning
        print("\n" + phases.get_summary())

        # Cost tracking is now handled in the finally block of run_pipeline.py

        return result

    def _build_fallback_topics(self, category_reports: Dict[str, CategoryReport]) -> List[TopTopic]:
        """Build publishable topics from category themes or analyzed items."""
        all_themes = []
        for category, report in category_reports.items():
            for theme in report.themes[:3]:  # Top 3 per category
                all_themes.append((theme, category))

        # Deduplicate by name (case-insensitive)
        seen_names = set()
        unique_themes = []
        for theme, category in all_themes:
            key = theme.name.lower().strip()
            if key not in seen_names:
                seen_names.add(key)
                unique_themes.append((theme, category))

        # Sort by importance, take top 6
        unique_themes.sort(key=lambda x: x[0].importance, reverse=True)
        unique_themes = unique_themes[:6]

        fallback_topics = []
        for theme, category in unique_themes:
            if not theme.name.strip() or not theme.description.strip():
                continue
            fallback_topics.append(TopTopic(
                name=theme.name,
                description=theme.description,
                description_html=self._markdown_links_to_html(theme.description),
                category_breakdown={category: theme.item_count},
                representative_items=[],
                importance=theme.importance
            ))

        if fallback_topics:
            logger.info(f"  Built {len(fallback_topics)} fallback topics from category themes")
            return fallback_topics

        category_labels = {
            "news": "News",
            "research": "Research",
            "social": "Social",
        }
        for category, report in category_reports.items():
            eligible_items = [
                item for item in report.top_items
                if not self._exclude_from_summaries(item)
            ]
            if eligible_items:
                item = eligible_items[0]
                title = item.item.title.strip()
                description = (item.summary or report.category_summary).strip()
                if title and description:
                    fallback_topics.append(TopTopic(
                        name=title,
                        description=description,
                        description_html=self._markdown_links_to_html(description),
                        category_breakdown={category: 1},
                        representative_items=[item.item.id],
                        importance=item.importance_score,
                    ))
                    continue

            description = report.category_summary.strip()
            if description:
                fallback_topics.append(TopTopic(
                    name=f"{category_labels.get(category, category.title())} briefing",
                    description=description,
                    description_html=self._markdown_links_to_html(description),
                    category_breakdown={category: len(report.all_items)},
                    representative_items=[],
                    importance=50,
                ))

        if fallback_topics:
            logger.info(f"  Built {len(fallback_topics)} fallback topics from analyzed category output")
        return fallback_topics

    # --- Checkpoint Methods ---

    def _checkpoint_dir(self) -> str:
        """Get checkpoint directory for current date."""
        path = os.path.join(self.data_dir, 'checkpoints', self.target_date)
        os.makedirs(path, exist_ok=True)
        return path

    def _save_checkpoint(self, phase: str, data: dict):
        """Save checkpoint data for a phase."""
        filepath = os.path.join(self._checkpoint_dir(), f"{phase}.json")
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"  Checkpoint saved: {phase}")
        except Exception as e:
            logger.warning(f"  Failed to save checkpoint for {phase}: {e}")

    def _load_checkpoint(self, phase: str) -> Optional[dict]:
        """Load checkpoint data for a phase. Returns None if missing or corrupt."""
        filepath = os.path.join(self._checkpoint_dir(), f"{phase}.json")
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"  Checkpoint loaded: {phase}")
            return data
        except Exception as e:
            logger.warning(f"  Failed to load checkpoint for {phase}: {e}")
            return None

    def _restore_gathered_items(self, checkpoint: dict) -> Dict[str, List[CollectedItem]]:
        """Restore gathered items from checkpoint data."""
        result = {}
        for category, items_data in checkpoint.get('categories', {}).items():
            result[category] = [CollectedItem.from_dict(item) for item in items_data]
        return result

    def _restore_category_reports(self, checkpoint: dict) -> Dict[str, CategoryReport]:
        """Restore CategoryReport objects from checkpoint data."""
        result = {}
        for category, report_data in checkpoint.get('category_reports', {}).items():
            result[category] = CategoryReport.from_dict(report_data)
        return result

    def _restore_top_topics(self, checkpoint: dict) -> List[TopTopic]:
        """Restore TopTopic objects from checkpoint data."""
        topics = []
        for topic_data in checkpoint.get('top_topics', []):
            topics.append(TopTopic(
                name=topic_data.get('name', ''),
                description=topic_data.get('description', ''),
                description_html=topic_data.get('description_html', ''),
                category_breakdown=topic_data.get('category_breakdown', {}),
                representative_items=topic_data.get('representative_items', []),
                importance=topic_data.get('importance', 50),
                business_implication=topic_data.get('business_implication', ''),
                trend_velocity=topic_data.get('trend_velocity', ''),
            ))
        return topics

    def _detect_resume_point(self) -> Optional[float]:
        """Auto-detect resume point from existing checkpoints."""
        checkpoint_dir = os.path.join(self.data_dir, 'checkpoints', self.target_date)
        if not os.path.exists(checkpoint_dir):
            return None

        # Check in reverse order: summary -> topics -> analysis -> gathering
        checkpoint_phases = [
            ('summary.json', 5.0),    # After Phase 4+4.5, resume from Phase 4.6
            ('topics.json', 4.0),      # After Phase 3, resume from Phase 4
            ('analysis.json', 3.0),    # After Phase 2+2.5, resume from Phase 3
            ('gathering.json', 2.0),   # After Phase 1, resume from Phase 2
        ]

        for filename, resume_point in checkpoint_phases:
            filepath = os.path.join(checkpoint_dir, filename)
            if os.path.exists(filepath):
                logger.info(f"  Auto-resume: found checkpoint {filename}, resuming from phase {resume_point}")
                return resume_point

        return None

    async def _gather_all(self) -> tuple:
        """
        Run all gatherers with proper coordination for link following.

        The workflow is:
        1. Run research, social, and web-scraper gatherers in parallel
        2. Pass social posts to news gatherer for link extraction
        3. Run news gatherer (which also collects RSS)

        Returns:
            Tuple of (Dict mapping category to list of collected items, collection_status dict).
        """
        results = {}
        collection_status = {}
        raw_counts: Dict[str, int] = {}
        durations_ms: Dict[str, int] = {}

        # Phase 1: Run research, social, and web-scraper gatherers in parallel
        logger.info("  Phase 1: Gathering research, social, web scraper...")

        async def gather_category(name: str) -> tuple:
            gatherer = self.gatherers[name]
            started = time.perf_counter()
            try:
                items = await gatherer.gather()
                logger.info(f"    {name} gatherer collected {len(items)} items")
                return name, items, None, int((time.perf_counter() - started) * 1000)
            except Exception as e:
                logger.error(f"    {name} gatherer failed: {e}")
                return name, [], str(e), int((time.perf_counter() - started) * 1000)

        phase1_tasks = [
            gather_category(name)
            for name in ['research', 'social', 'web_scraper']
            if name in self.gatherers
        ]
        phase1_results = await asyncio.gather(*phase1_tasks)

        for name, items, error, duration_ms in phase1_results:
            results[name] = items
            raw_counts[name] = len(items)
            durations_ms[name] = duration_ms
            if error:
                collection_status[name] = {'status': 'failed', 'count': 0, 'error': error}
            else:
                collection_status[name] = {'status': 'success', 'count': len(items), 'error': None}

        # Capture social sub-platform status from SocialGatherer
        social_gatherer = self.gatherers.get('social')
        if social_gatherer and hasattr(social_gatherer, 'get_collection_status'):
            social_platform_status = social_gatherer.get_collection_status()
            for platform, status in social_platform_status.items():
                collection_status[f'social_{platform}'] = status
                
        # Capture web_scraper per-url status
        web_scraper = self.gatherers.get('web_scraper')
        if web_scraper and hasattr(web_scraper, 'get_collection_status'):
            scraper_status = web_scraper.get_collection_status()
            for url, status in scraper_status.items():
                collection_status[url] = status
            if scraper_status:
                successful = sum(
                    1 for status in scraper_status.values()
                    if status.get('status') == 'success'
                )
                failed = sum(
                    1 for status in scraper_status.values()
                    if status.get('status') == 'failed'
                )
                partial = sum(
                    1 for status in scraper_status.values()
                    if status.get('status') == 'partial'
                )
                if failed or partial:
                    collection_status['web_scraper'] = {
                        'status': 'partial' if successful or partial else 'failed',
                        'count': len(results.get('web_scraper', [])),
                        'error': (
                            f'{failed} failed and {partial} partial out of '
                            f'{len(scraper_status)} configured sites'
                        ),
                    }

        # Phase 2: Run news gatherer with social posts for link following
        logger.info("  Phase 2: Gathering news with link following...")
        social_posts = results.get('social', [])

        started = time.perf_counter()
        try:
            news_gatherer = self.gatherers['news']
            news_items = await news_gatherer.gather(social_posts=social_posts)
            durations_ms['news'] = int((time.perf_counter() - started) * 1000)
            logger.info(f"    news gatherer collected {len(news_items)} items")
            results['news'] = news_items
            collection_status['news'] = {'status': 'success', 'count': len(news_items), 'error': None}
        except Exception as e:
            durations_ms['news'] = int((time.perf_counter() - started) * 1000)
            logger.error(f"    news gatherer failed: {e}")
            results['news'] = []
            collection_status['news'] = {'status': 'failed', 'count': 0, 'error': str(e)}

        # Phase 3: gather external trend sources and merge into news
        logger.info("  Phase 3: Gathering Hacker News and GitHub Trending...")
        hn_items = []
        gh_items = []
        try:
            started = time.perf_counter()
            hn_items = await self.hackernews_gatherer.gather()
            durations_ms['hackernews'] = int((time.perf_counter() - started) * 1000)
            collection_status['hackernews'] = {'status': 'success', 'count': len(hn_items), 'error': None}
        except Exception as e:
            durations_ms['hackernews'] = int((time.perf_counter() - started) * 1000)
            collection_status['hackernews'] = {'status': 'failed', 'count': 0, 'error': str(e)}
            logger.warning(f"    HackerNews gatherer failed: {e}")
        try:
            started = time.perf_counter()
            gh_items = await self.github_trending_gatherer.gather()
            durations_ms['github_trending'] = int((time.perf_counter() - started) * 1000)
            collection_status['github_trending'] = {'status': 'success', 'count': len(gh_items), 'error': None}
        except Exception as e:
            durations_ms['github_trending'] = int((time.perf_counter() - started) * 1000)
            collection_status['github_trending'] = {'status': 'failed', 'count': 0, 'error': str(e)}
            logger.warning(f"    GitHubTrending gatherer failed: {e}")

        if results.get('news') is not None and hn_items:
            results['news'].extend(hn_items)
            
        if results.get('news') is not None and results.get('web_scraper'):
            results['news'].extend(results['web_scraper'])
            
        if results.get('news') is not None:
            raw_counts['news'] = len(results['news'])
            results['news'] = deduplicate_items(results['news'])
            collection_status['news']['count'] = len(results['news'])

        # Store github_trending as its own distinct category
        results['github_trending'] = gh_items

        raw_counts.setdefault('hackernews', len(hn_items))
        raw_counts.setdefault('github_trending', len(gh_items))
        source_items = dict(results)
        source_items['hackernews'] = hn_items
        self._decorate_collection_status(
            collection_status, source_items, raw_counts, durations_ms
        )

        return results, collection_status

    def _decorate_collection_status(
        self,
        collection_status: Dict[str, Dict[str, Any]],
        source_items: Dict[str, List[CollectedItem]],
        raw_counts: Dict[str, int],
        durations_ms: Dict[str, int],
    ) -> None:
        """Add per-source health metrics and persist rolling last-success state."""
        health_path = Path(self.web_dir) / 'data' / 'source-health.json'
        previous: Dict[str, Any] = {}
        try:
            if health_path.exists():
                previous = json.loads(health_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Could not read previous source health: {exc}")

        observed_at = datetime.now().isoformat()
        expected_coverage_date = next(
            (
                str(getattr(gatherer, 'coverage_date'))
                for gatherer in self.gatherers.values()
                if getattr(gatherer, 'coverage_date', None)
            ),
            '',
        )
        previous_sources = previous.get('sources', {}) if isinstance(previous, dict) else {}
        persisted_sources: Dict[str, Any] = {}

        for source, status in collection_status.items():
            if not isinstance(status, dict):
                continue
            items = source_items.get(source, [])
            raw_count = int(raw_counts.get(source, status.get('count') or len(items)))
            final_count = int(status.get('count') or len(items))
            duplicates_removed = max(0, raw_count - final_count)
            dated_items = [item for item in items if getattr(item, 'published', None)]
            fresh_items = [
                item for item in dated_items
                if expected_coverage_date and str(getattr(item, 'published', '')).startswith(
                    expected_coverage_date
                )
            ]
            prior = previous_sources.get(source, {}) if isinstance(previous_sources, dict) else {}
            succeeded = status.get('status') in {'success', 'partial'}
            last_success = observed_at if succeeded else prior.get('last_success_at')
            last_nonempty = observed_at if succeeded and final_count > 0 else prior.get('last_nonempty_at')
            newest = max(
                (str(getattr(item, 'published', '')) for item in dated_items),
                default=None,
            )
            status.update({
                'raw_count': raw_count,
                'duration_ms': int(durations_ms.get(source, status.get('duration_ms') or 0)),
                'duplicates_removed': duplicates_removed,
                'duplicate_rate': round(duplicates_removed / raw_count, 4) if raw_count else 0.0,
                'fresh_items': len(fresh_items),
                'freshness_rate': round(len(fresh_items) / len(dated_items), 4) if dated_items else None,
                'newest_item_at': newest,
                'last_success_at': last_success,
                'last_nonempty_at': last_nonempty,
            })
            persisted_sources[source] = dict(status)

        try:
            health_path.parent.mkdir(parents=True, exist_ok=True)
            health_path.write_text(
                json.dumps({'updated_at': observed_at, 'sources': persisted_sources}, indent=2, ensure_ascii=False),
                encoding='utf-8',
            )
        except OSError as exc:
            logger.warning(f"Could not persist source health: {exc}")

    async def _apply_pre_analysis_filters(
        self,
        gathered_items: Dict[str, List[CollectedItem]],
    ) -> Dict[str, List[CollectedItem]]:
        news_items = list(gathered_items.get("news", []))
        if not news_items:
            return gathered_items

        filtered_news, keyword_matches = self.keyword_filter.filter_items(news_items)
        max_per_keyword = 3
        if self.provider_config and self.provider_config.pipeline:
            max_per_keyword = int(getattr(self.provider_config.pipeline, "max_news_per_keyword", 3) or 3)
        filtered_news = apply_keyword_limit(filtered_news, keyword_matches, max_per_keyword=max_per_keyword)
        gathered_items["news"] = filtered_news
        logger.info(
            f"Pre-analysis filters kept {len(filtered_news)}/{len(news_items)} news items "
            f"(keyword + per-keyword limit; semantic relevance runs once in NewsAnalyzer)"
        )
        return gathered_items

    async def _analyze_all(
        self,
        gathered_items: Dict[str, List[CollectedItem]]
    ) -> Dict[str, CategoryReport]:
        """
        Run all analyzers in parallel with grounding context.

        Args:
            gathered_items: Dict mapping category to collected items.

        Returns:
            Dict mapping category to CategoryReport.
        """
        # Re-instantiate analyzers with grounding context
        # (they were created in __init__ without it)
        analyzers_with_context = {
            'news': NewsAnalyzer(
                llm_client=self.llm_client,
                async_client=self.async_client,
                data_dir=self.data_dir,
                config_dir=self.config_dir,
                target_date=self.target_date,
                web_dir=self.web_dir,
                grounding_context=self.grounding_context,
                prompt_accessor=self.prompt_accessor
            ),
            'research': ResearchAnalyzer(
                llm_client=self.llm_client,
                async_client=self.async_client,
                data_dir=self.data_dir,
                config_dir=self.config_dir,
                target_date=self.target_date,
                web_dir=self.web_dir,
                grounding_context=self.grounding_context,
                prompt_accessor=self.prompt_accessor
            ),
            'social': SocialAnalyzer(
                llm_client=self.llm_client,
                async_client=self.async_client,
                data_dir=self.data_dir,
                config_dir=self.config_dir,
                target_date=self.target_date,
                web_dir=self.web_dir,
                grounding_context=self.grounding_context,
                prompt_accessor=self.prompt_accessor
            ),
            'github_trending': GitHubTrendingAnalyzer(
                llm_client=self.llm_client,
                async_client=self.async_client,
                data_dir=self.data_dir,
                config_dir=self.config_dir,
                target_date=self.target_date,
                web_dir=self.web_dir,
                grounding_context=self.grounding_context,
                prompt_accessor=self.prompt_accessor
            )
        }
        # Keep the actual grounded analyzer instances available for quality
        # repair after continuity/staleness sanitization.
        self.analyzers = analyzers_with_context

        async def analyze_category(
            name: str,
            analyzer: BaseAnalyzer,
            items: List[CollectedItem]
        ) -> tuple:
            logger.info(f"  Starting {name} analyzer with {len(items)} items...")
            try:
                report = await analyzer.analyze(items)
                logger.info(f"  {name} analyzer completed. Top items: {len(report.top_items)}")
                return name, report
            except Exception as e:
                logger.error(f"  {name} analyzer failed: {e}")
                # Return empty report on failure
                return name, CategoryReport(
                    category=name,
                    top_items=[],
                    all_items=[],
                    category_summary=f"Analysis failed: {e}",
                    themes=[],
                    cross_signals=[],
                    total_collected=len(items)
                )

        # Run all analyzers in parallel
        tasks = [
            analyze_category(name, analyzers_with_context[name], gathered_items.get(name, []))
            for name in analyzers_with_context.keys()
        ]
        results = await asyncio.gather(*tasks)

        return dict(results)

    async def _ensure_report_category_summaries(
        self,
        category_reports: Dict[str, CategoryReport],
    ) -> Dict[str, CategoryReport]:
        """Repair summaries made empty/generic/short by analysis or sanitization."""
        for category, report in category_reports.items():
            analyzer = self.analyzers.get(category)
            if not analyzer or not hasattr(analyzer, '_ensure_category_summary'):
                continue
            try:
                report.category_summary = await analyzer._ensure_category_summary(
                    report.category_summary,
                    report.top_items,
                )
            except Exception as exc:
                logger.warning(
                    f"Post-analysis category summary repair failed for {category}: {exc}"
                )
        return category_reports

    def _markdown_links_to_html(self, text: str) -> str:
        """Convert markdown links [text](url) to HTML <a> tags safely."""
        import re
        import html
        pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        def safe_link(m):
            label, url = m.group(1), m.group(2)
            if not re.match(r'^https?://', url.strip(), re.IGNORECASE):
                return html.escape(label)
            safe_label = html.escape(label)
            safe_url = html.escape(url.strip())
            return f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_label}</a>'
        return re.sub(pattern, safe_link, text)

    def _exclude_from_summaries(self, item: AnalyzedItem) -> bool:
        metadata = item.item.metadata if isinstance(item.item.metadata, dict) else {}
        freshness = metadata.get('freshness') if isinstance(metadata.get('freshness'), dict) else {}
        return bool(freshness.get('exclude_from_summaries'))

    def _current_item_categories(
        self, category_reports: Dict[str, CategoryReport]
    ) -> Dict[str, str]:
        """Map current, summary-eligible item IDs to their real categories."""
        return {
            item.item.id: category
            for category, report in category_reports.items()
            for item in report.all_items
            if item.item.id and not self._exclude_from_summaries(item)
        }

    def _validated_evidence_ids(
        self,
        raw_ids: Any,
        item_categories: Dict[str, str],
        minimum_categories: int,
        context: str,
    ) -> List[str]:
        """Return unique current evidence IDs or raise on unsupported output."""
        if not isinstance(raw_ids, list) or not raw_ids:
            raise ValueError(f"{context} has no evidence_item_ids")
        evidence_ids = []
        for raw_id in raw_ids:
            if not isinstance(raw_id, str) or not raw_id.strip():
                raise ValueError(f"{context} contains an invalid evidence item ID")
            item_id = raw_id.strip()
            if item_id not in item_categories:
                raise ValueError(f"{context} references non-current item {item_id!r}")
            if item_id not in evidence_ids:
                evidence_ids.append(item_id)
        covered_categories = {item_categories[item_id] for item_id in evidence_ids}
        if len(covered_categories) < minimum_categories:
            raise ValueError(
                f"{context} evidence covers {len(covered_categories)} categories; "
                f"minimum is {minimum_categories}"
            )
        return evidence_ids

    async def _detect_cross_category_topics(
        self,
        category_reports: Dict[str, CategoryReport]
    ) -> tuple:
        """
        Detect topics that span multiple categories.

        Uses ULTRATHINK for deep analysis across all categories.

        Returns:
            Tuple of (list of TopTopic, thinking string).
        """
        # Build context from all category reports with URLs for linking
        context_parts = []
        item_categories = self._current_item_categories(category_reports)
        for category, report in category_reports.items():
            context_parts.append(f"=== {category.upper()} ===")
            context_parts.append(f"Summary: {report.category_summary}")
            context_parts.append(f"Themes: {', '.join(t.name for t in report.themes)}")
            summary_items = [
                item for item in report.top_items
                if not self._exclude_from_summaries(item)
            ]
            context_parts.append(f"Top items ({len(summary_items)}):")
            for i, item in enumerate(summary_items[:10], 1):
                # Include URL so LLM can create inline links
                context_parts.append(f"  {i}. ID: {item.item.id}")
                context_parts.append(f"     Title: {normalize_untrusted_text(item.item.title)[:300]}")
                context_parts.append(f"     URL: {normalize_untrusted_text(item.item.url)[:512]}")
                context_parts.append(f"     Source: {item.item.source}")
                if item.summary:
                    context_parts.append(f"     Summary: {item.summary[:150]}...")
            context_parts.append("")

        context = "\n".join(context_parts)

        # CWE-1427: topic-detection instructions travel in the system prompt;
        # the category-report context (which quotes untrusted titles/URLs)
        # travels in the user message inside a nonce fence.
        nonce = new_fence_nonce()
        if self.prompt_accessor:
            instructions = self.prompt_accessor.get_orchestration_prompt(
                'topic_detection', {'context': DATA_POINTER}
            )
        else:
            # Fallback to inline prompt for backwards compatibility
            instructions = f"""You are an enterprise AI strategy advisor. Analyze the following category reports from today's AI news collection and identify the TOP 6 cross-category strategic topics that appear across multiple domains. If there are fewer than 6 distinct topics worth covering, return exactly 3 instead. Use a rigorous, decision-oriented, top-tier strategy-consulting style, but never mention a consulting firm or internal writing persona in the output.

{DATA_POINTER}

For each cross-category topic, provide a highly detailed, strategic brief:
1. A concise name (2-5 words)
2. A description (3-5 sentences) as PLAIN TEXT without any links.
   - DO NOT include any markdown links or URLs.
   - Write a rich, cohesive narrative synthesizing the news, research, and social chatter. Reference specific companies, models, and papers by name.
   - Links will be added automatically in a later processing step.
3. A business implication (business_implication) explaining the strategic impact on Enterprise markets, C-level decision making, and competitive dynamics (2-3 sentences).
4. A trend velocity (trend_velocity) as a single word (e.g., "Emerging", "Accelerating", "Mainstream", "Disruptive").
5. Which categories it appears in and roughly how many items
6. Exact current item IDs in `representative_items`, with at least one item from each claimed category and at least two different categories
7. An importance score (0-100)

IMPORTANT: Write descriptions as plain text WITHOUT any links. Reference sources by name (e.g., "Google announced...", "A Stanford paper found...") but do NOT include URLs or markdown link syntax.

Example description format:
"The competitive landscape for reasoning models shifted dramatically today as Google announced a major breakthrough, while researchers at Stanford published findings showing unexpected benchmark saturation. The developer community on GitHub and social media is already mobilizing to integrate these capabilities into enterprise workflows, signaling a rapid transition from research to production."

Return your analysis as JSON:
```json
{{
  "topics": [
    {{
      "name": "Topic Name",
      "description": "Plain text description referencing sources by name without any links.",
      "business_implication": "Explanation of the impact on B2B/Enterprise markets and AI strategy (1-2 sentences).",
      "trend_velocity": "A one-word indicator (e.g., 'Emerging', 'Accelerating', 'Mainstream', 'Fading')",
      "categories": {{"news": 5, "research": 2, "social": 10, "github_trending": 4}},
      "representative_items": ["current-news-item-id", "current-social-item-id"],
      "importance": 85
    }}
  ]
}}
```

Focus on genuinely cross-cutting themes representing the day's most significant AI developments.

RELEASE-DATE GROUNDING (mandatory check for any topic that names or implies a model release):
- For every model named in a candidate topic, look up the model in the AI ECOSYSTEM GROUNDING section at the top of your system prompt.
- If the model's GA date is more than 7 days before the coverage date, do NOT frame the topic as a "release", "launch", "strategic shift", "historically significant move", "major upgrade", or similar. Such items are coverage, tutorials, or follow-up discussion of an existing model — frame the topic accordingly (e.g., "Local inference tooling for GPT-OSS" rather than "Open-Weight Models & Local Inference: a strategic shift").
- A "release" topic must center on a model whose GA date is on or within ~7 days of the coverage date.
- Continuation/follow-up topics about a model that was already covered as a release in the prior 1-3 days should be downweighted (importance ≤ 65) unless there is a genuinely new development beyond initial coverage."""

        system_prompt = build_hardened_system(
            instructions, nonce, grounding=self.grounding_context
        )
        user_message = build_fenced_user_message(
            context, nonce,
            task_line="Analyze the fenced category reports below according to your system instructions.",
        )

        try:
            response = await self.async_client.call_with_thinking(
                messages=[{"role": "user", "content": user_message}],
                system=system_prompt,
                profile=ThinkingLevel.ULTRATHINK,
                caller="orchestrator.topics",
                full_output_budget=True,
            )

            if response.stop_reason == "max_tokens":
                logger.error(
                    "Topic detection response truncated at max_tokens after escalation; "
                    "topic JSON may be incomplete."
                )

            # Parse JSON response. Models occasionally wrap the object in a
            # ```json fence or emit a short prose preamble; extract_json_str
            # recovers the JSON substring (the fragile .strip('```json')
            # char-set stripping used to drop the whole day's topics with
            # "Expecting value: line 1 column 1").
            result = json.loads(extract_json_str(response.content))

            topics = []
            for topic_data in result.get('topics', []):
                if not isinstance(topic_data, dict):
                    continue
                try:
                    evidence_ids = self._validated_evidence_ids(
                        topic_data.get('representative_items'),
                        item_categories,
                        minimum_categories=2,
                        context=f"topic {topic_data.get('name', '<unnamed>')!r}",
                    )
                except ValueError as exc:
                    logger.warning("Dropping unsupported cross-category topic: %s", exc)
                    continue
                category_counts = Counter(item_categories[item_id] for item_id in evidence_ids)
                description = sanitize_editorial_text(topic_data.get('description', ''))
                topics.append(TopTopic(
                    name=sanitize_editorial_text(topic_data['name']),
                    description=description,
                    description_html=self._markdown_links_to_html(description),
                    category_breakdown=dict(category_counts),
                    representative_items=evidence_ids,
                    importance=topic_data.get('importance', 50),
                    business_implication=sanitize_editorial_text(
                        topic_data.get('business_implication', '')
                    ),
                    trend_velocity=sanitize_editorial_text(topic_data.get('trend_velocity', '')),
                ))

            # Sort by importance
            topics.sort(key=lambda t: t.importance, reverse=True)

            return topics, response.thinking or ""

        except Exception as e:
            logger.error(f"Cross-category topic detection failed: {e}")
            return [], f"Error: {e}"

    def _load_previous_summaries(self, lookback_days: int = 3) -> str:
        """
        Load executive summaries from previous days to avoid repetition.

        Args:
            lookback_days: Number of days to look back.

        Returns:
            Formatted string with previous summaries for context.
        """
        return format_previous_coverage(
            load_previous_summaries(
                self.web_dir,
                self.target_date,
                lookback_days=lookback_days,
            )
        )

    async def _generate_executive_summary(
        self,
        category_reports: Dict[str, CategoryReport],
        top_topics: List[TopTopic]
    ) -> tuple:
        """
        Generate an executive summary of all AI news for the day.

        Uses DEEP thinking for quality synthesis.

        Returns:
            Tuple of (summary string, thinking string, current evidence item IDs).
        """
        # Load previous days' summaries to avoid repetition
        previous_coverage = self._load_previous_summaries(lookback_days=3)

        item_categories = self._current_item_categories(category_reports)
        current_categories = []
        for category, report in category_reports.items():
            summary_items = [
                item for item in report.top_items
                if not self._exclude_from_summaries(item)
            ]
            current_categories.append((
                category,
                report.category_summary,
                [
                    {
                        "id": item.item.id,
                        "title": normalize_untrusted_text(item.item.title)[:300],
                        "summary": normalize_untrusted_text(item.summary)[:500],
                    }
                    for item in summary_items[:8]
                ],
            ))

        context = build_executive_context(
            self.target_date,
            previous_coverage,
            [(topic.name, topic.description) for topic in top_topics[:6]],
            current_categories,
        )

        # CWE-1427: summary instructions travel in the system prompt; the
        # aggregated context travels in the user message inside a nonce fence.
        nonce = new_fence_nonce()
        if self.prompt_accessor:
            instructions = self.prompt_accessor.get_orchestration_prompt(
                'executive_summary', {'context': DATA_POINTER}
            )
        else:
            # Fallback to inline prompt for backwards compatibility
            instructions = f"""You are an enterprise AI strategy advisor. Write a compact, scan-first strategic intelligence briefing of today's AI developments.

CRITICAL: Synthesize implications rather than listing headlines. Be concise: the complete briefing must stay below 650 words.

{DATA_POINTER}

FORMAT YOUR SUMMARY LIKE THIS:

#### Executive Briefing
Write 3-4 bullets, each no more than 45 words. Lead with the strategic implication, then the strongest supporting evidence. Integrate material social signals only when they change the interpretation.

#### Safety & Regulation
Write 2-3 bullets, each no more than 40 words, covering material safety, governance, security, or regulatory developments. Skip the section if evidence is weak.

#### Research Highlights
Write 2-3 bullets, each no more than 40 words. State the result and its practical relevance. Skip the section if evidence is weak.

#### Trending Repositories
Write 2-3 bullets, each no more than 35 words. Group related repositories where useful and explain why the momentum matters. Skip the section if evidence is weak.

#### Signals to Watch
Write 2-3 bullets, each no more than 35 words, covering genuinely forward-looking signals supported by current evidence.

FORMATTING RULES:
- Target audience: enterprise C-level executives and AI leaders.
- Use a rigorous, decision-oriented, top-tier strategy-consulting style, but never mention a consulting firm or internal writing persona in the output.
- Every section body MUST use bullets; do not place prose paragraphs between headings.
- A bullet must express one decision-relevant insight, not merely repeat a headline.
- Keep every subsection heading exactly as specified and never put Markdown links inside headings.
- DO NOT include a "Sentiment & Controversy" section.
- Use **bold** selectively for the key entity or metric; avoid visual clutter.
- Write in an authoritative, clear, and insight-driven executive tone - no hype or speculation.
- Avoid repetition of older headlines.
- The pipeline will automatically inject contextual "read more" links into your text after generation, so you do not need to format Markdown links yourself. Just write the text naturally as plain text.

EVIDENCE REQUIREMENT:
- Treat everything before `=== END PREVIOUS DAYS' COVERAGE ===` as historical anti-repetition context only.
- Use only developments supported by CURRENT ITEMS inside `=== TODAY'S DATA (CURRENT EVIDENCE) ===`.
- If a claim appears only in historical coverage, omit it from the new briefing.
- Return valid JSON only: {{"executive_summary": "the complete Markdown briefing", "evidence_item_ids": ["current-item-id-1", "current-item-id-2"]}}
- Use exact CURRENT ITEM IDs and cover at least two non-empty categories when two or more categories are available."""

        system_prompt = build_hardened_system(
            instructions, nonce, grounding=self.grounding_context
        )
        user_message = build_fenced_user_message(
            context, nonce,
            task_line="Write the executive summary from the fenced context below according to your system instructions.",
        )

        response = await self.async_client.call_with_thinking(
            messages=[{"role": "user", "content": user_message}],
            system=system_prompt,
            profile=ThinkingLevel.DEEP,
            caller="orchestrator.summary",
            full_output_budget=True,
        )

        if response.stop_reason == "max_tokens":
            logger.error(
                "Executive summary truncated at max_tokens after escalation; "
                "output may be incomplete."
            )

        result = json.loads(extract_json_str(response.content or ""))
        if not isinstance(result, dict):
            raise ValueError("Executive summary response is not a JSON object")
        content = sanitize_editorial_text(result.get('executive_summary', '')).strip()
        content = re.sub(
            r"(?ims)^#{1,6}\s+Sentiment\s*&\s*Controversy\s*$.*?(?=^#{1,6}\s+|\Z)",
            "",
            content,
        ).strip()
        word_count = len(content.split())
        if word_count > MAX_EXECUTIVE_SUMMARY_WORDS:
            raise ValueError(
                "Executive summary is too verbose "
                f"({word_count} > {MAX_EXECUTIVE_SUMMARY_WORDS} words)"
            )
        allowed_headings = {
            "Executive Briefing",
            "Safety & Regulation",
            "Research Highlights",
            "Trending Repositories",
            "Signals to Watch",
        }
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#### "):
                heading = stripped[5:].strip()
                if heading not in allowed_headings or "[" in heading or "](" in heading:
                    raise ValueError(f"Invalid executive-summary heading: {heading!r}")
                continue
            if not stripped.startswith(("- ", "* ")):
                raise ValueError(
                    "Executive summary is not scan-first: section bodies must use bullets"
                )
        if "#### Executive Briefing" not in content:
            raise ValueError("Executive summary is missing the Executive Briefing section")
        active_categories = set(item_categories.values())
        minimum_categories = min(2, len(active_categories))
        if minimum_categories == 0:
            raise ValueError("Executive summary has no current items available as evidence")
        evidence_ids = self._validated_evidence_ids(
            result.get('evidence_item_ids'),
            item_categories,
            minimum_categories=minimum_categories,
            context="executive summary",
        )
        if len(content) < MIN_EXECUTIVE_SUMMARY_CHARS:
            raise ValueError(
                "Executive summary response was empty or too short "
                f"({len(content)} < {MIN_EXECUTIVE_SUMMARY_CHARS} characters)"
            )

        return content, response.thinking or "", evidence_ids

    def _build_executive_summary_fallback(
        self,
        category_reports: Dict[str, CategoryReport],
        top_topics: List[TopTopic],
    ) -> str:
        """Build a publishable summary from already analyzed pipeline output."""
        lines: List[str] = []

        def compact(value: str, limit: int) -> str:
            text = " ".join(normalize_untrusted_text(value or "").split())
            if len(text) <= limit:
                return text
            return text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "."

        usable_topics = [
            topic for topic in top_topics
            if compact(topic.name, 120) and compact(topic.description, 700)
        ]
        lines.append("#### Executive Briefing")
        if usable_topics:
            for topic in usable_topics[:4]:
                lines.append(
                    f"- **{compact(topic.name, 120)}**: "
                    f"{compact(topic.description, 360)}"
                )

        category_sections = {
            "research": "Research Highlights",
            "github_trending": "Trending Repositories",
            "social": "Signals to Watch",
        }
        for category, report in category_reports.items():
            section = category_sections.get(category)
            if not section:
                continue
            eligible_items = [
                item for item in report.top_items
                if not self._exclude_from_summaries(item)
            ]
            category_lines: List[str] = []
            for item in eligible_items[:2]:
                title = compact(item.item.title, 180)
                summary = compact(item.summary, 300)
                if title and summary:
                    category_lines.append(f"- **{title}**: {summary}")

            if not eligible_items and report.category_summary:
                summary = compact(report.category_summary, 400)
                if summary:
                    category_lines.append(f"- {summary}")

            if category_lines:
                lines.extend(["", f"#### {section}", *category_lines])

        return "\n".join(lines).strip()

    def _save_result(self, result: OrchestratorResult):
        """Save orchestrator result to JSON file."""
        processed_dir = os.path.join(self.data_dir, 'processed')
        os.makedirs(processed_dir, exist_ok=True)

        filename = f"orchestrator_result_{self.target_date}.json"
        filepath = os.path.join(processed_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

        logger.info(f"Saved orchestrator result to {filepath}")

    def _log_collection_status(self, collection_status: Dict[str, Dict[str, Any]]):
        """Log collection status summary with clear indicators and save endpoint_status.json."""
        try:
            target_dir = os.path.join(self.web_dir, 'data', self.target_date)
            os.makedirs(target_dir, exist_ok=True)
            status_file = os.path.join(target_dir, 'endpoint_status.json')
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(collection_status, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved endpoint collection status to {status_file}")
        except Exception as e:
            logger.error(f"Failed to save endpoint status report: {e}")

        logger.info("\n" + "=" * 60)
        logger.info("COLLECTION STATUS SUMMARY")
        logger.info("=" * 60)

        has_failures = False
        has_partial = False

        # Group by category vs sub-platform
        main_sources = ['news', 'research', 'social', 'web_scraper', 'hackernews', 'github_trending']
        sub_platforms = [k for k in collection_status.keys() if k.startswith('social_')]

        for source in main_sources:
            status = collection_status.get(source, {})
            self._log_source_status(source, status)
            if status.get('status') == 'failed':
                has_failures = True
            elif status.get('status') in {'partial', 'unknown'}:
                has_partial = True

        if sub_platforms:
            logger.info("\n  Social Platform Breakdown:")
            for platform in sorted(sub_platforms):
                status = collection_status.get(platform, {})
                platform_name = platform.replace('social_', '').capitalize()
                self._log_source_status(f"    {platform_name}", status, indent=True)
                if status.get('status') == 'failed':
                    has_failures = True
                elif status.get('status') == 'partial':
                    has_partial = True

        logger.info("=" * 60)

        # Clear warning at the end if there were issues
        if has_failures:
            logger.warning("⚠️  SOME SOURCES FAILED TO COLLECT - check errors above")
        elif has_partial:
            logger.warning("⚠️  SOME SOURCES HAD PARTIAL COLLECTION - check warnings above")
        else:
            logger.info("✅ All sources collected successfully")

    def _log_source_status(self, source: str, status: Dict[str, Any], indent: bool = False):
        """Log status for a single source."""
        prefix = "  " if indent else ""
        status_val = status.get('status', 'unknown')
        count = status.get('count', 0)
        error = status.get('error')

        if status_val == 'success':
            logger.info(f"{prefix}✓ {source}: {count} items")
        elif status_val == 'partial':
            logger.warning(f"{prefix}⚠ {source}: {count} items (partial - {error})")
        elif status_val == 'failed':
            logger.error(f"{prefix}✗ {source}: FAILED - {error}")
        elif status_val == 'skipped':
            logger.info(f"{prefix}- {source}: skipped ({error})")
        else:
            logger.warning(f"{prefix}? {source}: unknown status")

    async def close(self):
        """Close LLM clients."""
        self.llm_client.close()
        await self.async_client.close()
