"""Focused regression checks for scraper and summary-pipeline resilience."""

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx

from agents.analyzers.github_trending_analyzer import GitHubTrendingAnalyzer
from agents.base import BaseAnalyzer, CollectedItem
from agents.cache import AnalysisCache
from agents.cost_tracker import CostTracker
from agents.gatherers.social_gatherer import SocialGatherer
from agents.gatherers.webscraper_gatherer import WebScraperGatherer
from agents.link_enricher import LinkEnricher
from agents.llm_client import AsyncLLMRouter, LLMResponse, ThinkingLevel
from agents.orchestrator import MainOrchestrator
from agents.quality_score import calculate_quality_score
from generators.json_generator import JSONGenerator
from scripts.validate_report import validate


class ScraperResilienceTests(unittest.TestCase):
    def test_tweet_entity_expanded_urls_are_preserved(self):
        tweet = {
            "entities": {
                "urls": [
                    {
                        "url": "https://t.co/short",
                        "expanded_url": "https://example.com/article",
                    }
                ]
            }
        }

        self.assertEqual(
            SocialGatherer._extract_tweet_urls(tweet),
            ["https://example.com/article"],
        )

    def test_twitter_search_uses_at_most_twenty_accounts_and_logs_empty_chunks(self):
        with tempfile.TemporaryDirectory() as config_dir:
            with open(os.path.join(config_dir, "twitter_accounts.txt"), "w") as accounts_file:
                accounts_file.write("\n".join(f"account{index}" for index in range(21)))

            gatherer = SocialGatherer(config_dir=config_dir, target_date="2026-08-08")
            response = MagicMock()
            response.json.return_value = {"tweets": []}

            with patch("agents.gatherers.social_gatherer.GETXAPI_KEY", "test-key"), \
                 patch("agents.gatherers.social_gatherer.requests.get", return_value=response) as get, \
                 patch("agents.gatherers.social_gatherer.time.sleep"), \
                 self.assertLogs("agents.gatherers.social_gatherer", "WARNING") as logs:
                tweets = gatherer._twitter_search(gatherer.twitter_users)

        self.assertEqual(tweets, [])
        self.assertEqual(get.call_count, 2)
        self.assertTrue(all(
            call.kwargs["params"]["q"].count("from:") <= 20
            for call in get.call_args_list
        ))
        self.assertTrue(any("returned no tweets" in message for message in logs.output))

    def test_truncated_scraper_array_recovers_complete_objects(self):
        content = (
            '[{"title":"Complete","url":"https://example.com/one"},'
            '{"title":"Truncated","url":"https://example.com/two"'
        )

        recovered = WebScraperGatherer._recover_complete_json_objects(content)

        self.assertEqual(
            recovered,
            [{"title": "Complete", "url": "https://example.com/one"}],
        )


class BatchCoverageTests(unittest.TestCase):
    @staticmethod
    def _item(item_id):
        return CollectedItem(
            id=item_id,
            title=item_id,
            content="",
            url=f"https://example.com/{item_id}",
            author="",
            published="2026-08-06T00:00:00",
            source="example",
            source_type="rss",
        )

    def test_valid_but_incomplete_batch_json_is_rejected(self):
        previous = os.environ.get("ANALYZER_MIN_BATCH_COVERAGE")
        os.environ["ANALYZER_MIN_BATCH_COVERAGE"] = "0.85"
        try:
            expected = [self._item(str(index)) for index in range(4)]
            result = {"items": [{"id": str(index)} for index in range(3)]}

            error = BaseAnalyzer._batch_coverage_error(result, expected)

            self.assertIn("3/4", error)
        finally:
            if previous is None:
                os.environ.pop("ANALYZER_MIN_BATCH_COVERAGE", None)
            else:
                os.environ["ANALYZER_MIN_BATCH_COVERAGE"] = previous


