import unittest

from agents.analyzers.news_analyzer import NewsAnalyzer
from agents.base import CollectedItem
from agents.llm_client import LLMResponse


def make_item(title: str, content: str = "", item_id: str = "test-item") -> CollectedItem:
    return CollectedItem(
        id=item_id,
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


class FakeAsyncClient:
    def __init__(self, content: str):
        self.content = content

    async def call_with_thinking(self, **_kwargs) -> LLMResponse:
        return LLMResponse(
            content=self.content,
            thinking=None,
            usage={},
            model="mock-model",
        )


class NewsLlmFilterFailOpenTest(unittest.IsolatedAsyncioTestCase):
    def _analyzer(self, response_content: str) -> NewsAnalyzer:
        analyzer = NewsAnalyzer.__new__(NewsAnalyzer)
        analyzer.async_client = FakeAsyncClient(response_content)
        analyzer.prompt_accessor = None
        return analyzer

    def _items(self):
        return [
            make_item("AI story one", item_id="article-00000001-full"),
            make_item("AI story two", item_id="article-00000002-full"),
        ]

    async def test_malformed_json_keeps_keyword_filtered_items(self):
        items = self._items()
        filtered = await self._analyzer("not valid JSON")._filter_with_llm(items)
        self.assertEqual(filtered, items)

    async def test_missing_or_invalid_schema_keeps_keyword_filtered_items(self):
        items = self._items()
        for response in (
            '{}',
            '{"ai_article_ids": "article-00000001"}',
            '{"ai_article_ids": [null]}',
        ):
            with self.subTest(response=response):
                filtered = await self._analyzer(response)._filter_with_llm(items)
                self.assertEqual(filtered, items)

    async def test_empty_or_unknown_selection_cannot_wipe_news(self):
        items = self._items()
        for response in (
            '{"ai_article_ids": []}',
            '{"ai_article_ids": ["unknown-article-id"]}',
        ):
            with self.subTest(response=response):
                filtered = await self._analyzer(response)._filter_with_llm(items)
                self.assertEqual(filtered, items)

    async def test_valid_selection_still_filters_items(self):
        items = self._items()
        response = '{"ai_article_ids": ["article-00000001"]}'
        filtered = await self._analyzer(response)._filter_with_llm(items)
        self.assertEqual(filtered, [items[0]])


if __name__ == "__main__":
    unittest.main()
