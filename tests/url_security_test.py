import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.config.migration import detect_env_vars, migrate_from_env
from agents.delivery.telegram import format_daily_report
from agents.url_utils import hostname_matches
from generators.markdown_export import generate_digest_markdown


class HostnameValidationTests(unittest.TestCase):
    def test_accepts_domain_and_subdomains(self):
        self.assertTrue(hostname_matches("https://github.com/org/repo", "github.com"))
        self.assertTrue(hostname_matches("https://www.lesswrong.com/posts/1", "lesswrong.com"))
        self.assertTrue(hostname_matches("https://integrate.api.nvidia.com/v1", "nvidia.com"))

    def test_rejects_suffix_confusion_and_non_http_urls(self):
        self.assertFalse(hostname_matches("https://github.com.attacker.example/repo", "github.com"))
        self.assertFalse(hostname_matches("https://attacker.example/github.com/repo", "github.com"))
        self.assertFalse(hostname_matches("javascript://github.com/%0Aalert(1)", "github.com"))
        self.assertFalse(hostname_matches("not a url", "github.com"))

    def test_exports_only_real_github_repositories(self):
        news = {
            "top_items": [
                {"item": {"title": "Safe", "url": "https://github.com/acme/safe"}},
                {"item": {"title": "Spoof", "url": "https://github.com.attacker.example/acme/spoof"}},
            ]
        }
        result = {"date": "2026-08-19", "category_reports": {"news": news}}
        with tempfile.TemporaryDirectory() as temp_dir:
            markdown = generate_digest_markdown(result, temp_dir)
        trending = markdown.split("## 📦 Trending Repos", 1)[1].split("## 🐦", 1)[0]
        self.assertIn("acme/safe", trending)
        self.assertNotIn("attacker.example", trending)

        telegram = format_daily_report(result)
        telegram_trending = telegram.split("📦 *Trending Repos*", 1)[1].split("🐦", 1)[0]
        self.assertIn("acme/safe", telegram_trending)
        self.assertNotIn("attacker.example", telegram_trending)


class MigrationSecretTests(unittest.TestCase):
    def test_migration_uses_references_without_persisting_secret_values(self):
        secret = "must-not-be-written"
        env = {
            "ANTHROPIC_API_KEY": secret,
            "ANTHROPIC_API_BASE": "https://proxy.example",
            "ANTHROPIC_MODEL": "test-model",
            "GEMINI_API_KEY": "another-secret",
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, env, clear=True):
            detected = detect_env_vars()
            self.assertIs(detected["llm"]["api_key"], True)
            self.assertTrue(migrate_from_env(temp_dir))
            content = (Path(temp_dir) / "providers.yaml").read_text(encoding="utf-8")

        self.assertNotIn(secret, content)
        self.assertNotIn("another-secret", content)
        self.assertIn("${ANTHROPIC_API_KEY}", content)
        self.assertIn("${ANTHROPIC_API_BASE}", content)


if __name__ == "__main__":
    unittest.main()
