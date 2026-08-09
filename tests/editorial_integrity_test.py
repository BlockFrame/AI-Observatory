"""Regression tests for publication integrity and evidence grounding."""

import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import yaml

from agents.analysis_schema import sanitize_ranking_result
from agents.base import AnalyzedItem, CategoryReport, CollectedItem
from agents.editorial_guard import contains_forbidden_brand, sanitize_editorial_text
from agents.gatherers.link_follower import LinkFollower
from agents.orchestrator import MainOrchestrator
from agents.quality_score import calculate_quality_score
from scripts.validate_report import validate


ROOT = Path(__file__).resolve().parent.parent


class SocialRankingSchemaTests(unittest.TestCase):
    def test_top_25_survives_schema_sanitization(self):
        ids = [f"social-{index}" for index in range(25)]
        result = sanitize_ranking_result({
            "top_25": ids,
            "category_summary": "Strategic social briefing",
        })

        self.assertEqual(result["top_25"], ids)
        self.assertEqual(result["category_summary"], "Strategic social briefing")


class EditorialBrandGuardTests(unittest.TestCase):
    def test_internal_style_brand_is_removed_from_generated_heading(self):
        leaked = "#### QuantumBlack Executive Briefing: AI by McKinsey"
        cleaned = sanitize_editorial_text(leaked)

        self.assertFalse(contains_forbidden_brand(cleaned))
        self.assertIn("Executive Briefing", cleaned)

    def test_prompt_sources_do_not_name_internal_style_brands(self):
        prompt_sources = [
            ROOT / "config" / "prompts.yaml",
            ROOT / "agents" / "base.py",
            ROOT / "agents" / "orchestrator.py",
            *sorted((ROOT / "agents" / "analyzers").glob("*_analyzer.py")),
        ]
        leaked = [
            str(path.relative_to(ROOT))
            for path in prompt_sources
            if contains_forbidden_brand(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(leaked, [])


class PublicationIntegrityTests(unittest.TestCase):
    @staticmethod
    def _summary():
        top_items = [
            {
                "id": f"news-{index}",
                "title": f"AI story {index}",
                "url": f"https://example.com/news-{index}",
                "source": "example",
            }
            for index in range(5)
        ]
        social_items = [
            {
                "id": f"social-{index}",
                "title": f"AI discussion {index}",
                "url": f"https://x.com/example/{index}",
                "source": "X",
            }
            for index in range(5)
        ]
        summary = {
            "date": "2026-08-09",
            "executive_summary": "Evidence-grounded strategic briefing. " * 20,
            "executive_evidence_items": ["news-0", "social-0"],
            "top_topics": [{
                "name": "Current AI signal",
                "description": "A current development supported across news and social channels.",
                "category_breakdown": {"news": 1, "social": 1},
                "representative_items": ["news-0", "social-0"],
            }],
            "total_items_collected": 10,
            "total_items_analyzed": 10,
            "analysis_funnel": {
                "news": {"collected": 5, "analyzed": 5, "wipeout": False},
                "social": {"collected": 5, "analyzed": 5, "wipeout": False},
            },
            "phase_status": [
                {"name": "Phase 3: Topic Detection", "status": "success"},
                {"name": "Phase 4: Executive Summary", "status": "success"},
            ],
            "generation_quality": {"fallback_used": False},
            "collection_status": {"overall": "success", "sources": []},
            "categories": {
                "news": {
                    "count": 5,
                    "current_item_ids": [item["id"] for item in top_items],
                    "category_summary": "Current news analysis. " * 25,
                    "analysis_quality": {"total_items": 5, "fallback_items": 0, "fallback_rate": 0},
                    "top_items": top_items,
                },
                "social": {
                    "count": 5,
                    "current_item_ids": [item["id"] for item in social_items],
                    "category_summary": "Current social analysis. " * 25,
                    "analysis_quality": {"total_items": 5, "fallback_items": 0, "fallback_rate": 0},
                    "top_items": social_items,
                },
            },
        }
        summary["quality_score"] = calculate_quality_score(summary)
        return summary

    def test_category_wipeout_blocks_publication_and_caps_score(self):
        summary = self._summary()
        summary["analysis_funnel"]["news"] = {
            "collected": 22,
            "analyzed": 0,
            "wipeout": True,
        }
        summary["categories"]["news"]["count"] = 0
        summary["categories"]["news"]["current_item_ids"] = []
        summary["quality_score"] = calculate_quality_score(summary)

        result = validate(summary, "2026-08-09")

        self.assertFalse(result["valid"])
        self.assertTrue(any("category wipeout" in failure for failure in result["failures"]))
        self.assertLessEqual(summary["quality_score"]["score"], 20)

    def test_topic_must_have_two_current_categories(self):
        summary = self._summary()
        summary["top_topics"][0]["category_breakdown"] = {"news": 2}
        summary["top_topics"][0]["representative_items"] = ["news-0", "news-1"]

        result = validate(summary, "2026-08-09")

        self.assertFalse(result["valid"])
        self.assertTrue(any("not cross-category" in failure for failure in result["failures"]))

    def test_non_current_executive_evidence_blocks_publication(self):
        summary = self._summary()
        summary["executive_evidence_items"] = ["news-0", "yesterday-item"]

        result = validate(summary, "2026-08-09")

        self.assertFalse(result["valid"])
        self.assertTrue(any("non-current evidence" in failure for failure in result["failures"]))


class OrchestrationEvidenceContractTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _report(category: str, item_id: str) -> CategoryReport:
        item = CollectedItem(
            id=item_id,
            title=f"Current {category} development",
            content="Current evidence",
            url=f"https://example.com/{item_id}",
            author="Example",
            published="2026-08-08T12:00:00",
            source="Example",
            source_type=category,
        )
        analyzed = AnalyzedItem(
            item=item,
            summary=f"Current evidence from {category}.",
            importance_score=90,
            reasoning="Current and relevant",
            themes=["Current AI"],
        )
        return CategoryReport(
            category=category,
            top_items=[analyzed],
            all_items=[analyzed],
            category_summary=(f"Current {category} strategic analysis. " * 20),
            themes=[],
            cross_signals=[],
            total_collected=1,
        )

    @staticmethod
    def _orchestrator(response_content: str) -> MainOrchestrator:
        client = SimpleNamespace()
        client.call_with_thinking = AsyncMock(return_value=SimpleNamespace(
            content=response_content,
            thinking=None,
            stop_reason="stop",
        ))
        orchestrator = object.__new__(MainOrchestrator)
        orchestrator.async_client = client
        orchestrator.prompt_accessor = None
        orchestrator.grounding_context = None
        orchestrator.target_date = "2026-08-09"
        orchestrator.web_dir = "/nonexistent"
        return orchestrator

    async def test_topic_contract_keeps_only_current_cross_category_evidence(self):
        response = json.dumps({
            "topics": [{
                "name": "Current cross signal",
                "description": "A current signal across news and social.",
                "categories": {"news": 99, "social": 99},
                "representative_items": ["news-current", "social-current"],
                "importance": 90,
            }]
        })
        orchestrator = self._orchestrator(response)
        reports = {
            "news": self._report("news", "news-current"),
            "social": self._report("social", "social-current"),
        }

        topics, _ = await orchestrator._detect_cross_category_topics(reports)

        self.assertEqual(len(topics), 1)
        self.assertEqual(topics[0].representative_items, ["news-current", "social-current"])
        self.assertEqual(topics[0].category_breakdown, {"news": 1, "social": 1})

    async def test_executive_contract_returns_verified_current_evidence(self):
        briefing = "#### Executive Briefing\n\n" + ("Current strategic evidence. " * 25)
        response = json.dumps({
            "executive_summary": briefing,
            "evidence_item_ids": ["news-current", "social-current"],
        })
        orchestrator = self._orchestrator(response)
        reports = {
            "news": self._report("news", "news-current"),
            "social": self._report("social", "social-current"),
        }

        content, _, evidence = await orchestrator._generate_executive_summary(reports, [])

        self.assertEqual(content, briefing.strip())
        self.assertEqual(evidence, ["news-current", "social-current"])


class TcoExpansionTests(unittest.IsolatedAsyncioTestCase):
    async def test_tco_redirect_is_expanded_before_relevance_filter(self):
        follower = LinkFollower(llm_client=None)
        follower.should_follow_link = AsyncMock(return_value=False)
        post = CollectedItem(
            id="post-1",
            title="Social post",
            content="Read https://t.co/abc123",
            url="https://x.com/example/status/1",
            author="example",
            published="2026-08-08T12:00:00",
            source="X",
            source_type="twitter",
        )

        with patch.object(
            follower,
            "_expand_tco_url",
            return_value="https://example.com/current-ai-story",
        ):
            await follower.process_social_posts(
                [post],
                start_time=SimpleNamespace(),
                end_time=SimpleNamespace(),
            )

        follower.should_follow_link.assert_awaited_once()
        self.assertEqual(
            follower.should_follow_link.await_args.args[0],
            "https://example.com/current-ai-story",
        )


class GeminiQuotaRoutingTests(unittest.TestCase):
    def test_paid_glm_is_primary_and_gemini_36_is_complex_task_fallback(self):
        providers = yaml.safe_load((ROOT / "config" / "providers.yaml").read_text())
        paid_glm = next(
            route for route in providers["llm"]["routes"]
            if route["id"] == "openrouter-glm-complex"
        )
        gemini = next(
            route for route in providers["llm"]["routes"]
            if route["model"] == "gemini-3.6-flash"
        )
        self.assertEqual(
            set(paid_glm["caller_patterns"]),
            {
                "*_analyzer.reduce_rank",
                "analysis.*_summary",
                "orchestrator.topics",
                "orchestrator.summary",
            },
        )
        self.assertEqual(paid_glm["fallback_route_id"], "gemini-quality-fallback")
        self.assertEqual(set(gemini["caller_patterns"]), set(paid_glm["caller_patterns"]))


if __name__ == "__main__":
    unittest.main()
