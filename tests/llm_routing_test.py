"""Focused tests for Opus 4.8 adaptive thinking and async LLM routing."""

import asyncio
import os
import unittest

import httpx
from pydantic import ValidationError

from agents.config.schema import LLMProviderConfig, LLMRouteConfig
from agents.llm_client import (
    AsyncAnthropicClient,
    AsyncLLMRouter,
    LLMResponse,
    OpenRouterResponseError,
    ProviderQuotaExhaustedError,
    ProviderRateLimiter,
    ThinkingLevel,
    _normalize_gemini_response,
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
    ):
        self.provider_id = provider_id
        self.model = model or f"claude-4.8-opus-{provider_id}"
        self.max_concurrent_requests = 8
        self.failures = list(failures or [])
        self.calls = []
        self.route_profiles = set(route_profiles or [])
        self.caller_patterns = list(caller_patterns or [])

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


class LLMRouteConfigTests(unittest.TestCase):
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
                    requests_per_minute=5,
                    requests_per_day=20,
                    profiles=["DEEP", "ULTRATHINK"],
                    caller_patterns=["orchestrator.*"],
                )
            ],
        )

        route = config.get_route_configs()[0]
        self.assertEqual(config.base_url, "https://generativelanguage.googleapis.com")
        self.assertEqual(route.mode, "gemini")
        self.assertEqual(route.requests_per_minute, 5)
        self.assertEqual(route.tokens_per_minute, 250000)
        self.assertEqual(route.requests_per_day, 20)
        self.assertEqual(route.profiles, ["DEEP", "ULTRATHINK"])

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


class AsyncLLMRouterTests(unittest.TestCase):
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

    def test_retryable_failure_falls_back_to_another_provider(self):
        async def run():
            aws = FakeRouteClient("aws", failures=[httpx.ConnectError("boom")])
            gcp = FakeRouteClient("gcp")
            anthropic = FakeRouteClient("anthropic")
            router = AsyncLLMRouter([aws, gcp, anthropic])

            response = await router.call(messages=[{"role": "user", "content": "hi"}])

            self.assertEqual(response.content, "gcp")
            self.assertEqual(len(aws.calls), 1)
            self.assertEqual(len(gcp.calls), 1)
            self.assertEqual(gcp.calls[0]["routing_context"]["attempt"], 2)
            self.assertEqual(gcp.calls[0]["routing_context"]["fallback_from"], "aws")
            self.assertEqual(gcp.calls[0]["routing_context"]["retry_reason"], "ConnectError")

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

    def test_openrouter_call_with_thinking_uses_plain_chat_completion(self):
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
            self.assertEqual(captured_kwargs["model"], "nvidia/nemotron-3-ultra-550b-a55b:free")
            self.assertEqual(captured_context["kind"], "openrouter_chat")
            self.assertEqual(captured_context["analysis_profile"], "QUICK")

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
