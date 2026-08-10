"""Focused tests for Opus 4.8 adaptive thinking and async LLM routing."""

import asyncio
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import openai
from pydantic import ValidationError

from agents.config.schema import LLMProviderConfig, LLMRouteConfig
from agents.config.loader import load_config
from agents.llm_client import (
    AsyncAnthropicClient,
    AsyncLLMRouter,
    LLMResponse,
    OpenRouterResponseError,
    ProviderQuotaExhaustedError,
    ProviderRateLimiter,
    ThinkingLevel,
    _normalize_gemini_response,
    _openrouter_provider_preferences,
    _uses_adaptive_thinking,
)


class FakeUsage:
    input_tokens = 10
    output_tokens = 5
    cache_creation_input_tokens = 0
    cache_read_input_tokens = 0


class FakeTextBlock:
    type = "text"
    text = "ok"


class FakeAnthropicResponse:
    content = [FakeTextBlock()]
    usage = FakeUsage()
    model = "claude-4.8-opus-aws"
    stop_reason = "end_turn"


class FakeOpenRouterResponse:
    content = [FakeTextBlock()]
    usage = FakeUsage()
    model = "nvidia/nemotron-3-ultra-550b-a55b:free"
    stop_reason = "stop"


class FakeRouteClient:
    def __init__(
        self,
        provider_id,
        model=None,
        failures=None,
        route_profiles=None,
        caller_patterns=None,
        fallback_route_id=None,
        route_priority=0,
    ):
        self.provider_id = provider_id
        self.model = model or f"claude-4.8-opus-{provider_id}"
        self.max_concurrent_requests = 8
        self.failures = list(failures or [])
        self.calls = []
        self.route_profiles = set(route_profiles or [])
        self.caller_patterns = list(caller_patterns or [])
        self.fallback_route_id = fallback_route_id
        self.route_priority = route_priority

    async def call(self, **kwargs):
        self.calls.append(kwargs)
        if self.failures:
            raise self.failures.pop(0)
        return LLMResponse(
            content=self.provider_id,
            thinking=None,
            usage={"input_tokens": 1, "output_tokens": 1},
            model=self.model,
        )

    async def call_with_thinking(self, **kwargs):
        return await self.call(**kwargs)

    async def close(self):
        return None


class HTTP400(Exception):
    status_code = 400


class HTTP410(Exception):
    status_code = 410


class HTTP429RPD(Exception):
    status_code = 429


class HTTP400UnsupportedParameter(Exception):
    status_code = 400


