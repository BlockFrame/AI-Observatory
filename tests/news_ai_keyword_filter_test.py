import unittest

from agents.analyzers.news_analyzer import NewsAnalyzer
from agents.base import CollectedItem


def make_item(title: str, content: str = "") -> CollectedItem:
    return CollectedItem(
        id="test-item",
        title=title,
        content=content,
        url="https://example.com/article",
        author="Test",
        published="2026-07-22T00:00:00",
        source="Test",
        source_type="rss",
    )


class NewsAiKeywordFilterTest(unittest.TestCase):
    def setUp(self):
        self.analyzer = NewsAnalyzer.__new__(NewsAnalyzer)

    def test_rejects_incidental_ai_substrings(self):
        self.assertFalse(
            self.analyzer._has_ai_keywords(
                make_item("Range Rover GT preview", "Ars does not accept paid editorial content.")
            )
        )
        self.assertFalse(
            self.analyzer._has_ai_keywords(
                make_item("Sony releases a Spider-Man trailer")
            )
        )
        self.assertFalse(
            self.analyzer._has_ai_keywords(
                make_item("Fashion model launches a new summer collection")
            )
        )

    def test_accepts_standalone_ai_terms_and_model_names(self):
        self.assertTrue(
            self.analyzer._has_ai_keywords(
                make_item("OpenAI releases a new GPT-5 reasoning model")
            )
        )
        self.assertTrue(
            self.analyzer._has_ai_keywords(
                make_item("New AI infrastructure improves model inference")
            )
        )


if __name__ == "__main__":
    unittest.main()
