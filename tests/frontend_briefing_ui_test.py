import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendBriefingUiRegressionTest(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_category_page_expands_compact_ssr_data_to_complete_public_json(self):
        server = self.read("frontend/src/lib/server/briefingData.ts")
        component = self.read(
            "frontend/src/lib/components/briefings/BriefingCategory.svelte"
        )

        self.assertIn(".slice(0, 12).map(compactItem)", server)
        self.assertIn("loadCategoryData(summary.date, category)", component)
        self.assertIn("items={displayItems}", component)
        self.assertIn("All {categoryData.total_items} current items", component)

    def test_category_route_labels_are_reactive(self):
        component = self.read(
            "frontend/src/lib/components/briefings/BriefingCategory.svelte"
        )
        self.assertIn("$: config = CATEGORY_CONFIG[category]", component)
        self.assertIn("$: title = `${config.title} Briefing`;", component)
        self.assertIn("$: pageTitle = `${title} — ${reportDate}`", component)
        self.assertIn("datetime={summary.date}", component)

    def test_search_waits_for_index_and_preserves_card_anchor_id(self):
        search_bar = self.read("frontend/src/lib/components/search/SearchBar.svelte")
        search_worker = self.read("frontend/src/lib/services/searchWorker.ts")

        self.assertIn("isReady = await initializeSearch()", search_bar)
        self.assertIn("if (isReady && query.length >= 2) await performSearch()", search_bar)
        self.assertIn("itemId: doc.id", search_worker)
        self.assertIn("id: r.itemId as string", search_worker)


if __name__ == "__main__":
    unittest.main()
