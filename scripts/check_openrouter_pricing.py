#!/usr/bin/env python3
"""Fail closed before the pipeline when the paid model promotion is unavailable."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline_support.openrouter_pricing import (  # noqa: E402
    OPENROUTER_COMPLEX_MODEL,
    OpenRouterPriceGuardError,
    eligible_endpoints,
    max_input_per_mtok,
    max_output_per_mtok,
)


def main() -> int:
    model = OPENROUTER_COMPLEX_MODEL
    url = f"https://openrouter.ai/api/v1/models/{model}/endpoints"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Wiredframe-Radar-price-preflight/1.0",
    }
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with urlopen(Request(url, headers=headers), timeout=20) as response:
            payload = json.load(response)
        endpoints = eligible_endpoints(payload)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"ERROR: OpenRouter price preflight could not verify pricing: {exc}", file=sys.stderr)
        return 1
    except OpenRouterPriceGuardError as exc:
        print(f"ERROR: OpenRouter price preflight blocked the run: {exc}", file=sys.stderr)
        return 1

    selected = endpoints[0]
    print(
        f"OpenRouter price preflight passed for {model}: {selected.provider_name} "
        f"at ${selected.input_per_mtok}/M input and ${selected.output_per_mtok}/M output "
        f"(caps ${max_input_per_mtok()}/M and ${max_output_per_mtok()}/M)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
