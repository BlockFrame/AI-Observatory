"""Focused regression checks for scraper and summary-pipeline resilience."""

import asyncio
import unittest
from types import SimpleNamespace

from agents.analyzers.github_trending_analyzer import GitHubTrendingAnalyzer
from agents.gatherers.social_gatherer import SocialGatherer
from agents.gatherers.webscraper_gatherer import WebScraperGatherer
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


class PublicationQualityGateTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
