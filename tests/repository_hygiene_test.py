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

    def test_obsolete_documentation_trees_are_absent(self):
        self.assertFalse((ROOT / ".planning").exists())
        self.assertFalse((ROOT / "docs" / "archived").exists())


if __name__ == "__main__":
    unittest.main()
