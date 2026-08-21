import json
import tempfile
import unittest
from pathlib import Path

from mcp_report_store import available_dates, daily_summary, search_summaries


class McpReportStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_summary(self, date, payload):
        date_dir = self.data_dir / date
        date_dir.mkdir()
        (date_dir / "summary.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_lists_only_valid_date_directories_in_descending_order(self):
        (self.data_dir / "2026-08-20").mkdir()
        (self.data_dir / "2026-08-21").mkdir()
        (self.data_dir / "latest").mkdir()

        self.assertEqual(available_dates(self.data_dir), ["2026-08-21", "2026-08-20"])

    def test_reads_versioned_and_legacy_reports(self):
        self.write_summary("2026-08-20", {"date": "2026-08-20"})
        self.write_summary(
            "2026-08-21",
            {"schema_version": "1.0", "date": "2026-08-21"},
        )

        self.assertNotIn("schema_version", daily_summary(self.data_dir, "2026-08-20"))
        self.assertEqual(daily_summary(self.data_dir, "2026-08-21")["schema_version"], "1.0")

    def test_rejects_invalid_dates_and_empty_queries(self):
        with self.assertRaises(ValueError):
            daily_summary(self.data_dir, "../../secrets")
        with self.assertRaises(ValueError):
            search_summaries(self.data_dir, "  ")

    def test_search_skips_malformed_reports_and_matches_topics(self):
        malformed = self.data_dir / "2026-08-20"
        malformed.mkdir()
        (malformed / "summary.json").write_text("{broken", encoding="utf-8")
        self.write_summary(
            "2026-08-21",
            {
                "executive_summary": "Daily briefing",
                "top_topics": [{"name": "Agent orchestration", "description": "Evidence"}],
            },
        )

        self.assertEqual(
            search_summaries(self.data_dir, "orchestration"),
            [{"date": "2026-08-21", "match": "top_topic", "topic": "Agent orchestration"}],
        )


if __name__ == "__main__":
    unittest.main()
