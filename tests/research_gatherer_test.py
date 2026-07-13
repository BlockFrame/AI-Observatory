"""Focused tests for date-aligned research paper collection."""

import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from agents.gatherers.research_gatherer import ResearchGatherer


class ResearchGathererTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _gatherer_for_coverage(self, coverage_date):
        report_date = (
            datetime.strptime(coverage_date, "%Y-%m-%d") + timedelta(days=1)
        ).strftime("%Y-%m-%d")
        return ResearchGatherer(
            config_dir=self.temp_dir.name,
            data_dir=self.temp_dir.name,
            target_date=report_date,
        )

    @patch("agents.gatherers.research_gatherer.requests.get")
    def test_huggingface_fetch_requests_exact_coverage_date(self, mock_get):
        response = Mock()
        response.json.return_value = []
        response.raise_for_status.return_value = None
        mock_get.return_value = response
        gatherer = self._gatherer_for_coverage("2026-07-10")

        self.assertEqual(gatherer._fetch_huggingface_daily_papers(), [])

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"], {"date": "2026-07-10"})

    def test_huggingface_record_uses_daily_selection_date(self):
        gatherer = self._gatherer_for_coverage("2026-07-10")
        item = gatherer._huggingface_entry_to_item(
            {
                "paper": {
                    "id": "2607.03118",
                    "title": "Vidu S1",
                    "summary": "A real-time video generation model.",
                    "ai_summary": "Real-time interactive video generation.",
                    "ai_keywords": ["video generation", "real-time"],
                    "authors": [{"name": "Jintao Zhang"}, {"name": "Kai Jiang"}],
                    "publishedAt": "2026-07-03T00:00:00.000Z",
                    "submittedOnDailyAt": "2026-07-10T00:00:00.000Z",
                    "upvotes": 128,
                }
            }
        )

        self.assertIsNotNone(item)
        self.assertEqual(item.published, "2026-07-10T00:00:00+00:00")
        self.assertEqual(item.source_type, "research_paper")
        self.assertEqual(item.metadata["arxiv_id"], "2607.03118")
        self.assertEqual(item.author, "Jintao Zhang, Kai Jiang")

    def test_alphaxiv_record_filters_and_extracts_structured_summary(self):
        gatherer = self._gatherer_for_coverage("2026-07-10")
        matching = gatherer._alphaxiv_record_to_item(
            {
                "universal_paper_id": "2607.09657",
                "title": "Scalable Visual Pretraining",
                "abstract": "Fallback abstract.",
                "paper_summary": {"summary": "Structured AlphaXiv summary."},
                "publication_date": "2026-07-10T17:57:03.000Z",
                "authors": ["Yiming Zhang", "Zhonghan Zhao"],
                "topics": ["cs.AI", "vision-language-models"],
                "metrics": {
                    "public_total_votes": 17,
                    "visits_count": {"all": 126},
                },
            }
        )
        outside_window = {
            "universal_paper_id": "2607.00001",
            "title": "Outside window",
            "publication_date": "2026-07-09T17:57:03.000Z",
        }

        self.assertIsNotNone(matching)
        self.assertEqual(matching.content, "Structured AlphaXiv summary.")
        self.assertEqual(matching.metadata["alphaxiv"]["public_total_votes"], 17)
        self.assertIsNone(gatherer._alphaxiv_record_to_item(outside_window))

    @patch("agents.gatherers.research_gatherer.requests.get")
    def test_alphaxiv_fetch_filters_response_to_coverage_date(self, mock_get):
        response = Mock()
        response.json.return_value = {
            "papers": [
                {
                    "universal_paper_id": "2607.09657",
                    "title": "Matching paper",
                    "abstract": "Inside the coverage date.",
                    "publication_date": "2026-07-10T17:57:03.000Z",
                },
                {
                    "universal_paper_id": "2607.00001",
                    "title": "Outside paper",
                    "abstract": "Outside the coverage date.",
                    "publication_date": "2026-07-09T17:57:03.000Z",
                },
            ]
        }
        response.raise_for_status.return_value = None
        mock_get.return_value = response
        gatherer = self._gatherer_for_coverage("2026-07-10")

        papers = gatherer._fetch_alphaxiv_trending()

        self.assertEqual([paper.title for paper in papers], ["Matching paper"])
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["sort"], "Hot")
        self.assertIn("cs.AI", kwargs["params"]["topics"])

    def test_cross_source_duplicates_merge_provenance(self):
        gatherer = self._gatherer_for_coverage("2026-07-10")
        huggingface = gatherer._huggingface_entry_to_item(
            {
                "paper": {
                    "id": "2607.03118",
                    "title": "Shared paper",
                    "summary": "Hugging Face summary.",
                    "submittedOnDailyAt": "2026-07-10T00:00:00.000Z",
                }
            }
        )
        alphaxiv = gatherer._alphaxiv_record_to_item(
            {
                "universal_paper_id": "2607.03118v2",
                "title": "Shared paper",
                "abstract": "Longer AlphaXiv abstract for the same shared paper.",
                "publication_date": "2026-07-10T12:00:00.000Z",
                "topics": ["cs.AI"],
            }
        )

        merged = gatherer._merge_trending_papers([huggingface], [alphaxiv])

        self.assertEqual(len(merged), 1)
        self.assertEqual(
            merged[0].metadata["discovery_sources"],
            ["huggingface", "alphaxiv"],
        )
        self.assertEqual(merged[0].source, "Hugging Face Papers + AlphaXiv")
        self.assertIn("alphaxiv", merged[0].metadata["source_urls"])

    def test_alphaxiv_is_skipped_beyond_historical_window(self):
        old_coverage = (datetime.now() - timedelta(days=91)).strftime("%Y-%m-%d")
        gatherer = self._gatherer_for_coverage(old_coverage)

        self.assertIsNone(gatherer._alphaxiv_interval_for_coverage())


if __name__ == "__main__":
    unittest.main()
