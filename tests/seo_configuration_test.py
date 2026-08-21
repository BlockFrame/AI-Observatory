"""Dependency-free guards for SEO/GEO deployment configuration."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SeoConfigurationTest(unittest.TestCase):
    def test_public_brand_has_distinct_visual_and_search_safe_names(self):
        site = (ROOT / "frontend/src/lib/site.ts").read_text()
        readme = (ROOT / "README.md").read_text()

        self.assertIn("name: 'rAIdar'", site)
        self.assertIn("visualName: 'R[AI]DAR'", site)
        self.assertIn("# R[AI]DAR", readme)
        self.assertIn("product by [Wiredframe]", readme)
        self.assertNotIn("rAIdar", readme)

    def test_readme_inventory_and_llm_routes_match_runtime_configuration(self):
        readme = (ROOT / "README.md").read_text()

        def active_lines(relative_path):
            return [
                line
                for line in (ROOT / relative_path).read_text().splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]

        self.assertIn(
            f"{len(active_lines('config/rss_feeds.txt'))} RSS/Atom feeds",
            readme,
        )
        self.assertIn(
            f"{len(active_lines('config/web_scraper_sources.txt'))} direct web pages",
            readme,
        )
        self.assertIn(
            f"{len(active_lines('config/research_feeds.txt'))} configured feed routes",
            readme,
        )
        self.assertIn(
            f"{len(active_lines('config/research_web_sources.txt'))} dated web hubs",
            readme,
        )
        self.assertIn(
            f"{len(active_lines('config/twitter_accounts.txt'))} configured X accounts",
            readme,
        )
        self.assertIn("OpenRouter MiniMax M3", readme)
        self.assertIn("Gemini 3.6 Flash → NVIDIA GLM 5.2", readme)
        self.assertNotIn("Nemotron", readme)
        self.assertNotIn("OpenRouter GLM", readme)

    def test_watchdog_validates_the_production_domain(self):
        workflow = (ROOT / ".github/workflows/pipeline-watchdog.yml").read_text()
        self.assertIn("https://radar.wiredframe.xyz", workflow)

    def test_vercel_build_publishes_machine_readable_indexes(self):
        package = json.loads((ROOT / "frontend/package.json").read_text())
        self.assertEqual(package["scripts"]["postbuild"], "node scripts/finalize-build.mjs")
        finalizer = (ROOT / "frontend/scripts/finalize-build.mjs").read_text()
        self.assertIn("'llms.txt'", finalizer)
        self.assertIn("'ai-index.json'", finalizer)
        self.assertIn("copyFileSync", finalizer)

    def test_briefing_routes_are_prerendered_from_current_data(self):
        overview = (ROOT / "frontend/src/routes/briefings/[date]/+page.server.ts").read_text()
        category = (
            ROOT / "frontend/src/routes/briefings/[date]/[category]/+page.server.ts"
        ).read_text()
        self.assertIn("export const prerender = true", overview)
        self.assertIn("export const entries = briefingEntries", overview)
        self.assertIn("export const prerender = true", category)
        self.assertIn("export const entries = categoryEntries", category)

    def test_sitemap_includes_briefings_and_last_modified_dates(self):
        sitemap = (ROOT / "frontend/src/routes/sitemap.xml/+server.ts").read_text()
        self.assertIn("briefingPages", sitemap)
        self.assertIn("<lastmod>${metadata.lastmod}</lastmod>", sitemap)
        self.assertIn("categoryEntries", sitemap)

    def test_segmented_sitemap_index_is_declared_in_robots(self):
        robots = (ROOT / "frontend/static/robots.txt").read_text()
        sitemap_index = (
            ROOT / "frontend/src/routes/sitemap-index.xml/+server.ts"
        ).read_text()

        self.assertIn(
            "Sitemap: https://radar.wiredframe.xyz/sitemap-index.xml", robots
        )
        self.assertIn("/sitemaps/core.xml", sitemap_index)
        self.assertIn("/sitemaps/models.xml", sitemap_index)
        self.assertIn("/sitemaps/briefings.xml", sitemap_index)

    def test_segmented_sitemaps_cover_current_public_routes(self):
        core = (ROOT / "frontend/src/routes/sitemaps/core.xml/+server.ts").read_text()
        models = (
            ROOT / "frontend/src/routes/sitemaps/models.xml/+server.ts"
        ).read_text()
        briefings = (
            ROOT / "frontend/src/routes/sitemaps/briefings.xml/+server.ts"
        ).read_text()

        for route in ("/about", "/influencers", "/models", "/tools", "/archive"):
            self.assertIn(route, core)
        self.assertIn("slugify(model.name)", models)
        self.assertIn("briefingEntries", briefings)
        self.assertIn("categoryEntries", briefings)
        self.assertIn("lastmod: date", briefings)

    def test_homepage_receives_latest_report_during_prerender(self):
        loader = (ROOT / "frontend/src/routes/+page.server.ts").read_text()
        page = (ROOT / "frontend/src/routes/+page.svelte").read_text()
        self.assertIn("loadBriefing(index.latestDate)", loader)
        self.assertIn("let summary: DaySummary | null = data.summary", page)
        self.assertIn("reportStructuredData", page)

    def test_historical_summaries_tolerate_missing_categories(self):
        helper = (ROOT / "frontend/src/lib/server/briefingData.ts").read_text()
        self.assertIn("function compactCategorySummary(category?: CategorySummary)", helper)
        self.assertIn("if (!category)", helper)


if __name__ == "__main__":
    unittest.main()
