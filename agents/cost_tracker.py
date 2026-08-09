"""
Cost Tracker for LLM API Usage

Tracks token usage and calculates provider-aware cost estimates.
Provides detailed statistics for pipeline runs.

Claude pricing source: https://platform.claude.com/docs/en/about-claude/pricing
Gemini AI Studio quota-tier calls are reported as a zero-dollar estimate.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ModelPricing(Enum):
    """Pricing per million tokens (MTok) for different models."""

    # Claude Opus pricing (USD per million tokens) — identical between 4.6 and 4.8
    OPUS_4_6_INPUT = 5.00
    OPUS_4_6_OUTPUT = 25.00
    OPUS_4_6_CACHE_WRITE_5MIN = 6.25
    OPUS_4_6_CACHE_WRITE_1HR = 10.00
    OPUS_4_6_CACHE_HIT = 0.50

    # Claude Sonnet 4.5 pricing
    SONNET_4_5_INPUT = 3.00
    SONNET_4_5_OUTPUT = 15.00

    # Claude Haiku 4.5 pricing
    HAIKU_4_5_INPUT = 1.00
    HAIKU_4_5_OUTPUT = 5.00

    # OpenRouter promotional GLM 5.2 pricing observed through /api/v1/models
    # on 2026-08-09. Keep this route-specific so NVIDIA-hosted GLM remains $0.
    OPENROUTER_GLM_5_2_INPUT = 0.07
    OPENROUTER_GLM_5_2_OUTPUT = 0.22
    OPENROUTER_GLM_5_2_CACHE_HIT = 0.013


@dataclass
class APICallRecord:
    """Record of a single API call."""
    timestamp: str
    caller: str  # Which component made the call (e.g., "news_analyzer.filter")
    thinking_level: Optional[str]
    input_tokens: int
    output_tokens: int
    thinking_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    model: str = "claude-4.8-opus-aws"
    provider_id: Optional[str] = None
    analysis_profile: Optional[str] = None
    adaptive_effort: Optional[str] = None
    duration_seconds: float = 0.0
    attempt: int = 1
    same_provider_retry: int = 0
    fallback_from: Optional[str] = None
    retry_reason: Optional[str] = None

    @property
    def total_input_tokens(self) -> int:
        """Total input tokens including cache operations."""
        return self.input_tokens + self.cache_creation_tokens + self.cache_read_tokens

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output)."""
        return self.total_input_tokens + self.output_tokens + self.thinking_tokens


@dataclass
class CostBreakdown:
    """Detailed cost breakdown."""
    input_cost: float = 0.0
    output_cost: float = 0.0
    cache_write_cost: float = 0.0
    cache_hit_cost: float = 0.0

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.output_cost + self.cache_write_cost + self.cache_hit_cost


@dataclass
class APIFailureRecord:
    """Prompt-free record of one failed provider attempt."""
    timestamp: str
    caller: str
    model: str
    provider_id: str
    duration_seconds: float
    error_type: str
    retry_reason: Optional[str] = None
    attempt: int = 1
    same_provider_retry: int = 0
    fallback_from: Optional[str] = None


