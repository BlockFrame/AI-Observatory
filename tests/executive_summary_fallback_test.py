import unittest
from types import SimpleNamespace

from agents.orchestrator import (
    MIN_EXECUTIVE_SUMMARY_CHARS,
    MainOrchestrator,
    TopTopic,
)


class ExecutiveSummaryFallbackTest(unittest.TestCase):
    def test_builds_topics_from_analyzed_items_when_category_themes_are_empty(self):
        orchestrator = MainOrchestrator.__new__(MainOrchestrator)
        item = SimpleNamespace(
            item=SimpleNamespace(
                id="item-1",
                title="New reasoning model improves scientific workflows",
                metadata={},
            ),
            summary="The release improves tool use and scientific reasoning benchmarks.",
            importance_score=88,
        )
        reports = {
            "news": SimpleNamespace(
                themes=[],
                top_items=[item],
                all_items=[item],
                category_summary="",
            )
        }

        topics = orchestrator._build_fallback_topics(reports)

        self.assertEqual(len(topics), 1)
        self.assertEqual(topics[0].name, item.item.title)
        self.assertEqual(topics[0].representative_items, [item.item.id])
        self.assertEqual(topics[0].importance, item.importance_score)

    def test_builds_publishable_summary_without_failure_sentinel(self):
        orchestrator = MainOrchestrator.__new__(MainOrchestrator)
        topics = [
            TopTopic(
                name=f"Topic {index}",
                description=(
                    f"Development {index} connects product announcements, research, "
                    "and community response with concrete details from today's coverage."
                ),
                description_html="",
                category_breakdown={"news": 1},
                representative_items=[],
                importance=90 - index,
            )
            for index in range(6)
        ]
        item = SimpleNamespace(
            item=SimpleNamespace(
                title="A detailed AI industry development",
                metadata={},
            ),
            summary=(
                "The analyzed report explains what changed, identifies the organizations "
                "involved, and records the practical implications reported by the source."
            ),
        )
        reports = {
            "news": SimpleNamespace(
                top_items=[item],
                category_summary="",
            )
        }

        summary = orchestrator._build_executive_summary_fallback(reports, topics)

        self.assertGreaterEqual(len(summary), MIN_EXECUTIVE_SUMMARY_CHARS)
        self.assertNotIn("generation failed", summary.lower())
        self.assertIn("#### Top Story", summary)
        self.assertIn("#### Category Briefings", summary)


if __name__ == "__main__":
    unittest.main()
