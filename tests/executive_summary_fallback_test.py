import unittest
from types import SimpleNamespace

from agents.orchestrator import (
    MIN_EXECUTIVE_SUMMARY_CHARS,
    MainOrchestrator,
    TopTopic,
)


class ExecutiveSummaryFallbackTest(unittest.TestCase):
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
