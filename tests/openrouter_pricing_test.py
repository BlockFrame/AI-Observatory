import os
import subprocess
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from pipeline_support.openrouter_pricing import (
    OPENROUTER_COMPLEX_MODEL,
    OpenRouterPriceGuardError,
    eligible_endpoints,
    provider_preferences,
)


def catalog(*endpoints):
    return {"data": {"id": OPENROUTER_COMPLEX_MODEL, "endpoints": list(endpoints)}}


def endpoint(prompt, completion, *, status=0, provider="GMICloud", discount=0.6):
    return {
        "name": f"{provider} | minimax-m3",
        "provider_name": provider,
        "status": status,
        "pricing": {
            "prompt": str(Decimal(prompt) / Decimal(1_000_000)),
            "completion": str(Decimal(completion) / Decimal(1_000_000)),
            "discount": discount,
        },
    }


class OpenRouterPricingTests(unittest.TestCase):
    def test_preflight_imports_without_third_party_dependencies(self):
        project_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                "-c",
                (
                    "import runpy; "
                    "runpy.run_path('scripts/check_openrouter_pricing.py', "
                    "run_name='pricing_preflight_import_test')"
                ),
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_current_promotional_endpoint_passes(self):
        result = eligible_endpoints(catalog(endpoint("0.24", "0.96")))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].provider_name, "GMICloud")

    def test_run_is_blocked_when_promotion_price_increases(self):
        with self.assertRaisesRegex(OpenRouterPriceGuardError, "promotion unavailable"):
            eligible_endpoints(catalog(endpoint("0.28", "1.10", discount=0)))

    def test_inactive_promotional_endpoint_does_not_pass(self):
        with self.assertRaises(OpenRouterPriceGuardError):
            eligible_endpoints(catalog(endpoint("0.24", "0.96", status=-2)))

    def test_runtime_request_uses_the_same_price_caps(self):
        with patch.dict(os.environ, {}, clear=False):
            self.assertEqual(
                provider_preferences(OPENROUTER_COMPLEX_MODEL),
                {
                    "sort": "price",
                    "max_price": {"prompt": 0.24, "completion": 0.96},
                },
            )

    def test_caps_can_be_tightened_from_environment(self):
        with patch.dict(
            os.environ,
            {
                "OPENROUTER_COMPLEX_MAX_INPUT_PER_MTOK": "0.20",
                "OPENROUTER_COMPLEX_MAX_OUTPUT_PER_MTOK": "0.80",
            },
        ):
            with self.assertRaises(OpenRouterPriceGuardError):
                eligible_endpoints(catalog(endpoint("0.24", "0.96")))


if __name__ == "__main__":
    unittest.main()