class LLMRouteConfigTests(unittest.TestCase):
    def test_production_routes_keep_bulk_and_quality_chains_separate(self):
        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": "test-key",
                "NVIDIA_API_KEY": "test-key",
                "OPENROUTER_API_KEY": "test-key",
            },
        ):
            config = load_config("config")

        routes = {route.id: route for route in config.llm.get_route_configs()}
        self.assertNotIn("glm-bulk", routes)
        self.assertEqual(
            routes["openrouter-minimax-bulk"].fallback_route_id,
            "gemini-bulk-fallback",
        )
        self.assertEqual(
            routes["openrouter-minimax-complex"].fallback_route_id,
            "gemini-quality-fallback",
        )
        self.assertIn(
            "link_enricher.*",
            routes["openrouter-minimax-link"].caller_patterns,
        )
        self.assertNotIn(
            "link_enricher.*",
            routes["gemini-quality-fallback"].caller_patterns,
        )

        async def verify_routing():
            router = AsyncLLMRouter([
                FakeRouteClient(
                    route.id,
                    model=route.model,
                    route_profiles=route.profiles,
                    caller_patterns=route.caller_patterns,
                    fallback_route_id=route.fallback_route_id,
                    route_priority=route.priority,
                )
                for route in routes.values()
            ])
            link = await router.call_with_thinking(
                messages=[{"role": "user", "content": "links"}],
                profile=ThinkingLevel.STANDARD,
                caller="link_enricher.executive_summary",
            )
            summary = await router.call_with_thinking(
                messages=[{"role": "user", "content": "summary"}],
                profile=ThinkingLevel.DEEP,
                caller="orchestrator.summary",
            )
            bulk = await router.call_with_thinking(
                messages=[{"role": "user", "content": "batch"}],
                profile=ThinkingLevel.STANDARD,
                caller="news_analyzer.batch_1",
            )
            small_news = await router.call_with_thinking(
                messages=[{"role": "user", "content": "small news batch"}],
                profile=ThinkingLevel.DEEP,
                caller="news_analyzer.small_batch",
            )
            self.assertEqual(link.content, "openrouter-minimax-link")
            self.assertEqual(summary.content, "openrouter-minimax-complex")
            self.assertEqual(small_news.content, "openrouter-minimax-complex")
            self.assertEqual(bulk.content, "openrouter-minimax-bulk")

        asyncio.run(verify_routing())

        async def verify_orchestration_fallback():
            clients = []
            for route in routes.values():
                failures = (
                    [ProviderQuotaExhaustedError("20 RPD")]
                    if route.id in {
                        "openrouter-minimax-complex",
                        "gemini-quality-fallback",
                    }
                    else None
                )
                clients.append(FakeRouteClient(
                    route.id,
                    model=route.model,
                    failures=failures,
                    route_profiles=route.profiles,
                    caller_patterns=route.caller_patterns,
                    fallback_route_id=route.fallback_route_id,
                    route_priority=route.priority,
                ))
            router = AsyncLLMRouter(clients)
            first = await router.call_with_thinking(
                messages=[{"role": "user", "content": "summary"}],
                profile=ThinkingLevel.DEEP,
                caller="orchestrator.summary",
            )
            second = await router.call_with_thinking(
                messages=[{"role": "user", "content": "topics"}],
                profile=ThinkingLevel.ULTRATHINK,
                caller="orchestrator.topics",
            )
            self.assertEqual(first.content, "nvidia-glm-orchestration-backup")
            self.assertEqual(second.content, "nvidia-glm-orchestration-backup")

        asyncio.run(verify_orchestration_fallback())

    def test_single_model_config_normalizes_to_one_route(self):
        config = LLMProviderConfig(
            mode="openai-compatible",
            api_key="test-key",
            base_url="https://proxy.example.com/",
            model="claude-4.8-opus-aws",
        )

        routes = config.get_route_configs()

        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].id, "claude-4.8-opus-aws")
        self.assertEqual(routes[0].model, "claude-4.8-opus-aws")
        self.assertEqual(routes[0].mode, "openai-compatible")
        self.assertEqual(routes[0].api_key, "test-key")
        self.assertEqual(routes[0].base_url, "https://proxy.example.com")

    def test_multi_route_config_inherits_root_fields(self):
        config = LLMProviderConfig(
            mode="openai-compatible",
            api_key="root-key",
            base_url="https://proxy.example.com",
            model="claude-4.8-opus-aws",
            routes=[
                LLMRouteConfig(id="aws", model="claude-4.8-opus-aws"),
                LLMRouteConfig(id="gcp", model="claude-4.8-opus-gcp"),
                LLMRouteConfig(id="anthropic", model="claude-4.8-opus-anthropic"),
            ],
        )

        routes = config.get_route_configs()

        self.assertEqual([route.id for route in routes], ["aws", "gcp", "anthropic"])
        self.assertEqual([route.mode for route in routes], ["openai-compatible"] * 3)
        self.assertEqual([route.api_key for route in routes], ["root-key"] * 3)
        self.assertEqual(
            [route.model for route in routes],
            [
                "claude-4.8-opus-aws",
                "claude-4.8-opus-gcp",
                "claude-4.8-opus-anthropic",
            ],
        )

    def test_openrouter_mode_defaults_to_openrouter_base_url(self):
        config = LLMProviderConfig(
            mode="openrouter",
            api_key="test-key",
            model="nvidia/nemotron-3-ultra-550b-a55b:free",
        )

        self.assertEqual(config.base_url, "https://openrouter.ai/api/v1")
        self.assertEqual(config.get_route_configs()[0].base_url, "https://openrouter.ai/api/v1")

    def test_paid_minimax_route_repeats_preflight_price_cap(self):
        self.assertEqual(
            _openrouter_provider_preferences("minimax/minimax-m3"),
            {
                "sort": "price",
                "max_price": {"prompt": 0.24, "completion": 0.96},
            },
        )
        self.assertEqual(_openrouter_provider_preferences("another/model"), {})

    def test_gemini_mode_defaults_and_route_quota_fields(self):
        config = LLMProviderConfig(
            mode="gemini",
            api_key="test-key",
            model="gemini-3.5-flash-lite",
            requests_per_minute=15,
            tokens_per_minute=250000,
            requests_per_day=500,
            routes=[
                LLMRouteConfig(
                    id="quality",
                    model="gemini-3.6-flash",
                    priority=100,
                    fallback_route_id="bulk",
                    requests_per_minute=5,
                    requests_per_day=20,
                    profiles=["DEEP", "ULTRATHINK"],
                    caller_patterns=["orchestrator.*"],
                ),
                LLMRouteConfig(
                    id="bulk",
                    model="gemini-3.5-flash-lite",
                    profiles=["QUICK", "STANDARD"],
                ),
            ],
        )

        route = config.get_route_configs()[0]
        self.assertEqual(config.base_url, "https://generativelanguage.googleapis.com")
        self.assertEqual(route.mode, "gemini")
        self.assertEqual(route.requests_per_minute, 5)
        self.assertEqual(route.tokens_per_minute, 250000)
        self.assertEqual(route.requests_per_day, 20)
        self.assertEqual(route.priority, 100)
        self.assertEqual(route.profiles, ["DEEP", "ULTRATHINK"])
        self.assertEqual(route.fallback_route_id, "bulk")

    def test_empty_routes_fail_clearly(self):
        with self.assertRaises(ValidationError) as error:
            LLMProviderConfig(api_key="test-key", routes=[])

        self.assertIn("llm.routes must not be empty", str(error.exception))

    def test_all_hosted_opus_47_aliases_use_adaptive_thinking(self):
        for model in (
            "claude-4.8-opus-aws",
            "claude-4.8-opus-gcp",
            "claude-4.8-opus-anthropic",
        ):
            with self.subTest(model=model):
                self.assertTrue(_uses_adaptive_thinking(model))

    def test_non_claude_version_numbers_do_not_enable_adaptive_thinking(self):
        for model in (
            "z-ai/glm-5.2",
            "nvidia/nemotron-3-nano-30b-a3b",
            "gemini-3.6-flash",
        ):
            with self.subTest(model=model):
                self.assertFalse(_uses_adaptive_thinking(model))


