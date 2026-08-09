"""Tests for strict historical/current executive-summary context partitioning."""

import json
import tempfile
import unittest
from pathlib import Path

from agents.summary_context import (
    PREVIOUS_COVERAGE_CLOSE,
    PREVIOUS_COVERAGE_OPEN,
    TODAYS_DATA_CLOSE,
    TODAYS_DATA_OPEN,
    build_executive_context,
    format_previous_coverage,
    load_previous_summaries,
)


class SummaryContextTest(unittest.TestCase):
    def test_context_keeps_history_outside_current_evidence(self):
        history = format_previous_coverage([
            ("2026-08-09", "Historical-only launch claim."),
        ])
        context = build_executive_context(
            "2026-08-10",
            history,
            [("Current topic", "Supported by today's sources")],
            [(
                "news",
                "Current category summary",
                [{
                    "id": "current-news-1",
                    "title": "Current headline",
                    "summary": "Current evidence",
                }],
            )],
        )

        history_start = context.index(PREVIOUS_COVERAGE_OPEN)
        history_end = context.index(PREVIOUS_COVERAGE_CLOSE)
        today_start = context.index(TODAYS_DATA_OPEN)
        today_end = context.index(TODAYS_DATA_CLOSE)

        self.assertLess(history_start, history_end)
        self.assertLess(history_end, today_start)
        self.assertLess(today_start, today_end)
        self.assertIn("Historical-only launch claim", context[history_start:history_end])
        self.assertNotIn("current-news-1", context[:today_start])
        self.assertIn("current-news-1", context[today_start:today_end])

    def test_context_without_history_starts_with_current_section(self):
        context = build_executive_context("2026-08-10", "", [], [])

        self.assertNotIn(PREVIOUS_COVERAGE_OPEN, context)
        self.assertIn(TODAYS_DATA_OPEN, context)
        self.assertIn("None detected.", context)
        self.assertTrue(context.endswith(TODAYS_DATA_CLOSE))

    def test_loader_skips_invalid_and_empty_summaries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            valid_dir = data_dir / "2026-08-09"
            valid_dir.mkdir(parents=True)
            (valid_dir / "summary.json").write_text(
                json.dumps({"executive_summary": "Valid prior summary"}),
                encoding="utf-8",
            )

            invalid_dir = data_dir / "2026-08-08"
            invalid_dir.mkdir()
            (invalid_dir / "summary.json").write_text("{invalid", encoding="utf-8")

            empty_dir = data_dir / "2026-08-07"
            empty_dir.mkdir()
            (empty_dir / "summary.json").write_text("{}", encoding="utf-8")

            summaries = load_previous_summaries(
                temp_dir,
                "2026-08-10",
                lookback_days=3,
            )

        self.assertEqual(summaries, [("2026-08-09", "Valid prior summary")])


if __name__ == "__main__":
    unittest.main()