class PublicationQualityGateTests(unittest.TestCase):
    def test_high_quality_scored_report_is_publishable(self):
        top_items = [
            {
                "id": f"item-{index}",
                "title": f"AI story {index}",
                "url": f"https://source-{index}.example/story",
                "source": f"source-{index}",
            }
            for index in range(5)
        ]
        summary = {
            "date": "2026-08-09",
            "executive_summary": "x" * 800,
            "top_topics": [{"name": f"Topic {index}"} for index in range(3)],
            "total_items_collected": 10,
            "total_items_analyzed": 10,
            "phase_status": [
                {"name": "Phase 3: Topic Detection", "status": "success"},
                {"name": "Phase 4: Executive Summary", "status": "success"},
            ],
            "generation_quality": {"fallback_used": False},
            "collection_status": {"overall": "success", "sources": []},
            "categories": {
                "news": {
                    "count": 10,
                    "category_summary": "y" * 500,
                    "analysis_quality": {"total_items": 10, "fallback_items": 0, "fallback_rate": 0},
                    "top_items": top_items,
                }
            },
        }
        summary["quality_score"] = calculate_quality_score(summary)

        result = validate(summary, "2026-08-09")

        self.assertTrue(result["valid"], result["failures"])
        self.assertGreaterEqual(summary["quality_score"]["score"], 70)

    def test_generated_numeric_score_blocks_below_threshold(self):
        fixture_path = Path(__file__).parent / "fixtures" / "resilience_scenario.json"
        scenario = json.loads(fixture_path.read_text(encoding="utf-8"))
        summary = scenario["low_quality_report"]
        summary["quality_score"] = calculate_quality_score(summary)

        result = validate(summary, "2026-08-09")

        self.assertFalse(result["valid"])
        self.assertLess(summary["quality_score"]["score"], 70)
        self.assertTrue(any("quality score" in failure for failure in result["failures"]))

    def test_excessive_item_analysis_fallback_is_rejected(self):
        summary = {
            "date": "2026-08-06",
            "executive_summary": "x" * 500,
            "top_topics": [{"name": "A topic"}],
            "total_items_collected": 10,
            "total_items_analyzed": 10,
            "phase_status": [
                {"name": "Phase 3: Topic Detection", "status": "success"},
                {"name": "Phase 4: Executive Summary", "status": "success"},
            ],
            "categories": {
                "news": {
                    "count": 10,
                    "category_summary": "x" * 400,
                    "analysis_quality": {
                        "total_items": 10,
                        "llm_analyzed_items": 6,
                        "fallback_items": 4,
                        "fallback_rate": 0.4,
                    },
                }
            },
        }

        result = validate(summary, "2026-08-06")

        self.assertFalse(result["valid"])
        self.assertTrue(
            any("news analysis fallback rate" in failure for failure in result["failures"])
        )

    def test_critical_phase_fallback_is_rejected(self):
        summary = {
            "date": "2026-08-06",
            "executive_summary": "x" * 500,
            "top_topics": [{"name": "A topic"}],
            "total_items_collected": 10,
            "total_items_analyzed": 10,
            "phase_status": [
                {
                    "name": "Phase 3: Topic Detection",
                    "status": "partial",
                    "details": "used deterministic fallback topics",
                },
                {
                    "name": "Phase 4: Executive Summary",
                    "status": "success",
                },
            ],
        }

        result = validate(summary, "2026-08-06")

        self.assertFalse(result["valid"])
        self.assertTrue(
            any("Topic Detection" in failure for failure in result["failures"])
        )

    def test_valid_checkpointed_synthesis_is_accepted(self):
        summary = {
            "date": "2026-08-06",
            "executive_summary": "x" * 500,
            "top_topics": [{"name": "A topic"}],
            "total_items_collected": 10,
            "total_items_analyzed": 10,
            "phase_status": [
                {
                    "name": "Phase 3: Topic Detection",
                    "status": "skipped",
                    "details": "loaded from checkpoint (4 topics)",
                },
                {
                    "name": "Phase 4: Executive Summary",
                    "status": "skipped",
                    "details": "loaded from checkpoint",
                },
            ],
        }

        result = validate(summary, "2026-08-06")

        self.assertTrue(result["valid"], result["failures"])

    def test_failed_category_is_rejected_even_when_analyzed_count_is_zero(self):
        summary = {
            "date": "2026-08-06",
            "executive_summary": "x" * 500,
            "top_topics": [{"name": "A topic"}],
            "total_items_collected": 10,
            "total_items_analyzed": 10,
            "phase_status": [
                {"name": "Phase 3: Topic Detection", "status": "success"},
                {"name": "Phase 4: Executive Summary", "status": "success"},
            ],
            "categories": {
                "news": {
                    "count": 0,
                    "category_summary": "Analysis failed: provider timeout",
                }
            },
        }

        result = validate(summary, "2026-08-06")

        self.assertFalse(result["valid"])
        self.assertIn(
            "news category_summary is a generic fallback",
            result["failures"],
        )


class CategorySummaryRoutingTests(unittest.TestCase):
    def test_github_trending_uses_quality_summary_route_and_budget(self):
        class FakeClient:
            def __init__(self):
                self.kwargs = None

            async def call_with_thinking(self, **kwargs):
                self.kwargs = kwargs
                return SimpleNamespace(
                    content="A" * 500,
                    stop_reason="stop",
                )

        async def run():
            client = FakeClient()
            analyzer = object.__new__(GitHubTrendingAnalyzer)
            analyzer.async_client = client
            analyzer.prompt_accessor = None
            item = SimpleNamespace(
                item=SimpleNamespace(
                    title="[GitHub Trending] example/repository",
                    content="An agent framework for enterprise workflows",
                ),
                summary="Trending repository",
            )

            result = await analyzer._generate_executive_summary([item])

            self.assertEqual(len(result), 500)
            self.assertEqual(
                client.kwargs["caller"],
                "analysis.github_trending_summary",
            )
            self.assertEqual(client.kwargs["max_tokens"], 4096)

        asyncio.run(run())