class AsyncLLMRouterTests(unittest.TestCase):
    def test_route_in_cooldown_is_skipped_when_fallback_is_healthy(self):
        async def run():
            primary = FakeRouteClient(
                "primary",
                failures=[httpx.ConnectTimeout("free-tier endpoint timed out")],
            )
            fallback = FakeRouteClient("fallback")
            router = AsyncLLMRouter([primary, fallback])

            first = await router.call(messages=[{"role": "user", "content": "first"}])
            router._next_route_index = 0
            second = await router.call(messages=[{"role": "user", "content": "second"}])

            self.assertEqual(first.content, "fallback")
            self.assertEqual(second.content, "fallback")
            self.assertEqual(len(primary.calls), 1)
            self.assertEqual(len(fallback.calls), 2)
            self.assertEqual(
                router.get_health_snapshot()["primary"]["cooldown_skips"],
                1,
            )

        asyncio.run(run())

    def test_round_robin_rotation(self):
        async def run():
            router = AsyncLLMRouter([
                FakeRouteClient("aws"),
                FakeRouteClient("gcp"),
                FakeRouteClient("anthropic"),
            ])

            providers = []
            for _ in range(6):
                response = await router.call(messages=[{"role": "user", "content": "hi"}])
                providers.append(response.content)

            self.assertEqual(
                providers,
                ["aws", "gcp", "anthropic", "aws", "gcp", "anthropic"],
            )

        asyncio.run(run())

    def test_per_provider_cap_is_applied_from_environment(self):
        async def run():
            previous = os.environ.get("LLM_MAX_CONCURRENT_REQUESTS")
            os.environ["LLM_MAX_CONCURRENT_REQUESTS"] = "3"
            router = None
            try:
                config = LLMProviderConfig(
                    mode="openai-compatible",
                    api_key="test-key",
                    base_url="https://proxy.example.com",
                    model="claude-4.8-opus-aws",
                    routes=[
                        LLMRouteConfig(id="aws", model="claude-4.8-opus-aws"),
                        LLMRouteConfig(id="gcp", model="claude-4.8-opus-gcp"),
                        LLMRouteConfig(id="anthropic", model="claude-4.8-opus-anthropic"),
                    ],
                )
                router = AsyncLLMRouter.from_config(config)

                self.assertIsInstance(router, AsyncLLMRouter)
                self.assertEqual(
                    [client.max_concurrent_requests for client in router.clients],
                    [3, 3, 3],
                )
                self.assertEqual(router.max_total_concurrent_requests, 9)
            finally:
                if router is not None:
                    await router.close()
                if previous is None:
                    os.environ.pop("LLM_MAX_CONCURRENT_REQUESTS", None)
                else:
                    os.environ["LLM_MAX_CONCURRENT_REQUESTS"] = previous

        asyncio.run(run())

    def test_three_providers_at_cap_eight_allow_twenty_four_total_requests(self):
        async def run():
            config = LLMProviderConfig(
                mode="openai-compatible",
                api_key="test-key",
                base_url="https://proxy.example.com",
                model="claude-4.8-opus-aws",
                routes=[
                    LLMRouteConfig(
                        id="aws",
                        model="claude-4.8-opus-aws",
                        max_concurrent_requests=8,
                    ),
                    LLMRouteConfig(
                        id="gcp",
                        model="claude-4.8-opus-gcp",
                        max_concurrent_requests=8,
                    ),
                    LLMRouteConfig(
                        id="anthropic",
                        model="claude-4.8-opus-anthropic",
                        max_concurrent_requests=8,
                    ),
                ],
            )
            router = AsyncLLMRouter.from_config(config)
            try:
                self.assertIsInstance(router, AsyncLLMRouter)
                self.assertEqual(
                    [client.max_concurrent_requests for client in router.clients],
                    [8, 8, 8],
                )
                self.assertEqual(router.max_total_concurrent_requests, 24)
            finally:
                await router.close()

        asyncio.run(run())

    def test_fast_connection_failure_retries_same_provider_once(self):
        async def run():
            aws = FakeRouteClient("aws", failures=[httpx.ConnectError("boom")])
            gcp = FakeRouteClient("gcp")
            anthropic = FakeRouteClient("anthropic")
            router = AsyncLLMRouter([aws, gcp, anthropic])

            response = await router.call(messages=[{"role": "user", "content": "hi"}])

            self.assertEqual(response.content, "aws")
            self.assertEqual(len(aws.calls), 2)
            self.assertEqual(len(gcp.calls), 0)
            self.assertEqual(
                aws.calls[1]["routing_context"]["same_provider_retry"],
                1,
            )
            self.assertEqual(
                aws.calls[1]["routing_context"]["retry_reason"],
                "ConnectError",
            )

        asyncio.run(run())

    def test_second_fast_connection_failure_falls_back(self):
        async def run():
            aws = FakeRouteClient(
                "aws",
                failures=[httpx.ConnectError("first"), httpx.ConnectError("second")],
            )
            gcp = FakeRouteClient("gcp")
            router = AsyncLLMRouter([aws, gcp])

            response = await router.call(messages=[{"role": "user", "content": "hi"}])

            self.assertEqual(response.content, "gcp")
            self.assertEqual(len(aws.calls), 2)
            self.assertEqual(len(gcp.calls), 1)
            self.assertEqual(gcp.calls[0]["routing_context"]["attempt"], 2)
            self.assertEqual(gcp.calls[0]["routing_context"]["fallback_from"], "aws")
            self.assertEqual(gcp.calls[0]["routing_context"]["retry_reason"], "ConnectError")

        asyncio.run(run())

    def test_explicit_chain_root_starts_each_new_call(self):
        async def run():
            primary = FakeRouteClient("primary", fallback_route_id="fallback")
            fallback = FakeRouteClient("fallback")
            router = AsyncLLMRouter([primary, fallback])

            responses = [
                await router.call(messages=[{"role": "user", "content": str(index)}])
                for index in range(3)
            ]

            self.assertEqual([response.content for response in responses], ["primary"] * 3)
            self.assertEqual(len(primary.calls), 3)
            self.assertEqual(len(fallback.calls), 0)

        asyncio.run(run())

    def test_retryable_failure_prioritizes_explicit_fallback_route(self):
        async def run():
            primary = FakeRouteClient(
                "primary",
                failures=[httpx.ReadTimeout("provider stalled")],
                fallback_route_id="preferred-fallback",
            )
            unrelated = FakeRouteClient("unrelated")
            preferred = FakeRouteClient("preferred-fallback")
            router = AsyncLLMRouter([primary, unrelated, preferred])

            response = await router.call(messages=[{"role": "user", "content": "hi"}])

            self.assertEqual(response.content, "preferred-fallback")
            self.assertEqual(len(primary.calls), 1)
            self.assertEqual(len(unrelated.calls), 0)
            self.assertEqual(
                preferred.calls[0]["routing_context"]["retry_reason"],
                "ReadTimeout",
            )

        asyncio.run(run())

    def test_invalid_openrouter_response_falls_back_to_another_route(self):
        async def run():
            primary = FakeRouteClient(
                "primary",
                failures=[OpenRouterResponseError("missing choices")],
            )
            fallback = FakeRouteClient("free-router-fallback")
            router = AsyncLLMRouter([primary, fallback])

            response = await router.call(messages=[{"role": "user", "content": "hi"}])

            self.assertEqual(response.content, "free-router-fallback")
            self.assertEqual(
                fallback.calls[0]["routing_context"]["retry_reason"],
                "invalid_openrouter_response",
            )

        asyncio.run(run())

    def test_client_error_does_not_cross_provider_retry(self):
        async def run():
            aws = FakeRouteClient("aws", failures=[HTTP400("bad request")])
            gcp = FakeRouteClient("gcp")
            router = AsyncLLMRouter([aws, gcp])

            with self.assertRaises(HTTP400):
                await router.call(messages=[{"role": "user", "content": "hi"}])

            self.assertEqual(len(aws.calls), 1)
            self.assertEqual(len(gcp.calls), 0)

        asyncio.run(run())

    def test_removed_model_fails_over_and_is_disabled_for_the_run(self):
        async def run():
            removed = FakeRouteClient(
                "removed",
                failures=[HTTP410("model endpoint is no longer available")],
            )
            fallback = FakeRouteClient("fallback")
            router = AsyncLLMRouter([removed, fallback])

            first = await router.call(messages=[{"role": "user", "content": "hi"}])
            second = await router.call(messages=[{"role": "user", "content": "again"}])

            self.assertEqual(first.content, "fallback")
            self.assertEqual(second.content, "fallback")
            self.assertEqual(len(removed.calls), 1)
            self.assertEqual(
                router.get_health_snapshot()["removed"]["disabled_reason"],
                "http_410",
            )

        asyncio.run(run())

    def test_provider_rpd_429_is_disabled_instead_of_retried_later(self):
        async def run():
            limited = FakeRouteClient(
                "limited",
                failures=[HTTP429RPD("GenerateRequestsPerDay quota exhausted")],
            )
            fallback = FakeRouteClient("fallback")
            router = AsyncLLMRouter([limited, fallback])

            response = await router.call(messages=[{"role": "user", "content": "hi"}])

            self.assertEqual(response.content, "fallback")
            self.assertEqual(
                router.get_health_snapshot()["limited"]["disabled_reason"],
                "provider_rpd_exhausted",
            )

        asyncio.run(run())

    def test_unsupported_provider_parameter_fails_over_and_disables_route(self):
        async def run():
            incompatible = FakeRouteClient(
                "incompatible",
                failures=[HTTP400UnsupportedParameter("Unsupported parameter(s): output_config")],
            )
            fallback = FakeRouteClient("fallback")
            router = AsyncLLMRouter([incompatible, fallback])

            response = await router.call(messages=[{"role": "user", "content": "hi"}])

            self.assertEqual(response.content, "fallback")
            self.assertEqual(
                router.get_health_snapshot()["incompatible"]["disabled_reason"],
                "request_compatibility_http_400",
            )

        asyncio.run(run())

    def test_profile_and_caller_routing_prefers_quality_route(self):
        async def run():
            bulk = FakeRouteClient(
                "bulk",
                route_profiles=["QUICK", "STANDARD", "DEEP"],
            )
            quality = FakeRouteClient(
                "quality",
                route_profiles=["STANDARD", "DEEP", "ULTRATHINK"],
                caller_patterns=["orchestrator.*", "*_analyzer.reduce_rank"],
            )
            router = AsyncLLMRouter([bulk, quality])

            response = await router.call_with_thinking(
                messages=[{"role": "user", "content": "rank"}],
                profile=ThinkingLevel.DEEP,
                caller="news_analyzer.reduce_rank",
            )

            self.assertEqual(response.content, "quality")
            self.assertEqual(len(bulk.calls), 0)
            self.assertEqual(len(quality.calls), 1)

        asyncio.run(run())

    def test_deep_bulk_caller_stays_on_flash_lite_route(self):
        async def run():
            bulk = FakeRouteClient(
                "bulk",
                route_profiles=["QUICK", "STANDARD", "DEEP"],
            )
            quality = FakeRouteClient(
                "quality",
                route_profiles=["STANDARD", "DEEP", "ULTRATHINK"],
                caller_patterns=["orchestrator.*", "*_analyzer.reduce_rank"],
            )
            router = AsyncLLMRouter([bulk, quality])

            response = await router.call_with_thinking(
                messages=[{"role": "user", "content": "curate"}],
                profile=ThinkingLevel.DEEP,
                caller="continuity.curator",
            )

            self.assertEqual(response.content, "bulk")

        asyncio.run(run())

    def test_caller_restricted_quality_route_is_not_used_for_bulk_batch(self):
        async def run():
            bulk = FakeRouteClient(
                "bulk",
                route_profiles=["QUICK", "STANDARD", "DEEP"],
            )
            quality = FakeRouteClient(
                "quality",
                route_profiles=["STANDARD", "DEEP", "ULTRATHINK"],
                caller_patterns=["orchestrator.*", "*_analyzer.reduce_rank"],
            )
            router = AsyncLLMRouter([bulk, quality])

            response = await router.call_with_thinking(
                messages=[{"role": "user", "content": "map"}],
                profile=ThinkingLevel.STANDARD,
                caller="news_analyzer.batch_1",
            )

            self.assertEqual(response.content, "bulk")
            self.assertEqual(len(quality.calls), 0)

        asyncio.run(run())

    def test_plain_call_is_routed_as_quick_bulk_work(self):
        async def run():
            bulk = FakeRouteClient("bulk", route_profiles=["QUICK", "STANDARD"])
            quality = FakeRouteClient(
                "quality",
                route_profiles=["STANDARD", "DEEP"],
                caller_patterns=["orchestrator.*"],
            )
            router = AsyncLLMRouter([bulk, quality])

            response = await router.call(
                messages=[{"role": "user", "content": "classify"}],
                caller="interest_filter",
            )

            self.assertEqual(response.content, "bulk")
            self.assertEqual(len(quality.calls), 0)

        asyncio.run(run())

    def test_rpd_exhaustion_is_retryable_on_fallback_route(self):
        async def run():
            quality = FakeRouteClient(
                "quality",
                failures=[ProviderQuotaExhaustedError("20 RPD")],
                route_profiles=["DEEP"],
                caller_patterns=["orchestrator.*"],
            )
            bulk = FakeRouteClient("bulk", route_profiles=["DEEP"])
            router = AsyncLLMRouter([quality, bulk])

            response = await router.call_with_thinking(
                messages=[{"role": "user", "content": "summarize"}],
                profile=ThinkingLevel.DEEP,
                caller="orchestrator.summary",
            )

            self.assertEqual(response.content, "bulk")
            self.assertEqual(
                bulk.calls[0]["routing_context"]["retry_reason"],
                "provider_rpd_exhausted",
            )

        asyncio.run(run())

    def test_opus_47_request_uses_top_level_adaptive_thinking(self):
        async def run():
            captured_kwargs = {}
            captured_context = {}
            client = AsyncAnthropicClient(
                api_key="test-key",
                base_url="https://proxy.example.com",
                model="claude-4.8-opus-aws",
                mode="openai-compatible",
                max_retries=0,
            )

            async def fake_create_message(request_context=None, **kwargs):
                captured_kwargs.update(kwargs)
                captured_context.update(request_context or {})
                return FakeAnthropicResponse()

            client._create_message = fake_create_message
            try:
                await client.call_with_thinking(
                    messages=[{"role": "user", "content": "summarize"}],
                    profile=ThinkingLevel.QUICK,
                    caller="test.adaptive",
                )
            finally:
                await client.close()

            self.assertEqual(
                captured_kwargs["thinking"],
                {"type": "adaptive", "display": "summarized"},
            )
            self.assertNotIn("budget_tokens", captured_kwargs["thinking"])
            self.assertEqual(
                captured_kwargs["extra_body"],
                {"output_config": {"effort": "high"}},
            )
            self.assertNotIn("temperature", captured_kwargs)
            self.assertEqual(captured_context["thinking_type"], "adaptive")
            self.assertNotIn("profile", captured_context)
            self.assertEqual(captured_context["analysis_profile"], "QUICK")
            self.assertEqual(captured_context["adaptive_effort"], "high")
            self.assertEqual(captured_context["response_max_tokens"], 65536)

        asyncio.run(run())

    def test_opus_47_plain_call_uses_top_level_adaptive_thinking(self):
        async def run():
            captured_kwargs = {}
            captured_context = {}
            client = AsyncAnthropicClient(
                api_key="test-key",
                base_url="https://proxy.example.com",
                model="claude-4.8-opus-gcp",
                mode="openai-compatible",
                max_retries=0,
            )

            async def fake_create_message(request_context=None, **kwargs):
                captured_kwargs.update(kwargs)
                captured_context.update(request_context or {})
                return FakeAnthropicResponse()

            client._create_message = fake_create_message
            try:
                await client.call(
                    messages=[{"role": "user", "content": "classify"}],
                    caller="test.plain",
                )
            finally:
                await client.close()

            self.assertEqual(
                captured_kwargs["thinking"],
                {"type": "adaptive", "display": "summarized"},
            )
            self.assertNotIn("budget_tokens", captured_kwargs["thinking"])
            self.assertEqual(
                captured_kwargs["extra_body"],
                {"output_config": {"effort": "high"}},
            )
            self.assertNotIn("temperature", captured_kwargs)
            self.assertEqual(captured_context["kind"], "adaptive_message")
            self.assertEqual(captured_context["thinking_type"], "adaptive")
            self.assertNotIn("profile", captured_context)
            self.assertEqual(captured_context["analysis_profile"], "plain")
            self.assertEqual(captured_context["adaptive_effort"], "high")

        asyncio.run(run())

    def test_openrouter_call_with_thinking_uses_reasoning_effort(self):
        async def run():
            captured_kwargs = {}
            captured_context = {}
            client = AsyncAnthropicClient(
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1",
                model="nvidia/nemotron-3-ultra-550b-a55b:free",
                mode="openrouter",
                max_retries=0,
            )

            async def fake_create_message(request_context=None, **kwargs):
                captured_kwargs.update(kwargs)
                captured_context.update(request_context or {})
                return FakeOpenRouterResponse()

            client._create_message = fake_create_message
            try:
                await client.call_with_thinking(
                    messages=[{"role": "user", "content": "summarize"}],
                    profile=ThinkingLevel.QUICK,
                    caller="test.openrouter",
                )
            finally:
                await client.close()

            self.assertNotIn("thinking", captured_kwargs)
            self.assertEqual(
                captured_kwargs["reasoning"],
                {"effort": "high", "exclude": False},
            )
            self.assertEqual(captured_kwargs["model"], "nvidia/nemotron-3-ultra-550b-a55b:free")
            self.assertEqual(captured_context["kind"], "openrouter_chat")
            self.assertEqual(captured_context["thinking_type"], "adaptive")
            self.assertEqual(captured_context["analysis_profile"], "QUICK")
            self.assertEqual(captured_context["adaptive_effort"], "high")

        asyncio.run(run())

    def test_openrouter_complex_call_uses_full_output_budget(self):
        async def run():
            captured_kwargs = {}
            client = AsyncAnthropicClient(
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1",
                model="minimax/minimax-m3",
                mode="openrouter",
                max_output_tokens=32768,
                max_retries=0,
            )

            async def fake_create_message(request_context=None, **kwargs):
                captured_kwargs.update(kwargs)
                return FakeOpenRouterResponse()

            client._create_message = fake_create_message
            try:
                await client.call_with_thinking(
                    messages=[{"role": "user", "content": "detect topics"}],
                    profile=ThinkingLevel.ULTRATHINK,
                    caller="orchestrator.topics",
                    full_output_budget=True,
                )
            finally:
                await client.close()

            self.assertEqual(captured_kwargs["max_tokens"], 32768)
            self.assertEqual(
                captured_kwargs["reasoning"],
                {"effort": "max", "exclude": False},
            )

        asyncio.run(run())

    def test_glm_52_does_not_receive_opus_output_config(self):
        async def run():
            captured_kwargs = {}
            client = AsyncAnthropicClient(
                api_key="test-key",
                base_url="https://integrate.api.nvidia.com/v1",
                model="z-ai/glm-5.2",
                mode="openai-compatible",
                max_output_tokens=16384,
                max_retries=0,
            )

            async def fake_create_message(request_context=None, **kwargs):
                captured_kwargs.update(kwargs)
                return FakeAnthropicResponse()

            client._create_message = fake_create_message
            try:
                await client.call_with_thinking(
                    messages=[{"role": "user", "content": "rank"}],
                    profile=ThinkingLevel.DEEP,
                    caller="news_analyzer.reduce_rank",
                )
            finally:
                await client.close()

            self.assertNotIn("extra_body", captured_kwargs)
            self.assertEqual(captured_kwargs["temperature"], 1.0)
            self.assertEqual(captured_kwargs["model"], "z-ai/glm-5.2")

        asyncio.run(run())

    def test_nemotron_accepts_valid_content_without_separate_reasoning_block(self):
        async def run():
            client = AsyncAnthropicClient(
                api_key="test-key",
                base_url="https://integrate.api.nvidia.com/v1",
                model="nvidia/nemotron-3-nano-30b-a3b",
                mode="openai-compatible",
                max_output_tokens=16384,
                max_retries=0,
            )

            async def fake_create_message(request_context=None, **kwargs):
                return FakeAnthropicResponse()

            client._create_message = fake_create_message
            try:
                response = await client.call_with_thinking(
                    messages=[{"role": "user", "content": "analyze"}],
                    profile=ThinkingLevel.STANDARD,
                    caller="news_analyzer.batch_0",
                )
            finally:
                await client.close()

            self.assertEqual(response.content, "ok")
            self.assertEqual(response.thinking_block_count, 0)

        asyncio.run(run())

    def test_nvidia_hosted_payloads_use_supported_parameters(self):
        async def run():
            captured_payloads = []

            class FakeCompletions:
                async def create(self, **kwargs):
                    captured_payloads.append(kwargs)
                    return SimpleNamespace(
                        choices=[SimpleNamespace(
                            message=SimpleNamespace(
                                content='{"ok": true}',
                                model_extra={"reasoning_content": "reasoning"},
                            ),
                            finish_reason="stop",
                        )],
                        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
                        model=kwargs["model"],
                    )

            class FakeOpenAI:
                def __init__(self):
                    self.chat = SimpleNamespace(completions=FakeCompletions())

                async def close(self):
                    return None

            client = AsyncAnthropicClient(
                api_key="test-key",
                base_url="https://integrate.api.nvidia.com/v1",
                model="nvidia/nemotron-3-nano-30b-a3b",
                mode="openai-compatible",
                max_retries=0,
            )
            await client._openai_client.close()
            client._openai_client = FakeOpenAI()
            client.log_requests = False
            try:
                await client._create_openai_completion(
                    model="nvidia/nemotron-3-nano-30b-a3b",
                    messages=[{"role": "user", "content": "analyze"}],
                    max_tokens=16384,
                    temperature=1.0,
                    thinking={"type": "enabled", "budget_tokens": 8192},
                )
                await client._create_openai_completion(
                    model="z-ai/glm-5.2",
                    messages=[{"role": "user", "content": "rank"}],
                    max_tokens=16384,
                    temperature=1.0,
                )
            finally:
                await client.close()

            nemotron, glm = captured_payloads
            self.assertEqual(nemotron["max_tokens"], 16384)
            self.assertNotIn("max_completion_tokens", nemotron)
            self.assertEqual(nemotron["extra_body"], {"reasoning_budget": 8192})
            self.assertNotIn("max_thinking_tokens", nemotron["extra_body"])
            self.assertEqual(glm["max_tokens"], 16384)
            self.assertEqual(glm["top_p"], 1)
            self.assertEqual(glm["seed"], 42)
            self.assertNotIn("extra_body", glm)

        asyncio.run(run())

    def test_openai_sdk_serializes_nvidia_payloads_on_the_wire(self):
        async def run():
            request_bodies = []

            async def handler(request):
                body = json.loads(request.content)
                request_bodies.append(body)
                return httpx.Response(
                    200,
                    json={
                        "id": "chatcmpl-test",
                        "object": "chat.completion",
                        "created": 0,
                        "model": body["model"],
                        "choices": [{
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": '{"ok": true}',
                            },
                            "finish_reason": "stop",
                        }],
                        "usage": {
                            "prompt_tokens": 10,
                            "completion_tokens": 5,
                            "total_tokens": 15,
                        },
                    },
                )

            mock_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            sdk_client = openai.AsyncOpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key="test-key",
                http_client=mock_http,
                max_retries=0,
            )
            client = AsyncAnthropicClient(
                api_key="test-key",
                base_url="https://integrate.api.nvidia.com/v1",
                model="nvidia/nemotron-3-nano-30b-a3b",
                mode="openai-compatible",
                max_retries=0,
            )
            await client._openai_client.close()
            client._openai_client = sdk_client
            client.log_requests = False
            try:
                await client._create_openai_completion(
                    model="nvidia/nemotron-3-nano-30b-a3b",
                    messages=[{"role": "user", "content": "analyze"}],
                    max_tokens=16384,
                    temperature=1.0,
                    thinking={"type": "enabled", "budget_tokens": 8192},
                )
                await client._create_openai_completion(
                    model="z-ai/glm-5.2",
                    messages=[{"role": "user", "content": "rank"}],
                    max_tokens=16384,
                    temperature=1.0,
                )
            finally:
                await client.close()

            nemotron, glm = request_bodies
            self.assertEqual(nemotron["max_tokens"], 16384)
            self.assertEqual(nemotron["reasoning_budget"], 8192)
            self.assertNotIn("max_thinking_tokens", nemotron)
            self.assertNotIn("max_completion_tokens", nemotron)
            self.assertEqual(glm["max_tokens"], 16384)
            self.assertEqual(glm["top_p"], 1)
            self.assertEqual(glm["seed"], 42)
            self.assertNotIn("output_config", glm)

        asyncio.run(run())


