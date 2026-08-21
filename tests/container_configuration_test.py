import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ContainerConfigurationTest(unittest.TestCase):
    def test_image_build_uses_repository_layout_and_current_runtime_files(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("COPY llms.txt ai-index.json ./", dockerfile)
        self.assertIn("RAIDAR_ALLOW_EMPTY_REPORT_DATA=true npm run build", dockerfile)
        self.assertIn("COPY config/ ./config-defaults/", dockerfile)
        self.assertIn("COPY pipeline_support/ ./pipeline_support/", dockerfile)
        self.assertIn("COPY report_schema.py .", dockerfile)
        self.assertIn("COPY --from=frontend-builder /src/web ./web/", dockerfile)

        svelte_config = (ROOT / "frontend/svelte.config.js").read_text(encoding="utf-8")
        self.assertIn("allowEmptyReportData ? 'ignore' : 'fail'", svelte_config)

    def test_compose_exposes_current_routes_without_legacy_model_default(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        for variable in (
            "GEMINI_API_KEY",
            "OPENROUTER_API_KEY",
            "NVIDIA_API_KEY",
            "GETXAPI_KEY",
            "OPENROUTER_COMPLEX_MAX_INPUT_PER_MTOK",
            "OPENROUTER_COMPLEX_MAX_OUTPUT_PER_MTOK",
        ):
            self.assertIn(variable, compose)
        self.assertNotIn("ANTHROPIC_MODEL", compose)

    def test_container_is_no_spend_by_default_and_cron_preserves_routes(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        entrypoint = (ROOT / "entrypoint.sh").read_text(encoding="utf-8")

        self.assertIn("ENABLE_CRON: ${ENABLE_CRON:-false}", compose)
        self.assertIn("cp -an /app/config-defaults/. /app/config/", entrypoint)
        self.assertIn("/app/.pipeline-env", entrypoint)
        self.assertIn("shlex.quote", entrypoint)
        self.assertIn("check_openrouter_pricing.py", entrypoint)

    def test_daily_workflow_has_no_ineffective_model_override(self):
        workflow = (ROOT / ".github/workflows/daily-pipeline.yml").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("anthropic_model", workflow)
        self.assertNotIn("ANTHROPIC_MODEL", workflow)


if __name__ == "__main__":
    unittest.main()
