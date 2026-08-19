"""Dependency-free OpenRouter model and price policy for the paid route."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional


OPENROUTER_COMPLEX_MODEL = "minimax/minimax-m3"
DEFAULT_MAX_INPUT_PER_MTOK = Decimal("0.24")
DEFAULT_MAX_OUTPUT_PER_MTOK = Decimal("0.96")


class OpenRouterPriceGuardError(ValueError):
    """Raised when the configured promotional price is unavailable."""


@dataclass(frozen=True)
class EligibleEndpoint:
    name: str
    provider_name: str
    input_per_mtok: Decimal
    output_per_mtok: Decimal
    discount: Decimal


def _env_decimal(name: str, default: Decimal) -> Decimal:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise OpenRouterPriceGuardError(f"{name} must be a decimal number, got {raw!r}") from exc
    if value < 0:
        raise OpenRouterPriceGuardError(f"{name} must be non-negative")
    return value


def max_input_per_mtok() -> Decimal:
    return _env_decimal(
        "OPENROUTER_COMPLEX_MAX_INPUT_PER_MTOK",
        DEFAULT_MAX_INPUT_PER_MTOK,
    )


def max_output_per_mtok() -> Decimal:
    return _env_decimal(
        "OPENROUTER_COMPLEX_MAX_OUTPUT_PER_MTOK",
        DEFAULT_MAX_OUTPUT_PER_MTOK,
    )


def provider_preferences(model: str) -> Dict[str, Any]:
    """Return a runtime price cap matching the preflight policy."""
    if model != OPENROUTER_COMPLEX_MODEL:
        return {}
    return {
        "sort": "price",
        "max_price": {
            "prompt": float(max_input_per_mtok()),
            "completion": float(max_output_per_mtok()),
        },
    }


def _price_per_mtok(pricing: Dict[str, Any], field: str) -> Decimal:
    try:
        # The endpoint catalog expresses prices in dollars per token.
        return Decimal(str(pricing[field])) * Decimal(1_000_000)
    except (KeyError, InvalidOperation, TypeError) as exc:
        raise OpenRouterPriceGuardError(f"invalid endpoint {field} price") from exc


def eligible_endpoints(
    payload: Dict[str, Any],
    *,
    model: str = OPENROUTER_COMPLEX_MODEL,
    max_input: Optional[Decimal] = None,
    max_output: Optional[Decimal] = None,
) -> List[EligibleEndpoint]:
    """Validate a catalog response and return active endpoints below the cap."""
    data = payload.get("data")
    if not isinstance(data, dict):
        raise OpenRouterPriceGuardError("OpenRouter response has no data object")
    if data.get("id") != model:
        raise OpenRouterPriceGuardError(
            f"OpenRouter returned model {data.get('id')!r}, expected {model!r}"
        )

    input_cap = max_input if max_input is not None else max_input_per_mtok()
    output_cap = max_output if max_output is not None else max_output_per_mtok()
    endpoints = data.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        raise OpenRouterPriceGuardError(f"OpenRouter returned no endpoints for {model}")

    eligible: List[EligibleEndpoint] = []
    observed: List[str] = []
    for endpoint in endpoints:
        if not isinstance(endpoint, dict) or endpoint.get("status") != 0:
            continue
        pricing = endpoint.get("pricing")
        if not isinstance(pricing, dict):
            continue
        try:
            input_price = _price_per_mtok(pricing, "prompt")
            output_price = _price_per_mtok(pricing, "completion")
        except OpenRouterPriceGuardError:
            continue
        name = str(endpoint.get("name") or endpoint.get("provider_name") or "unknown")
        observed.append(f"{name}: ${input_price}/M input, ${output_price}/M output")
        if input_price <= input_cap and output_price <= output_cap:
            try:
                discount = Decimal(str(pricing.get("discount", 0)))
            except InvalidOperation:
                discount = Decimal(0)
            eligible.append(
                EligibleEndpoint(
                    name=name,
                    provider_name=str(endpoint.get("provider_name") or "unknown"),
                    input_per_mtok=input_price,
                    output_per_mtok=output_price,
                    discount=discount,
                )
            )

    if not eligible:
        observed_text = "; ".join(observed[:6]) or "no active priced endpoints"
        raise OpenRouterPriceGuardError(
            f"promotion unavailable for {model}: required <= ${input_cap}/M input and "
            f"<= ${output_cap}/M output; observed {observed_text}"
        )

    return sorted(
        eligible,
        key=lambda endpoint: (endpoint.input_per_mtok, endpoint.output_per_mtok),
    )