class GeminiResponseTests(unittest.TestCase):
    def test_normalizes_text_thoughts_usage_and_truncation(self):
        class Part:
            def __init__(self, text, thought=False):
                self.text = text
                self.thought = thought

        class Content:
            parts = [Part("reasoning", thought=True), Part('{"ok": true}')]

        class Candidate:
            content = Content()
            finish_reason = "MAX_TOKENS"

        class Usage:
            prompt_token_count = 100
            candidates_token_count = 20
            thoughts_token_count = 30

        class Response:
            candidates = [Candidate()]
            usage_metadata = Usage()
            model_version = "gemini-3.6-flash"

        result = _normalize_gemini_response(Response(), "configured-model")

        self.assertEqual(result.content, '{"ok": true}')
        self.assertEqual(result.thinking, "reasoning")
        self.assertEqual(result.stop_reason, "max_tokens")
        self.assertEqual(result.usage["thinking_tokens"], 30)

    def test_rate_limiter_enforces_daily_quota(self):
        limiter = ProviderRateLimiter(
            requests_per_minute=None,
            tokens_per_minute=None,
            requests_per_day=1,
        )
        limiter.acquire(1)
        with self.assertRaises(ProviderQuotaExhaustedError):
            limiter.acquire(1)


if __name__ == "__main__":
    unittest.main()
