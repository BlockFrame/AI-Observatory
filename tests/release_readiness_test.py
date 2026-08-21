import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODALS = (
    "FeedbackModal.svelte",
    "SuggestInfluencerModal.svelte",
    "SuggestModelModal.svelte",
    "SuggestToolModal.svelte",
)


class ReleaseReadinessTest(unittest.TestCase):
    def test_public_submissions_do_not_expose_token_backed_endpoints(self):
        api_dir = ROOT / "api"
        self.assertFalse(any(api_dir.glob("*.js")))

        helper = (ROOT / "frontend/src/lib/githubIssues.ts").read_text()
        self.assertIn("https://github.com/BlockFrame/wiredframe-radar/issues/new", helper)
        for modal_name in MODALS:
            modal = (ROOT / "frontend/src/lib/components" / modal_name).read_text()
            self.assertIn("openGitHubIssue", modal)
            self.assertIn("Nothing is sent until you confirm there", modal)
            self.assertNotIn("fetch('/api/", modal)

    def test_watchdog_is_self_contained_and_can_dispatch_with_repository_token(self):
        workflow = (ROOT / ".github/workflows/pipeline-watchdog.yml").read_text()

        self.assertIn("pip install --disable-pip-version-check -r requirements.txt", workflow)
        self.assertIn("secrets.WORKFLOW_DISPATCH_PAT || github.token", workflow)
        self.assertIn("actions: write", workflow)

    def test_release_versions_are_in_lockstep(self):
        root_package = json.loads((ROOT / "package.json").read_text())
        frontend_package = json.loads((ROOT / "frontend/package.json").read_text())

        self.assertEqual(root_package["version"], "1.0.2")
        self.assertEqual(frontend_package["version"], root_package["version"])

    def test_public_source_brand_is_consistent(self):
        public_files = [
            ROOT / "llms.txt",
            ROOT / "ai-index.json",
            ROOT / "mcp_server.py",
            ROOT / "frontend/src/lib/site.ts",
            *(ROOT / "frontend/src").rglob("*.svelte"),
        ]
        for path in public_files:
            self.assertNotIn("rAIdar", path.read_text(encoding="utf-8"), path)


if __name__ == "__main__":
    unittest.main()