class LLMTelemetryTests(unittest.TestCase):
    def test_openrouter_glm_promotional_cost_is_provider_specific(self):
        tracker = CostTracker("test-model")
        tracker.record_call(
            caller="orchestrator.summary",
            usage={"input_tokens": 1_000_000, "output_tokens": 1_000_000},
            model="z-ai/glm-5.2",
            provider_id="openrouter-glm-complex",
        )
        tracker.record_call(
            caller="link_enricher.executive summary",
            usage={"input_tokens": 1_000_000, "output_tokens": 1_000_000},
            model="z-ai/glm-5.2",
            provider_id="nvidia-glm-quality",
        )

        self.assertAlmostEqual(tracker.get_total_cost().total_cost, 0.29)

    def test_category_telemetry_reports_provider_failover_and_tokens(self):
        tracker = CostTracker("test-model")
        tracker.start()
        tracker.record_failure(
            caller="news_analyzer.batch_1",
            model="primary-model",
            provider_id="primary",
            duration_seconds=2.5,
            error_type="ConnectError",
            retry_reason="ConnectError",
        )
        tracker.record_call(
            caller="news_analyzer.batch_1",
            usage={"input_tokens": 100, "output_tokens": 20, "thinking_tokens": 30},
            duration_seconds=1.5,
            model="fallback-model",
            provider_id="fallback",
            attempt=2,
            fallback_from="primary",
            retry_reason="ConnectError",
        )
        tracker.record_call(
            caller="analysis.research_summary",
            usage={"input_tokens": 50, "output_tokens": 10},
            duration_seconds=1.0,
            model="quality-model",
            provider_id="quality",
        )

        telemetry = tracker.get_llm_telemetry()
        news = telemetry["by_category"]["news"]
        research = telemetry["by_category"]["research"]

        self.assertEqual(news["status"], "recovered")
        self.assertEqual(news["provider_attempts"], 2)
        self.assertEqual(news["failed_attempts"], 1)
        self.assertEqual(news["fallback_successes"], 1)
        self.assertEqual(news["error_rate"], 0.5)
        self.assertEqual(news["input_tokens"], 100)
        self.assertEqual(news["thinking_tokens"], 30)
        self.assertEqual(
            {provider["model"] for provider in news["providers"]},
            {"primary-model", "fallback-model"},
        )
        self.assertEqual(research["status"], "success")
        self.assertEqual(telemetry["overall"]["provider_attempts"], 3)
        self.assertEqual(telemetry["overall"]["error_rate"], 0.3333)

    def test_unused_category_is_explicit(self):
        telemetry = CostTracker("test-model").get_llm_telemetry()

        self.assertEqual(telemetry["by_category"]["social"]["status"], "unused")
        self.assertEqual(telemetry["by_category"]["social"]["provider_attempts"], 0)

    def test_summary_json_publishes_llm_telemetry(self):
        telemetry = CostTracker("test-model").get_llm_telemetry()
        with tempfile.TemporaryDirectory() as output_dir:
            generator = JSONGenerator(output_dir)
            date_dir = os.path.join(output_dir, "data", "2026-08-09")
            os.makedirs(date_dir)
            generator._generate_summary_json(date_dir, {
                "date": "2026-08-09",
                "llm_telemetry": telemetry,
                "category_reports": {
                    "news": {"all_items": [], "category_summary": ""},
                },
            })
            with open(os.path.join(date_dir, "summary.json"), encoding="utf-8") as summary_file:
                summary = json.load(summary_file)

        self.assertEqual(summary["llm_telemetry"], telemetry)
        self.assertEqual(
            summary["categories"]["news"]["llm_telemetry"],
            telemetry["by_category"]["news"],
        )
        self.assertIn("quality_score", summary)


