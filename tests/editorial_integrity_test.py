"""Regression tests for publication integrity and evidence grounding."""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import yaml

from agents.analysis_schema import sanitize_ranking_result
from agents.analyzers.news_analyzer import NewsAnalyzer
from agents.base import AnalyzedItem, CategoryReport, CollectedItem
from agents.editorial_guard import (
    contains_forbidden_brand,
    contains_leaked_evidence_metadata,
    sanitize_editorial_text,
)
from agents.gatherers.link_follower import LinkFollower
from agents.orchestrator import MainOrchestrator
from agents.quality_score import calculate_quality_score
from scripts.validate_report import validate


ROOT = Path(__file__).resolve().parent.parent


class SourceInventoryTests(unittest.TestCase):
    def test_nvidia_sources_keep_ai_specific_channels_only(self):
        feeds = (ROOT / "config" / "rss_feeds.txt").read_text(encoding="utf-8")
        active_feeds = {
            line.split()[0]
            for line in feeds.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        accounts = {
            line.strip()
            for line in (ROOT / "config" / "twitter_accounts.txt")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

        self.assertIn(
            "https://blogs.nvidia.com/blog/tag/generative-ai/feed/",
            active_feeds,
        )
        self.assertNotIn("https://research.nvidia.com/rss.xml", active_feeds)
        self.assertIn("NVIDIAAI", accounts)
        self.assertNotIn("nvidia", accounts)

    def test_requested_research_sources_have_active_or_reference_routes(self):
        active = "\n".join(
            (ROOT / "config" / name).read_text(encoding="utf-8")
            for name in (
                "rss_feeds.txt",
                "web_scraper_sources.txt",
                "research_feeds.txt",
                "research_web_sources.txt",
            )
        )
        references = (ROOT / "config" / "research_reference_sources.txt").read_text(
            encoding="utf-8"
        )

        for expected in (
            "anthropic.com/research",
            "anthropic.com/economic-futures",
            "huggingface.co/blog/feed.xml",
            "kimi.com/blog",
            "engineering.fb.com/category/ai-research/feed",
            "wp.oecd.ai/feed",
            "arena.ai/blog/category/research",
            "epoch.ai/latest",
            "nist.gov/caisi",
            "edpb.europa.eu/rss.xml",
        ):
            self.assertIn(expected, active)
        for expected in (
            "ai.meta.com/research",
            "microsoft.com/en-us/research/group/aiei",
            "hai.stanford.edu/ai-index",
            "digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai",
            "governance.ai/research",
        ):
            self.assertIn(expected, references)

    def test_kimi_oecd_and_nist_are_news_not_research(self):
        news = "\n".join(
            (ROOT / "config" / name).read_text(encoding="utf-8")
            for name in ("rss_feeds.txt", "web_scraper_sources.txt")
        )
        research = "\n".join(
            (ROOT / "config" / name).read_text(encoding="utf-8")
            for name in ("research_feeds.txt", "research_web_sources.txt")
        )

        for source in ("kimi.com/blog", "wp.oecd.ai/feed", "nist.gov/caisi"):
            self.assertIn(source, news)
            self.assertNotIn(source, research)

    def test_new_ai_news_sources_are_configured(self):
        news = "\n".join(
            (ROOT / "config" / name).read_text(encoding="utf-8")
            for name in ("rss_feeds.txt", "web_scraper_sources.txt")
        )

        for source in (
            "deeplearning.ai/the-batch",
            "databricks.com/blog/feed.xml",
            "minimax.io/news",
            "docs.z.ai/release-notes/new-released",
        ):
            self.assertIn(source, news)


class ValidatorCliTests(unittest.TestCase):
    def test_validator_cli_imports_project_modules_without_pythonpath(self):
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "validate_report.py"),
                    "--help",
                ],
                cwd=temp_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validate a daily report", result.stdout)

    def test_workflow_uploads_candidate_diagnostics_before_cleanup(self):
        workflow = (ROOT / ".github" / "workflows" / "daily-pipeline.yml").read_text(
            encoding="utf-8"
        )

        upload_index = workflow.index("- name: Upload pipeline diagnostics")
        cleanup_index = workflow.index("- name: Discard invalid generated data")
        self.assertLess(upload_index, cleanup_index)
        self.assertIn("web/data/*/summary.json", workflow)
        self.assertIn("web/data/*/endpoint_status.json", workflow)

    def test_gathering_cache_hashes_all_source_configs(self):
        workflow = (ROOT / ".github" / "workflows" / "daily-pipeline.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("'config/web_scraper_sources.txt'", workflow)
        self.assertIn("'config/research_web_sources.txt'", workflow)
        self.assertNotIn("gathering-v2-", workflow)

    def test_workflow_checks_paid_price_before_setup_and_collection(self):
        workflow = (ROOT / ".github" / "workflows" / "daily-pipeline.yml").read_text(
            encoding="utf-8"
        )

        price_index = workflow.index("- name: Verify paid model promotional pricing")
        setup_index = workflow.index("- name: Set up Python")
        pipeline_index = workflow.index("- name: Run pipeline")
        self.assertLess(price_index, setup_index)
        self.assertLess(price_index, pipeline_index)
        self.assertIn("python3 scripts/check_openrouter_pricing.py", workflow)

    def test_workflow_pins_reruns_to_original_report_date(self):
        workflow = (ROOT / ".github" / "workflows" / "daily-pipeline.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("actions/runs/${GITHUB_RUN_ID}", workflow)
        self.assertIn(".created_at // empty", workflow)
        self.assertIn('--date "${{ steps.report_date.outputs.date }}"', workflow)
        self.assertIn("refusing an ambiguous collection", workflow)

    def test_workflow_reuses_gathering_without_reusing_failed_synthesis(self):
        workflow = (ROOT / ".github" / "workflows" / "daily-pipeline.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("Restore completed gathering checkpoint", workflow)
        self.assertIn("Inspect gathering checkpoint for reuse", workflow)
        self.assertIn("Save completed gathering checkpoint", workflow)
        self.assertIn("args+=(--resume-from 2)", workflow)
        self.assertIn("paid X collection will be skipped", workflow)
        self.assertIn("data/checkpoints/*/gathering.json", workflow)
        self.assertIn('twitter.get("status") != "success"', workflow)
        self.assertIn("steps.gathering_checkpoint.outputs.reusable == 'true'", workflow)
        self.assertNotIn("data/checkpoints/*/analysis.json", workflow)
        self.assertNotIn("data/checkpoints/*/topics.json", workflow)
        self.assertNotIn("data/checkpoints/*/summary.json", workflow)


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

    def test_machine_evidence_suffixes_are_removed_from_visible_copy(self):
        copy = (
            "- Supported story. [ca02b4f474cc, e57043c16a2e]\n"
            "- Supported repositories. ([098efe0dd09d], [1df29669a1e8])"
        )

        cleaned = sanitize_editorial_text(copy)

        self.assertEqual(cleaned, "- Supported story.\n- Supported repositories.")

    def test_inline_plain_evidence_ids_are_removed_without_joining_prose(self):
        copy = (
            "- OpenAI's Zero Data Retention and Private Safety Processing "
            "(cb22aa4a5626, 39e6521286de) turn confidentiality into a moat, "
            "while OpenRouter (1fcc0ac1faa8) raises switching costs."
        )

        cleaned = sanitize_editorial_text(copy)

        self.assertEqual(
            cleaned,
            "- OpenAI's Zero Data Retention and Private Safety Processing "
            "turn confidentiality into a moat, while OpenRouter raises switching costs.",
        )
        self.assertFalse(contains_leaked_evidence_metadata(cleaned))

    def test_evidence_cleanup_preserves_markdown_links_and_normal_brackets(self):
        copy = (
            "- [OpenAI](https://openai.com) shipped an update [enterprise].\n"
            "- [Research](/?date=2026-08-18&category=research#item-ca02b4f474cc) matters."
        )

        self.assertEqual(sanitize_editorial_text(copy), copy)


class CategorySummaryEvidenceRepairTests(unittest.TestCase):
    def test_regeneration_keeps_the_new_ordered_evidence_map(self):
        summary = """### Executive Signal
- **Enterprise signal** now requires a grounded leadership response across procurement, operations, and risk management for production AI systems.

### Priority Developments
- **Current release** changes enterprise deployment economics and creates a concrete decision point for technology leaders this quarter.
- **Operational controls** are becoming a material source of differentiation for organizations deploying AI into production workflows.
- **Governance expectations** increasingly require evidence-backed decisions linked to current, inspectable source material.

### Leadership Implications
- Validate the release through a controlled pilot before expanding contractual commitments or changing the target architecture.
- Assign accountable owners for technical, financial, and risk outcomes before moving the capability into production."""

        class FakeClient:
            async def call_with_thinking(self, **kwargs):
                return SimpleNamespace(
                    content=json.dumps({
                        "category_summary": summary,
                        "category_summary_evidence": [["news-1"]] * 6,
                    }),
                    stop_reason="stop",
                )

        item = AnalyzedItem(
            item=CollectedItem(
                id="news-1",
                title="Current AI release",
                content="Release details",
                url="https://example.com/release",
                author="Example",
                published="2026-08-18T12:00:00Z",
                source="Example",
                source_type="rss",
            ),
            summary="The release changes enterprise deployment economics.",
            importance_score=90,
            reasoning="Material current release",
            themes=["enterprise AI"],
        )

        async def run():
            analyzer = NewsAnalyzer.__new__(NewsAnalyzer)
            analyzer.async_client = FakeClient()
            return await analyzer._ensure_category_summary_with_evidence(
                summary,
                [],
                [item],
            )

        repaired_summary, evidence = asyncio.run(run())

        self.assertEqual(repaired_summary, summary)
        self.assertEqual(evidence, [["news-1"]] * 6)

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

    def test_visible_machine_evidence_ids_block_publication(self):
        summary = self._summary()
        summary["executive_summary"] += (
            " Private Safety Processing (cb22aa4a5626, 39e6521286de)."
        )

        result = validate(summary, "2026-08-09")

        self.assertFalse(result["valid"])
        self.assertIn(
            "executive_summary contains visible machine evidence IDs",
            result["failures"],
        )


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

    async def test_topic_contract_compacts_overlong_description(self):
        description = " ".join(["Evidence-grounded strategic topic."] * 40)
        response = json.dumps({
            "topics": [{
                "name": "Current cross signal",
                "description": description,
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

        self.assertLessEqual(len(topics[0].description.split()), 70)

    async def test_executive_contract_returns_verified_current_evidence(self):
        briefing = "#### Executive Briefing\n\n- " + ("Current strategic evidence. " * 25)
        response = json.dumps({
            "executive_summary": briefing,
            "evidence_by_bullet": [["news-current", "social-current"]],
            "evidence_item_ids": ["news-current", "social-current"],
        })
        orchestrator = self._orchestrator(response)
        reports = {
            "news": self._report("news", "news-current"),
            "social": self._report("social", "social-current"),
        }

        content, _, evidence, evidence_by_bullet = await orchestrator._generate_executive_summary(reports, [])

        self.assertEqual(content, briefing.strip())
        self.assertEqual(evidence, ["news-current", "social-current"])
        self.assertEqual(evidence_by_bullet, [["news-current", "social-current"]])

    async def test_executive_contract_removes_sentiment_section(self):
        briefing = (
            "#### Executive Briefing\n\n"
            + "- Current strategic evidence with a decision-relevant implication.\n" * 8
            + "\n#### Sentiment & Controversy\n"
            + "- This section must never be published."
        )
        response = json.dumps({
            "executive_summary": briefing,
            "evidence_item_ids": ["news-current", "social-current"],
        })
        orchestrator = self._orchestrator(response)
        reports = {
            "news": self._report("news", "news-current"),
            "social": self._report("social", "social-current"),
        }

        content, _, _, _ = await orchestrator._generate_executive_summary(reports, [])

        self.assertNotIn("Sentiment & Controversy", content)
        self.assertNotIn("must never be published", content)


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
    def test_paid_minimax_is_primary_and_gemini_36_is_complex_task_fallback(self):
        providers = yaml.safe_load((ROOT / "config" / "providers.yaml").read_text())
        paid_model = next(
            route for route in providers["llm"]["routes"]
            if route["id"] == "openrouter-minimax-complex"
        )
        gemini = next(
            route for route in providers["llm"]["routes"]
            if route["id"] == "gemini-quality-fallback"
        )
        self.assertEqual(
            set(paid_model["caller_patterns"]),
            {
                "news_analyzer.small_batch",
                "*_analyzer.reduce_rank",
                "analysis.*_summary",
                "orchestrator.topics",
                "orchestrator.summary",
            },
        )
        self.assertEqual(paid_model["fallback_route_id"], "gemini-quality-fallback")
        self.assertEqual(set(gemini["caller_patterns"]), set(paid_model["caller_patterns"]))


if __name__ == "__main__":
    unittest.main()