class CostTracker:
    """
    Tracks API usage and calculates costs for pipeline runs.

    Usage:
        tracker = CostTracker()
        tracker.record_call("news_analyzer.filter", usage_dict, "QUICK")
        tracker.record_call("news_analyzer.analyze", usage_dict, "DEEP")
        print(tracker.get_summary())
    """

    def __init__(self, model: str = "claude-4.8-opus-aws"):
        self.model = model
        self.calls: List[APICallRecord] = []
        self.failures: List[APIFailureRecord] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        # Non-LLM/third-party API usage (e.g. ScrapeCreators, GetXAPI), keyed by
        # provider name. Each value is a flat dict of metrics (calls, credits_consumed,
        # balance, balance_usd, est_cost_usd, items, note).
        self.external_apis: Dict[str, Dict] = {}

        # Determine pricing based on model
        if "opus" in model.lower():
            self.input_price = ModelPricing.OPUS_4_6_INPUT.value
            self.output_price = ModelPricing.OPUS_4_6_OUTPUT.value
            self.cache_write_price = ModelPricing.OPUS_4_6_CACHE_WRITE_5MIN.value
            self.cache_hit_price = ModelPricing.OPUS_4_6_CACHE_HIT.value
        elif "sonnet" in model.lower():
            self.input_price = ModelPricing.SONNET_4_5_INPUT.value
            self.output_price = ModelPricing.SONNET_4_5_OUTPUT.value
            self.cache_write_price = self.input_price * 1.25
            self.cache_hit_price = self.input_price * 0.1
        elif "haiku" in model.lower():
            self.input_price = ModelPricing.HAIKU_4_5_INPUT.value
            self.output_price = ModelPricing.HAIKU_4_5_OUTPUT.value
            self.cache_write_price = self.input_price * 1.25
            self.cache_hit_price = self.input_price * 0.1
        else:
            # Default to Opus pricing
            self.input_price = ModelPricing.OPUS_4_6_INPUT.value
            self.output_price = ModelPricing.OPUS_4_6_OUTPUT.value
            self.cache_write_price = ModelPricing.OPUS_4_6_CACHE_WRITE_5MIN.value
            self.cache_hit_price = ModelPricing.OPUS_4_6_CACHE_HIT.value

    def start(self):
        """Mark the start of a pipeline run."""
        self.start_time = datetime.now()
        self.calls = []
        self.failures = []
        self.external_apis = {}
        logger.info("Cost tracking started")

    def record_external_api(self, name: str, **metrics):
        """
        Record (or merge) usage for a non-LLM third-party API so it shows up in the
        run summary. Pass any of: calls, items, credits_consumed, balance, balance_usd,
        est_cost_usd, note. Repeated calls for the same name merge their keys.
        """
        existing = self.external_apis.get(name, {})
        existing.update({k: v for k, v in metrics.items() if v is not None})
        self.external_apis[name] = existing
        logger.debug(f"Recorded external API usage: {name} -> {existing}")

    def stop(self):
        """Mark the end of a pipeline run."""
        self.end_time = datetime.now()
        logger.info(f"Cost tracking stopped. Total calls: {len(self.calls)}")

    def record_call(
        self,
        caller: str,
        usage: Dict[str, int],
        thinking_level: Optional[str] = None,
        duration_seconds: float = 0.0,
        model: Optional[str] = None,
        provider_id: Optional[str] = None,
        analysis_profile: Optional[str] = None,
        adaptive_effort: Optional[str] = None,
        attempt: int = 1,
        same_provider_retry: int = 0,
        fallback_from: Optional[str] = None,
        retry_reason: Optional[str] = None,
    ):
        """
        Record an API call.

        Args:
            caller: Identifier for the component making the call
            usage: Usage dict from API response with input_tokens, output_tokens, etc.
            thinking_level: ThinkingLevel used (QUICK, STANDARD, DEEP, ULTRATHINK)
            duration_seconds: How long the call took
            model: Model used (if different from default)
        """
        record = APICallRecord(
            timestamp=datetime.now().isoformat(),
            caller=caller,
            thinking_level=thinking_level,
            input_tokens=usage.get('input_tokens', 0),
            output_tokens=usage.get('output_tokens', 0),
            thinking_tokens=usage.get('thinking_tokens', 0),
            cache_creation_tokens=usage.get('cache_creation_input_tokens', 0),
            cache_read_tokens=usage.get('cache_read_input_tokens', 0),
            model=model or self.model,
            provider_id=provider_id,
            analysis_profile=analysis_profile,
            adaptive_effort=adaptive_effort,
            duration_seconds=duration_seconds,
            attempt=attempt,
            same_provider_retry=same_provider_retry,
            fallback_from=fallback_from,
            retry_reason=retry_reason,
        )
        self.calls.append(record)

        logger.debug(
            f"Recorded call: {caller} - "
            f"in={record.input_tokens}, out={record.output_tokens}, "
            f"cache_write={record.cache_creation_tokens}, cache_read={record.cache_read_tokens}"
        )

    def record_failure(
        self,
        *,
        caller: str,
        model: str,
        provider_id: str,
        duration_seconds: float,
        error_type: str,
        retry_reason: Optional[str],
        attempt: int = 1,
        same_provider_retry: int = 0,
        fallback_from: Optional[str] = None,
    ) -> None:
        """Record a failed provider attempt without prompt or raw error text."""
        self.failures.append(APIFailureRecord(
            timestamp=datetime.now().isoformat(),
            caller=caller,
            model=model,
            provider_id=provider_id,
            duration_seconds=duration_seconds,
            error_type=error_type,
            retry_reason=retry_reason,
            attempt=attempt,
            same_provider_retry=same_provider_retry,
            fallback_from=fallback_from,
        ))

    @staticmethod
    def _caller_scope(caller: str) -> str:
        """Map stable caller IDs to public telemetry scopes."""
        normalized = (caller or "unknown").lower()
        for category in ("news", "research", "social", "github_trending"):
            if (
                normalized.startswith(f"{category}_analyzer")
                or normalized.startswith(f"analysis.{category}_summary")
                or normalized.startswith(f"continuity.matcher.{category}")
                or normalized.startswith(f"link_enricher.{category} summary")
            ):
                return category
        if normalized.startswith("orchestrator."):
            return "orchestration"
        if normalized.startswith("link_enricher."):
            return "cross_category_enrichment"
        if normalized.startswith("ecosystem_context."):
            return "ecosystem"
        if normalized.startswith("freshness."):
            return "freshness"
        return "other"

    def get_llm_telemetry(self) -> Dict[str, Any]:
        """Aggregate prompt-free reliability and usage telemetry by scope."""
        scopes: Dict[str, Dict[str, Any]] = {}

        def ensure_scope(name: str) -> Dict[str, Any]:
            return scopes.setdefault(name, {
                "successful_calls": 0,
                "failed_attempts": 0,
                "provider_attempts": 0,
                "fallback_successes": 0,
                "same_provider_retry_successes": 0,
                "duration_seconds": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "thinking_tokens": 0,
                "retry_reasons": {},
                "providers": {},
            })

        def ensure_provider(scope: Dict[str, Any], provider_id: str, model: str) -> Dict[str, Any]:
            providers = scope["providers"]
            provider = providers.setdefault(provider_id, {
                "provider_id": provider_id,
                "model": model,
                "successful_calls": 0,
                "failed_attempts": 0,
                "duration_seconds": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "thinking_tokens": 0,
            })
            return provider

        for call in self.calls:
            scope = ensure_scope(self._caller_scope(call.caller))
            provider_id = call.provider_id or call.model
            provider = ensure_provider(scope, provider_id, call.model)
            scope["successful_calls"] += 1
            scope["provider_attempts"] += 1
            scope["fallback_successes"] += int(bool(call.fallback_from) or call.attempt > 1)
            scope["same_provider_retry_successes"] += int(call.same_provider_retry > 0)
            scope["duration_seconds"] += call.duration_seconds
            scope["input_tokens"] += call.input_tokens
            scope["output_tokens"] += call.output_tokens
            scope["thinking_tokens"] += call.thinking_tokens
            provider["successful_calls"] += 1
            provider["duration_seconds"] += call.duration_seconds
            provider["input_tokens"] += call.input_tokens
            provider["output_tokens"] += call.output_tokens
            provider["thinking_tokens"] += call.thinking_tokens

        for failure in self.failures:
            scope = ensure_scope(self._caller_scope(failure.caller))
            provider = ensure_provider(scope, failure.provider_id, failure.model)
            scope["failed_attempts"] += 1
            scope["provider_attempts"] += 1
            scope["duration_seconds"] += failure.duration_seconds
            reason = failure.retry_reason or failure.error_type
            scope["retry_reasons"][reason] = scope["retry_reasons"].get(reason, 0) + 1
            provider["failed_attempts"] += 1
            provider["duration_seconds"] += failure.duration_seconds

        for scope in scopes.values():
            if scope["failed_attempts"] and scope["successful_calls"]:
                scope["status"] = "recovered"
            elif scope["failed_attempts"]:
                scope["status"] = "failed"
            else:
                scope["status"] = "success"
            scope["error_rate"] = (
                round(scope["failed_attempts"] / scope["provider_attempts"], 4)
                if scope["provider_attempts"] else 0.0
            )
            scope["duration_seconds"] = round(scope["duration_seconds"], 3)
            scope["providers"] = list(scope["providers"].values())
            for provider in scope["providers"]:
                provider["duration_seconds"] = round(provider["duration_seconds"], 3)

        overall = ensure_scope("overall")
        for name, scope in list(scopes.items()):
            if name == "overall":
                continue
            for key in (
                "successful_calls", "failed_attempts", "provider_attempts",
                "fallback_successes", "same_provider_retry_successes",
                "input_tokens", "output_tokens", "thinking_tokens",
            ):
                overall[key] += scope[key]
            overall["duration_seconds"] += scope["duration_seconds"]
            for reason, count in scope["retry_reasons"].items():
                overall["retry_reasons"][reason] = overall["retry_reasons"].get(reason, 0) + count

        overall["status"] = (
            "recovered" if overall["failed_attempts"] and overall["successful_calls"]
            else "failed" if overall["failed_attempts"]
            else "success"
        )
        overall["error_rate"] = (
            round(overall["failed_attempts"] / overall["provider_attempts"], 4)
            if overall["provider_attempts"] else 0.0
        )
        overall["duration_seconds"] = round(overall["duration_seconds"], 3)
        overall.pop("providers", None)

        category_names = ("news", "research", "social", "github_trending")
        return {
            "overall": overall,
            "by_category": {
                name: scopes.get(name, {
                    "status": "unused",
                    "successful_calls": 0,
                    "failed_attempts": 0,
                    "provider_attempts": 0,
                    "fallback_successes": 0,
                    "same_provider_retry_successes": 0,
                    "duration_seconds": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "thinking_tokens": 0,
                    "error_rate": 0.0,
                    "retry_reasons": {},
                    "providers": [],
                })
                for name in category_names
            },
            "pipeline_scopes": {
                name: scope
                for name, scope in scopes.items()
                if name not in {*category_names, "overall"}
            },
        }

    def calculate_cost(self, record: APICallRecord) -> CostBreakdown:
        """Calculate cost for a single API call."""
        # Costs are per million tokens
        mtok = 1_000_000
        model = (record.model or "").lower()
        provider_id = (record.provider_id or "").lower()
        if provider_id == "openrouter-glm-complex" and model == "z-ai/glm-5.2":
            input_price = ModelPricing.OPENROUTER_GLM_5_2_INPUT.value
            output_price = ModelPricing.OPENROUTER_GLM_5_2_OUTPUT.value
            cache_write_price = 0.0
            cache_hit_price = ModelPricing.OPENROUTER_GLM_5_2_CACHE_HIT.value
        elif model.startswith("gemini-") or provider_id.startswith("nvidia-"):
            # This project targets the quota-limited Google AI Studio tier.
            # NVIDIA NIM routes are also currently used without token billing.
            # Keep usage visible without incorrectly applying Claude pricing.
            input_price = output_price = cache_write_price = cache_hit_price = 0.0
        else:
            input_price = self.input_price
            output_price = self.output_price
            cache_write_price = self.cache_write_price
            cache_hit_price = self.cache_hit_price

        return CostBreakdown(
            input_cost=(record.input_tokens / mtok) * input_price,
            output_cost=(record.output_tokens / mtok) * output_price,
            cache_write_cost=(record.cache_creation_tokens / mtok) * cache_write_price,
            cache_hit_cost=(record.cache_read_tokens / mtok) * cache_hit_price
        )

    def get_totals(self) -> Dict[str, int]:
        """Get total token counts."""
        totals = {
            'input_tokens': 0,
            'output_tokens': 0,
            'thinking_tokens': 0,
            'cache_creation_tokens': 0,
            'cache_read_tokens': 0,
            'total_tokens': 0
        }

        for call in self.calls:
            totals['input_tokens'] += call.input_tokens
            totals['output_tokens'] += call.output_tokens
            totals['thinking_tokens'] += call.thinking_tokens
            totals['cache_creation_tokens'] += call.cache_creation_tokens
            totals['cache_read_tokens'] += call.cache_read_tokens
            totals['total_tokens'] += call.total_tokens

        return totals

    def get_total_cost(self) -> CostBreakdown:
        """Get total cost breakdown."""
        total = CostBreakdown()

        for call in self.calls:
            cost = self.calculate_cost(call)
            total.input_cost += cost.input_cost
            total.output_cost += cost.output_cost
            total.cache_write_cost += cost.cache_write_cost
            total.cache_hit_cost += cost.cache_hit_cost

        return total

    def get_cost_by_caller(self) -> Dict[str, CostBreakdown]:
        """Get cost breakdown by caller/component."""
        by_caller: Dict[str, CostBreakdown] = {}

        for call in self.calls:
            if call.caller not in by_caller:
                by_caller[call.caller] = CostBreakdown()

            cost = self.calculate_cost(call)
            by_caller[call.caller].input_cost += cost.input_cost
            by_caller[call.caller].output_cost += cost.output_cost
            by_caller[call.caller].cache_write_cost += cost.cache_write_cost
            by_caller[call.caller].cache_hit_cost += cost.cache_hit_cost

        return by_caller

    def get_cost_by_provider(self) -> Dict[str, CostBreakdown]:
        """Get cost breakdown by routed provider id."""
        by_provider: Dict[str, CostBreakdown] = {}

        for call in self.calls:
            provider = call.provider_id or call.model
            if provider not in by_provider:
                by_provider[provider] = CostBreakdown()

            cost = self.calculate_cost(call)
            by_provider[provider].input_cost += cost.input_cost
            by_provider[provider].output_cost += cost.output_cost
            by_provider[provider].cache_write_cost += cost.cache_write_cost
            by_provider[provider].cache_hit_cost += cost.cache_hit_cost

        return by_provider

    def get_summary(self) -> str:
        """Get a formatted summary of usage and costs."""
        totals = self.get_totals()
        cost = self.get_total_cost()
        by_caller = self.get_cost_by_caller()
        by_provider = self.get_cost_by_provider()

        duration = ""
        if self.start_time and self.end_time:
            elapsed = (self.end_time - self.start_time).total_seconds()
            duration = f"\nTotal Duration: {elapsed:.1f}s"

        lines = [
            "=" * 60,
            "📊 PIPELINE COST REPORT",
            "=" * 60,
            f"Model: {self.model}",
            f"API Calls: {len(self.calls)}{duration}",
            "",
            "TOKEN USAGE:",
            f"  Input tokens:        {totals['input_tokens']:>12,}",
            f"  Output tokens:       {totals['output_tokens']:>12,}",
            f"  Thinking tokens:     {totals['thinking_tokens']:>12,}",
            f"  Cache write tokens:  {totals['cache_creation_tokens']:>12,}",
            f"  Cache read tokens:   {totals['cache_read_tokens']:>12,}",
            f"  ─────────────────────────────────",
            f"  Total tokens:        {totals['total_tokens']:>12,}",
            "",
            "COST BREAKDOWN:",
            f"  Input cost:          ${cost.input_cost:>10.4f}",
            f"  Output cost:         ${cost.output_cost:>10.4f}",
            f"  Cache write cost:    ${cost.cache_write_cost:>10.4f}",
            f"  Cache hit savings:   ${cost.cache_hit_cost:>10.4f}",
            f"  ─────────────────────────────────",
            f"  TOTAL COST:          ${cost.total_cost:>10.4f}",
            "",
            "COST BY COMPONENT:",
        ]

        # Sort by cost descending
        sorted_callers = sorted(
            by_caller.items(),
            key=lambda x: x[1].total_cost,
            reverse=True
        )

        for caller, caller_cost in sorted_callers:
            lines.append(f"  {caller:30s} ${caller_cost.total_cost:.4f}")

        if len(by_provider) > 1:
            lines.extend([
                "",
                "COST BY PROVIDER:",
            ])
            sorted_providers = sorted(
                by_provider.items(),
                key=lambda x: x[1].total_cost,
                reverse=True
            )
            for provider, provider_cost in sorted_providers:
                lines.append(f"  {provider:30s} ${provider_cost.total_cost:.4f}")

        if self.external_apis:
            lines.extend(["", "EXTERNAL API USAGE (non-LLM):"])
            for name, info in self.external_apis.items():
                parts: List[str] = []
                if info.get('calls') is not None:
                    parts.append(f"calls={info['calls']:,}")
                if info.get('items') is not None:
                    parts.append(f"items={info['items']:,}")
                if info.get('credits_consumed') is not None:
                    parts.append(f"credits used={info['credits_consumed']:,}")
                if info.get('balance') is not None:
                    bal = f"balance={info['balance']:,}"
                    if info.get('balance_usd') is not None:
                        bal += f" (${info['balance_usd']:.2f})"
                    parts.append(bal)
                if info.get('est_cost_usd') is not None:
                    parts.append(f"est cost=${info['est_cost_usd']:.4f}")
                if info.get('note'):
                    parts.append(str(info['note']))
                lines.append(f"  {name}: " + "  |  ".join(parts) if parts else f"  {name}")

        lines.extend([
            "",
            "PRICING ESTIMATE:",
            "  Gemini AI Studio quota calls: $0 estimate",
            f"  Claude fallback input:  ${self.input_price:.2f}/MTok",
            f"  Claude fallback output: ${self.output_price:.2f}/MTok",
            "=" * 60
        ])

        return "\n".join(lines)

    def get_json_report(self) -> Dict:
        """Get a JSON-serializable report."""
        totals = self.get_totals()
        cost = self.get_total_cost()
        by_caller = self.get_cost_by_caller()
        by_provider = self.get_cost_by_provider()

        return {
            "model": self.model,
            "api_calls": len(self.calls),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": (
                (self.end_time - self.start_time).total_seconds()
                if self.start_time and self.end_time else None
            ),
            "tokens": totals,
            "cost": {
                "input": round(cost.input_cost, 6),
                "output": round(cost.output_cost, 6),
                "cache_write": round(cost.cache_write_cost, 6),
                "cache_hit": round(cost.cache_hit_cost, 6),
                "total": round(cost.total_cost, 6)
            },
            "cost_by_component": {
                caller: round(c.total_cost, 6)
                for caller, c in by_caller.items()
            },
            "cost_by_provider": {
                provider: round(c.total_cost, 6)
                for provider, c in by_provider.items()
            },
            "external_apis": self.external_apis,
            "llm_telemetry": self.get_llm_telemetry(),
            "calls": [
                {
                    "timestamp": call.timestamp,
                    "caller": call.caller,
                    "thinking_level": call.thinking_level,
                    "input_tokens": call.input_tokens,
                    "output_tokens": call.output_tokens,
                    "thinking_tokens": call.thinking_tokens,
                    "cache_creation_tokens": call.cache_creation_tokens,
                    "cache_read_tokens": call.cache_read_tokens,
                    "model": call.model,
                    "provider_id": call.provider_id,
                    "analysis_profile": call.analysis_profile,
                    "adaptive_effort": call.adaptive_effort,
                    "duration_seconds": call.duration_seconds,
                    "attempt": call.attempt,
                    "same_provider_retry": call.same_provider_retry,
                    "fallback_from": call.fallback_from,
                    "retry_reason": call.retry_reason,
                }
                for call in self.calls
            ],
            "failures": [
                {
                    "timestamp": failure.timestamp,
                    "caller": failure.caller,
                    "model": failure.model,
                    "provider_id": failure.provider_id,
                    "duration_seconds": failure.duration_seconds,
                    "error_type": failure.error_type,
                    "retry_reason": failure.retry_reason,
                    "attempt": failure.attempt,
                    "same_provider_retry": failure.same_provider_retry,
                    "fallback_from": failure.fallback_from,
                }
                for failure in self.failures
            ],
        }

    def save_report(self, filepath: str):
        """Save the JSON report to a file."""
        with open(filepath, 'w') as f:
            json.dump(self.get_json_report(), f, indent=2)
        logger.info(f"Cost report saved to {filepath}")


# Global tracker instance for easy access
_global_tracker: Optional[CostTracker] = None


def get_tracker() -> CostTracker:
    """Get the global cost tracker instance."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = CostTracker()
    return _global_tracker


def reset_tracker(model: str = "claude-4.8-opus-aws") -> CostTracker:
    """Reset and return a new global tracker."""
    global _global_tracker
    _global_tracker = CostTracker(model)
    return _global_tracker