class SemanticCacheTests(unittest.TestCase):
    def test_republished_article_with_new_url_reuses_analysis(self):
        def item(item_id, url, published, title="OpenAI launches a new reasoning model"):
            return CollectedItem(
                id=item_id,
                title=title,
                content="The same syndicated article body with normalized whitespace.",
                url=url,
                author="Wire service",
                published=published,
                source="feed",
                source_type="rss",
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            interests = root / "interests.txt"
            interests.write_text("reasoning models", encoding="utf-8")
            cache = AnalysisCache(root / "cache.jsonl", interests)
            original = item("one", "https://feed-a.example/story?utm=1", "2026-08-08T01:00:00")
            republished = item(
                "two",
                "https://feed-b.example/repost",
                "2026-08-09T02:00:00",
                title="New reasoning model launched by OpenAI",
            )
            analysis = {"summary": "Reusable analysis", "importance_score": 80}

            cache.set(original, analysis)

            self.assertEqual(cache.get(republished), analysis)
            self.assertEqual(cache.make_cache_key(original), cache.make_cache_key(republished))


class DeterministicLinkEnrichmentTests(unittest.TestCase):
    def test_clear_entity_match_skips_llm_call(self):
        class NeverCallClient:
            def __init__(self):
                self.calls = 0

            async def call_with_thinking(self, **kwargs):
                self.calls += 1
                raise AssertionError("deterministic match should not call the LLM")

        async def run():
            client = NeverCallClient()
            enricher = LinkEnricher(client, "2026-08-09")
            text = "OpenAI launches a new reasoning model with stronger tool use for enterprise agents."
            items = [{
                "id": "story-1",
                "category": "news",
                "title": "OpenAI launches a new reasoning model",
                "summary": "",
            }]

            enriched = await enricher._enrich_text(text, items, "executive summary")

            self.assertIn("#item-story-1", enriched)
            self.assertEqual(client.calls, 0)

        asyncio.run(run())


class GathererObservabilityTests(unittest.TestCase):
    def test_source_health_contains_latency_dedup_freshness_and_last_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator = object.__new__(MainOrchestrator)
            orchestrator.web_dir = temp_dir
            orchestrator.target_date = "2026-08-09"
            orchestrator.gatherers = {"news": SimpleNamespace(coverage_date="2026-08-08")}
            item = CollectedItem(
                id="one",
                title="Fresh story",
                content="body",
                url="https://example.com/one",
                author="",
                published="2026-08-08T12:00:00",
                source="example",
                source_type="rss",
            )
            status = {"news": {"status": "success", "count": 1, "error": None}}

            orchestrator._decorate_collection_status(
                status, {"news": [item]}, {"news": 2}, {"news": 1250}
            )

            news = status["news"]
            self.assertEqual(news["duration_ms"], 1250)
            self.assertEqual(news["duplicates_removed"], 1)
            self.assertEqual(news["duplicate_rate"], 0.5)
            self.assertEqual(news["freshness_rate"], 1.0)
            self.assertIsNotNone(news["last_success_at"])
            self.assertTrue((Path(temp_dir) / "data" / "source-health.json").exists())


class EndToEndResilienceFixtureTests(unittest.TestCase):
    def test_timeout_429_truncation_empty_feed_and_publish_rejection(self):
        fixture_path = Path(__file__).parent / "fixtures" / "resilience_scenario.json"
        scenario = json.loads(fixture_path.read_text(encoding="utf-8"))

        class RateLimited(Exception):
            status_code = 429

        class Route:
            def __init__(self, event, fallback_route_id=None):
                self.provider_id = event["provider"]
                self.model = f"fixture-{self.provider_id}"
                self.fallback_route_id = fallback_route_id
                self.route_profiles = {"STANDARD"}
                self.caller_patterns = []
                self.route_priority = 0
                self.max_concurrent_requests = 1
                self.event = event

            async def call_with_thinking(self, **kwargs):
                error = self.event.get("error")
                if error == "timeout":
                    raise httpx.ReadTimeout("fixture NVIDIA timeout")
                if error == "http_429":
                    raise RateLimited("fixture Gemini 429 RPM")
                return LLMResponse(
                    content=self.event["result"],
                    thinking=None,
                    usage={"input_tokens": 1, "output_tokens": 1},
                    model=self.model,
                )

        async def route_call():
            events = scenario["provider_events"]
            router = AsyncLLMRouter([
                Route(events[0], "gemini"),
                Route(events[1], "glm"),
                Route(events[2]),
            ])
            return await router.call_with_thinking(
                messages=[{"role": "user", "content": "fixture"}],
                profile=ThinkingLevel.STANDARD,
                caller="fixture.resilience",
            )

        response = asyncio.run(route_call())
        recovered = WebScraperGatherer._recover_complete_json_objects(
            scenario["truncated_feed_payload"]
        )
        report = scenario["low_quality_report"]
        report["quality_score"] = calculate_quality_score(report)

        self.assertEqual(response.content, "fallback recovered")
        self.assertEqual(len(recovered), 1)
        self.assertEqual(scenario["empty_feed_items"], [])
        self.assertFalse(validate(report, "2026-08-09")["valid"])


if __name__ == "__main__":
    unittest.main()
