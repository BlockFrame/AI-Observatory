import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_LINK = re.compile(r"\[[^]]*\]\(([^)]+)\)")


class RepositoryHygieneTest(unittest.TestCase):
    def test_root_contains_only_conventional_markdown_files(self):
        markdown_files = {path.name for path in ROOT.glob("*.md")}
        self.assertEqual(markdown_files, {"AGENTS.md", "CLAUDE.md", "README.md"})

    def test_public_documentation_uses_lowercase_kebab_case(self):
        for path in (ROOT / "docs").rglob("*.md"):
            if path.name == "README.md":
                continue
            self.assertEqual(path.name, path.name.lower(), path)
            self.assertNotIn("_", path.name, path)

    def test_active_markdown_has_no_broken_local_links(self):
        markdown_files = [
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "CLAUDE.md",
            ROOT / ".github" / "CONTRIBUTING.md",
            *(ROOT / "docs").rglob("*.md"),
        ]
        for document in markdown_files:
            for target in LOCAL_LINK.findall(document.read_text(encoding="utf-8")):
                target = target.split("#", 1)[0]
                if not target or "://" in target or target.startswith("mailto:"):
                    continue
                resolved = (document.parent / target).resolve()
                self.assertTrue(resolved.exists(), f"{document}: missing {target}")

    def test_documentation_index_links_every_canonical_guide(self):
        docs_dir = ROOT / "docs"
        index = (docs_dir / "README.md").read_text(encoding="utf-8")
        indexed_guides = {
            Path(target.split("#", 1)[0]).name
            for target in LOCAL_LINK.findall(index)
            if target.endswith(".md")
            and not target.startswith("..")
            and Path(target.split("#", 1)[0]).parent == Path(".")
        }
        canonical_guides = {
            path.name for path in docs_dir.glob("*.md") if path.name != "README.md"
        }
        self.assertEqual(indexed_guides, canonical_guides)

    def test_source_handbook_indexes_every_configured_url(self):
        handbook = (ROOT / "docs" / "sources.md").read_text(encoding="utf-8")
        registries = (
            "rss_feeds.txt",
            "web_scraper_sources.txt",
            "research_feeds.txt",
            "research_web_sources.txt",
            "research_reference_sources.txt",
        )
        for registry in registries:
            config_path = ROOT / "config" / registry
            for raw_line in config_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                url = line.split()[0]
                self.assertIn(url, handbook, f"{registry}: undocumented route {url}")

    def test_public_documentation_uses_the_visual_product_name(self):
        documents = [ROOT / "README.md", *(ROOT / "docs").glob("*.md")]
        for document in documents:
            text = document.read_text(encoding="utf-8")
            self.assertNotIn("rAIdar", text, document)
            self.assertNotIn("Wiredframe Radar", text, document)

    def test_legacy_observatory_brand_is_absent_from_public_surfaces(self):
        documents = [
            ROOT / "README.md",
            ROOT / "frontend" / "tailwind.config.js",
            *(ROOT / "docs").rglob("*.md"),
            *(ROOT / "frontend" / "src").rglob("*.svelte"),
            *(ROOT / "frontend" / "src").rglob("*.ts"),
        ]
        legacy_brand = re.compile(
            r"\b(?:AI|Synthetic Intelligence)[ _-]+Observatory\b",
            re.IGNORECASE,
        )
        for document in documents:
            self.assertIsNone(legacy_brand.search(document.read_text(encoding="utf-8")), document)

    def test_obsolete_documentation_trees_are_absent(self):
        self.assertFalse((ROOT / ".planning").exists())
        self.assertFalse((ROOT / "docs" / "archived").exists())


if __name__ == "__main__":
    unittest.main()
