"""
Anthropic Client with Adaptive/Manual Thinking Support

This module provides a wrapper around the Anthropic SDK that:
1. Uses Bearer token authentication (custom httpx transport)
2. Supports Opus 4.8 adaptive thinking and legacy manual thinking budgets
3. Returns structured responses including thinking blocks
4. Automatically tracks token usage and costs
"""

import os
import re
import json
import logging
import time
import asyncio
import fnmatch
import threading
from collections import deque
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from enum import IntEnum

import httpx
import anthropic
import openai
from google import genai
from google.genai import types as genai_types

from .cost_tracker import get_tracker
from agents.openrouter_pricing import provider_preferences as openrouter_provider_preferences

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .config import LLMProviderConfig
    from .config.schema import ResolvedLLMRouteConfig

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    """Read an integer environment setting with validation."""
    raw_value = os.environ.get(name)
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        logger.warning(f"Ignoring invalid {name}={raw_value!r}; using {default}")
        return default
    if value < minimum:
        logger.warning(f"Ignoring {name}={value}; minimum is {minimum}, using {default}")
        return default
    return value


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    """Read a float environment setting with validation."""
    raw_value = os.environ.get(name)
    if not raw_value:
        return default
    try:
        value = float(raw_value)
    except ValueError:
        logger.warning(f"Ignoring invalid {name}={raw_value!r}; using {default}")
        return default
    if value < minimum:
        logger.warning(f"Ignoring {name}={value}; minimum is {minimum}, using {default}")
        return default
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment setting."""
    raw_value = os.environ.get(name)
    if raw_value is None or raw_value == "":
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    logger.warning(f"Ignoring invalid {name}={raw_value!r}; using {default}")
    return default


def _routing_record_fields(context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return prompt-free route metadata for the public cost/health tracker."""
    context = context or {}
    return {
        "attempt": int(context.get("attempt") or 1),
        "same_provider_retry": int(context.get("same_provider_retry") or 0),
        "fallback_from": context.get("fallback_from"),
        "retry_reason": context.get("retry_reason"),
    }


class ThinkingLevel(IntEnum):
    """Internal analysis profiles.

    On Opus 4.8+, these legacy budget values are mapped to adaptive effort
    levels. On older Claude models, they remain manual thinking budgets.
    """
    QUICK = 4096       # Simple tasks (summarization)
    STANDARD = 8192    # Normal analysis
    DEEP = 16000       # Complex ranking
    ULTRATHINK = 32000 # Cross-category synthesis


# Map internal pipeline analysis profiles to Opus 4.8+ effort levels. Effort is
# the provider-facing reasoning knob; the enum values only remain for older
# manual-thinking models and backwards-compatible call sites.
BUDGET_TO_EFFORT = {
    ThinkingLevel.QUICK: "high",
    ThinkingLevel.STANDARD: "xhigh",
    ThinkingLevel.DEEP: "max",
    ThinkingLevel.ULTRATHINK: "max",
}

# Opus 4.8 adaptive thinking does not use fixed thinking budgets. Keep the
# response ceiling separate from internal profiles so logs do not imply that
# QUICK/STANDARD/DEEP/ULTRATHINK are Anthropic token-budget settings.
DEFAULT_ADAPTIVE_MAX_TOKENS = 65536

THINKING_LEVEL_NAMES = {
    ThinkingLevel.QUICK: "QUICK",
    ThinkingLevel.STANDARD: "STANDARD",
    ThinkingLevel.DEEP: "DEEP",
    ThinkingLevel.ULTRATHINK: "ULTRATHINK",
}

OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
GEMINI_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"

GEMINI_PROFILE_TO_THINKING = {
    ThinkingLevel.QUICK: "low",
    ThinkingLevel.STANDARD: "medium",
    ThinkingLevel.DEEP: "high",
    ThinkingLevel.ULTRATHINK: "high",
}


def _uses_openrouter(mode: str) -> bool:
    return mode == "openrouter"


def _openrouter_provider_preferences(model: str) -> Dict[str, Any]:
    """Apply the paid complex-route price policy to OpenRouter requests."""
    return openrouter_provider_preferences(model)


def _uses_gemini(mode: str) -> bool:
    return mode == "gemini"


class ProviderQuotaExhaustedError(RuntimeError):
    """Raised when an in-process provider RPD quota has been exhausted."""


class ProviderRateLimiter:
    """Shared process-local RPM, input-TPM, and RPD limiter for one model."""

    def __init__(
        self,
        requests_per_minute: Optional[int],
        tokens_per_minute: Optional[int],
        requests_per_day: Optional[int],
    ):
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.requests_per_day = requests_per_day
        self._lock = threading.Lock()
        self._request_times = deque()
        self._token_events = deque()
        self._day = datetime.now(timezone.utc).date()
        self._daily_requests = 0

    def acquire(self, estimated_input_tokens: int) -> None:
        while True:
            wait_seconds = 0.0
            now = time.monotonic()
            utc_day = datetime.now(timezone.utc).date()
            with self._lock:
                if utc_day != self._day:
                    self._day = utc_day
                    self._daily_requests = 0

                cutoff = now - 60.0
                while self._request_times and self._request_times[0] <= cutoff:
                    self._request_times.popleft()
                while self._token_events and self._token_events[0][0] <= cutoff:
                    self._token_events.popleft()

                if (
                    self.requests_per_day is not None
                    and self._daily_requests >= self.requests_per_day
                ):
                    raise ProviderQuotaExhaustedError(
                        f"Daily request quota exhausted ({self.requests_per_day} RPD)"
                    )

                if (
                    self.requests_per_minute is not None
                    and len(self._request_times) >= self.requests_per_minute
                ):
                    wait_seconds = max(wait_seconds, self._request_times[0] + 60.0 - now)

                minute_tokens = sum(tokens for _, tokens in self._token_events)
                if (
                    self.tokens_per_minute is not None
                    and minute_tokens + estimated_input_tokens > self.tokens_per_minute
                    and self._token_events
                ):
                    wait_seconds = max(wait_seconds, self._token_events[0][0] + 60.0 - now)

                if wait_seconds <= 0:
                    self._request_times.append(now)
                    self._token_events.append((now, estimated_input_tokens))
                    self._daily_requests += 1
                    return

            time.sleep(max(wait_seconds, 0.05))


_RATE_LIMITERS: Dict[Tuple[str, str, str], ProviderRateLimiter] = {}
_RATE_LIMITERS_LOCK = threading.Lock()


def _get_rate_limiter(
    mode: str,
    base_url: str,
    model: str,
    requests_per_minute: Optional[int],
    tokens_per_minute: Optional[int],
    requests_per_day: Optional[int],
) -> ProviderRateLimiter:
    key = (mode, base_url, model)
    with _RATE_LIMITERS_LOCK:
        limiter = _RATE_LIMITERS.get(key)
        if limiter is None:
            limiter = ProviderRateLimiter(
                requests_per_minute,
                tokens_per_minute,
                requests_per_day,
            )
            _RATE_LIMITERS[key] = limiter
        return limiter


@dataclass
class ResponseUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class ResponseBlock:
    type: str
    text: Optional[str] = None
    thinking: Optional[str] = None


@dataclass
class ProviderResponse:
    content: List[ResponseBlock]
    usage: ResponseUsage
    model: str
    stop_reason: Optional[str] = None


class OpenRouterResponseError(ValueError):
    """Raised when OpenRouter returns a successful but unusable response."""


def _coerce_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(content)


def _build_openrouter_messages(
    messages: List[Dict[str, Any]],
    system: Optional[str] = None,
) -> List[Dict[str, str]]:
    payload_messages: List[Dict[str, str]] = []
    if system:
        payload_messages.append({"role": "system", "content": system})
    for message in messages:
        payload_messages.append(
            {
                "role": message["role"],
                "content": _coerce_message_content(message.get("content", "")),
            }
        )
    return payload_messages


def _extract_openrouter_text(message_content: Any) -> str:
    if isinstance(message_content, str):
        return message_content
    if isinstance(message_content, list):
        parts = []
        for item in message_content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part)
    if message_content is None:
        return ""
    return str(message_content)


def _normalize_openrouter_response(response_json: Dict[str, Any]) -> ProviderResponse:
    choices = response_json.get("choices") or []
    if not choices:
        error = response_json.get("error")
        detail = ""
        if isinstance(error, dict):
            detail = str(error.get("message") or error.get("code") or "")
        elif error:
            detail = str(error)
        suffix = f": {detail}" if detail else ""
        raise OpenRouterResponseError(
            f"OpenRouter response did not include any choices{suffix}"
        )

    choice = choices[0]
    message = choice.get("message") or {}
    text = _extract_openrouter_text(message.get("content"))
    reasoning = _extract_openrouter_text(
        message.get("reasoning") or message.get("reasoning_content")
    )
    usage_json = response_json.get("usage") or {}
    usage = ResponseUsage(
        input_tokens=int(usage_json.get("prompt_tokens") or 0),
        output_tokens=int(usage_json.get("completion_tokens") or 0),
        cache_creation_input_tokens=int(usage_json.get("cache_creation_input_tokens") or 0),
        cache_read_input_tokens=int(usage_json.get("cache_read_input_tokens") or 0),
    )
    return ProviderResponse(
        content=(
            ([ResponseBlock(type="thinking", thinking=reasoning)] if reasoning else [])
            + [ResponseBlock(type="text", text=text)]
        ),
        usage=usage,
        model=response_json.get("model") or "",
        stop_reason=choice.get("finish_reason"),
    )


def _build_gemini_contents(messages: List[Dict[str, Any]]) -> List[genai_types.Content]:
    contents = []
    for message in messages:
        role = "model" if message.get("role") == "assistant" else "user"
        contents.append(
            genai_types.Content(
                role=role,
                parts=[
                    genai_types.Part.from_text(
                        text=_coerce_message_content(message.get("content", ""))
                    )
                ],
            )
        )
    return contents


def _gemini_finish_reason(response: Any) -> Optional[str]:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return None
    finish_reason = getattr(candidates[0], "finish_reason", None)
    value = getattr(finish_reason, "value", finish_reason)
    normalized = str(value or "").upper()
    if "MAX_TOKENS" in normalized:
        return "max_tokens"
    if normalized:
        return "stop"
    return None


def _normalize_gemini_response(response: Any, configured_model: str) -> 'LLMResponse':
    text_blocks = []
    thinking_blocks = []
    candidates = getattr(response, "candidates", None) or []
    parts = []
    if candidates:
        content = getattr(candidates[0], "content", None)
        parts = getattr(content, "parts", None) or []

    for part in parts:
        text = getattr(part, "text", None)
        if not text:
            continue
        if getattr(part, "thought", False):
            thinking_blocks.append(text)
        else:
            text_blocks.append(text)

    usage_metadata = getattr(response, "usage_metadata", None)
    usage = {
        "input_tokens": int(getattr(usage_metadata, "prompt_token_count", 0) or 0),
        "output_tokens": int(getattr(usage_metadata, "candidates_token_count", 0) or 0),
        "thinking_tokens": int(getattr(usage_metadata, "thoughts_token_count", 0) or 0),
    }
    model = getattr(response, "model_version", None) or configured_model
    return LLMResponse(
        content="\n".join(text_blocks),
        thinking="\n\n".join(thinking_blocks) if thinking_blocks else None,
        usage=usage,
        model=model,
        stop_reason=_gemini_finish_reason(response),
        thinking_type="adaptive",
        thinking_block_count=len(thinking_blocks),
    )


def _content_char_count(content: Any) -> int:
    """Estimate request content size without logging the raw content."""
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content)
    return len(json.dumps(content, ensure_ascii=False, default=str))


def _messages_char_count(messages: List[Dict[str, Any]]) -> int:
    return sum(_content_char_count(message.get("content")) for message in messages)


def _uses_adaptive_thinking(model: str) -> bool:
    """True if model requires adaptive thinking (Opus 4.8 and later).

    Opus 4.8 removed manual thinking (`type: enabled` + budget_tokens)
    and sampling parameters. Opus 4.6 and earlier still accept manual thinking,
    so we keep the legacy path for them. Regex is permissive to handle the
    alias space: claude-opus-4-8, claude-4.8-opus, claude-opus-4-8-20260416,
    claude-4.6-opus-aws, etc.
    """
    normalized = model.lower()
    # Adaptive thinking is an Anthropic Opus capability, not a generic model
    # version rule. Without this guard, z-ai/glm-5.2 was misclassified solely
    # because 5.2 is numerically greater than 4.7.
    if "claude" not in normalized or "opus" not in normalized:
        return False
    match = re.search(r'(\d+)[-.](\d+)', normalized)
    if not match:
        return False
    major, minor = int(match.group(1)), int(match.group(2))
    return major > 4 or (major == 4 and minor >= 7)


# Default model max token limit (can be overridden via config or constructor)
DEFAULT_MODEL_MAX_TOKENS = 128000


@dataclass
class LLMResponse:
    """Structured response from LLM including thinking."""
    content: str
    thinking: Optional[str]
    usage: Dict[str, int]
    model: str
    stop_reason: Optional[str] = None  # Detect truncation via "max_tokens"
    thinking_type: Optional[str] = None
    adaptive_effort: Optional[str] = None
    analysis_profile: Optional[str] = None
    thinking_block_count: int = 0


class BearerAuth(httpx.Auth):
    """Custom httpx auth handler for Bearer token authentication."""

    def __init__(self, token: str):
        self.token = token

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request


class ApiKeyAuth(httpx.Auth):
    """Custom httpx auth handler for Anthropic x-api-key authentication."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def auth_flow(self, request: httpx.Request):
        request.headers["x-api-key"] = self.api_key
        yield request


class AnthropicClient:
    """
    Native Anthropic client with mode-based auth and adaptive/manual thinking support.

    This client wraps the Anthropic SDK to work with either:
    - Direct Anthropic API (x-api-key header authentication)
    - OpenAI-compatible proxies (Bearer token authentication)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 600.0,
        mode: str = "anthropic",
        max_output_tokens: Optional[int] = None,
        requests_per_minute: Optional[int] = None,
        tokens_per_minute: Optional[int] = None,
        requests_per_day: Optional[int] = None,
    ):
        """
        Initialize the Anthropic client.

        Args:
            api_key: API key. Defaults to ANTHROPIC_API_KEY env var.
            base_url: API base URL. Defaults to ANTHROPIC_API_BASE env var.
            model: Model name. Defaults to ANTHROPIC_MODEL env var.
            timeout: Request timeout in seconds.
            mode: API mode - 'anthropic' for direct API (x-api-key),
                  'openai-compatible' for proxies (Bearer token).
            max_output_tokens: Maximum output tokens the model/proxy supports.
                             Defaults to DEFAULT_MODEL_MAX_TOKENS (128000).
        """
        default_api_key_env = (
            'OPENROUTER_API_KEY' if mode == "openrouter"
            else 'GEMINI_API_KEY' if mode == "gemini"
            else 'ANTHROPIC_API_KEY'
        )
        default_base_url = (
            OPENROUTER_DEFAULT_BASE_URL if mode == "openrouter"
            else GEMINI_DEFAULT_BASE_URL if mode == "gemini"
            else None
        )
        self.api_key = api_key or os.environ.get(default_api_key_env)
        if mode == "gemini" and not self.api_key:
            self.api_key = os.environ.get("GOOGLE_API_KEY")
        self.base_url = base_url or os.environ.get('ANTHROPIC_API_BASE') or default_base_url
        self.model = model or os.environ.get('ANTHROPIC_MODEL', 'claude-4.8-opus-aws')
        self.timeout = _env_float("LLM_TIMEOUT_SECONDS", timeout, minimum=1.0)
        self.mode = mode
        self.max_output_tokens = max_output_tokens or DEFAULT_MODEL_MAX_TOKENS
        self.adaptive_max_tokens = min(
            _env_int("LLM_ADAPTIVE_MAX_TOKENS", DEFAULT_ADAPTIVE_MAX_TOKENS, minimum=1024),
            self.max_output_tokens,
        )
        self.trust_env_proxy = _env_bool("LLM_TRUST_ENV_PROXY", False)
        self.max_retries = _env_int("LLM_MAX_RETRIES", 1, minimum=0)
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.requests_per_day = requests_per_day
        self._rate_limiter = _get_rate_limiter(
            self.mode,
            self.base_url or "",
            self.model,
            self.requests_per_minute,
            self.tokens_per_minute,
            self.requests_per_day,
        )

        if not self.api_key:
            raise ValueError(f"{default_api_key_env} environment variable or api_key parameter required")
        if not self.base_url:
            raise ValueError("base_url parameter required")

        # Select auth based on mode
        if self.mode == "anthropic":
            auth = ApiKeyAuth(self.api_key)
        elif self.mode in {"openai-compatible", "openrouter"}:
            auth = BearerAuth(self.api_key)
        elif self.mode == "gemini":
            auth = None
        else:
            raise ValueError(
                f"Unknown mode: {self.mode}. Expected anthropic, openai-compatible, "
                "openrouter, or gemini."
            )

        self._http_client = None
        if not _uses_gemini(self.mode):
            self._http_client = httpx.Client(
                auth=auth,
                timeout=httpx.Timeout(self.timeout),
                trust_env=self.trust_env_proxy
            )

        self._client = None
        self._gemini_client = None
        if _uses_gemini(self.mode):
            self._gemini_client = genai.Client(
                api_key=self.api_key,
                http_options=genai_types.HttpOptions(timeout=int(self.timeout * 1000)),
            )
        elif not _uses_openrouter(self.mode):
            self._client = anthropic.Anthropic(
                base_url=self.base_url,
                api_key=self.api_key,  # SDK sends this as x-api-key header
                http_client=self._http_client,
                max_retries=self.max_retries,
            )

        logger.info(
            f"AnthropicClient initialized with mode={self.mode}, model={self.model}, "
            f"base_url={self.base_url}, timeout={self.timeout}s, sdk_max_retries={self.max_retries}, "
            f"trust_env_proxy={self.trust_env_proxy}"
        )

    @classmethod
    def from_config(cls, config: 'LLMProviderConfig') -> 'AnthropicClient':
        """
        Create client from LLMProviderConfig.

        Args:
            config: LLMProviderConfig with api_key, base_url, model, timeout, mode

        Returns:
            Configured AnthropicClient instance
        """
        return cls(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            timeout=config.timeout,
            mode=config.mode,
            max_output_tokens=getattr(config, 'max_output_tokens', DEFAULT_MODEL_MAX_TOKENS),
            requests_per_minute=getattr(config, 'requests_per_minute', None),
            tokens_per_minute=getattr(config, 'tokens_per_minute', None),
            requests_per_day=getattr(config, 'requests_per_day', None),
        )

    def _create_gemini_completion(
        self,
        *,
        messages: List[Dict[str, Any]],
        system: Optional[str],
        max_tokens: int,
        temperature: Optional[float],
        thinking_level: str,
    ) -> LLMResponse:
        estimated_input_tokens = max(
            1,
            (_messages_char_count(messages) + _content_char_count(system) + 3) // 4,
        )
        self._rate_limiter.acquire(estimated_input_tokens)
        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=temperature,
            thinking_config=genai_types.ThinkingConfig(
                thinking_level=thinking_level,
                include_thoughts=True,
            ),
        )
        response = self._gemini_client.models.generate_content(
            model=self.model,
            contents=_build_gemini_contents(messages),
            config=config,
        )
        return _normalize_gemini_response(response, self.model)

    def _create_openrouter_completion(
        self,
        *,
        messages: List[Dict[str, Any]],
        system: Optional[str],
        max_tokens: int,
        temperature: Optional[float],
        reasoning: Optional[Dict[str, Any]] = None,
    ) -> ProviderResponse:
        payload = {
            "model": self.model,
            "messages": _build_openrouter_messages(messages, system),
            "max_tokens": max_tokens,
            **({"temperature": temperature} if temperature is not None else {}),
        }
        provider_preferences = _openrouter_provider_preferences(self.model)
        if provider_preferences:
            payload["provider"] = provider_preferences
        if reasoning:
            payload["reasoning"] = reasoning
        response = self._http_client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        return _normalize_openrouter_response(response.json())

    def call(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 1.0
    ) -> LLMResponse:
        """
        Make a plain API call.

        Opus 4.8+ still receives adaptive thinking request metadata here; this
        method only means the caller does not need returned thinking text.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            system: Optional system prompt.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature (ignored on Opus 4.8+).

        Returns:
            LLMResponse with content and no returned thinking text.
        """
        if _uses_gemini(self.mode):
            response = self._create_gemini_completion(
                messages=messages,
                system=system,
                max_tokens=min(max_tokens, self.max_output_tokens),
                temperature=temperature,
                thinking_level="minimal",
            )
            response.thinking = None
            response.analysis_profile = "plain"
            response.adaptive_effort = "minimal"
            return response

        if _uses_openrouter(self.mode):
            response = self._create_openrouter_completion(
                messages=messages,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = "".join(block.text or "" for block in response.content)
            return LLMResponse(
                content=content,
                thinking=None,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                model=response.model or self.model,
                stop_reason=response.stop_reason,
                thinking_type=None,
                adaptive_effort=None,
                analysis_profile="plain",
                thinking_block_count=0,
            )

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages
        }

        use_adaptive = _uses_adaptive_thinking(self.model)
        if use_adaptive:
            kwargs["thinking"] = {"type": "adaptive", "display": "summarized"}
            kwargs["extra_body"] = {"output_config": {"effort": "high"}}
        else:
            kwargs["temperature"] = temperature

        if system:
            kwargs["system"] = system

        response = self._client.messages.create(**kwargs)

        # Extract text content
        content = ""
        thinking_block_count = 0
        for block in response.content:
            if getattr(block, "type", None) == "thinking":
                thinking_block_count += 1
            if hasattr(block, 'text'):
                content += block.text

        return LLMResponse(
            content=content,
            thinking=None,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            },
            model=response.model,
            thinking_type="adaptive" if use_adaptive else None,
            adaptive_effort="high" if use_adaptive else None,
            analysis_profile="plain" if use_adaptive else None,
            thinking_block_count=thinking_block_count
        )

    def call_with_thinking(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        budget_tokens: int = ThinkingLevel.STANDARD,
        profile: Optional[int] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        full_output_budget: bool = False
    ) -> LLMResponse:
        """
        Make an API call with adaptive or manual thinking enabled.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            system: Optional system prompt.
            budget_tokens: Backward-compatible manual thinking budget/profile.
            profile: Analysis profile (use ThinkingLevel enum). Opus 4.8+
                     maps this to adaptive effort; older models use it as a
                     manual thinking budget.
            max_tokens: Maximum response output tokens. On adaptive models this
                       defaults to LLM_ADAPTIVE_MAX_TOKENS; older manual
                       thinking models default to profile plus an output buffer.
            temperature: Must be 1.0 for thinking mode.
            full_output_budget: Raise the default ceiling to the full model
                       output limit so max-effort thinking cannot clip the
                       output. Effort is never reduced.

        Returns:
            LLMResponse with content and thinking blocks.
        """
        requested_profile = profile if profile is not None else budget_tokens
        profile_name = THINKING_LEVEL_NAMES.get(requested_profile, str(requested_profile))

        if _uses_gemini(self.mode):
            thinking_level = GEMINI_PROFILE_TO_THINKING.get(requested_profile, "medium")
            if max_tokens is None:
                max_tokens = self.max_output_tokens
            response = self._create_gemini_completion(
                messages=messages,
                system=system,
                max_tokens=min(max_tokens, self.max_output_tokens),
                temperature=temperature,
                thinking_level=thinking_level,
            )
            response.analysis_profile = profile_name
            response.adaptive_effort = thinking_level
            return response

        if _uses_openrouter(self.mode):
            if max_tokens is None:
                max_tokens = (
                    self.max_output_tokens
                    if full_output_budget
                    else min(self.max_output_tokens, 16384)
                )
            effort = BUDGET_TO_EFFORT.get(requested_profile, "high")
            response = self._create_openrouter_completion(
                messages=messages,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                reasoning={"effort": effort, "exclude": False},
            )
            content = "".join(block.text or "" for block in response.content)
            thinking = "\n\n".join(
                block.thinking or "" for block in response.content if block.type == "thinking"
            ) or None
            return LLMResponse(
                content=content,
                thinking=thinking,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                model=response.model or self.model,
                stop_reason=response.stop_reason,
                thinking_type="adaptive",
                adaptive_effort=effort,
                analysis_profile=profile_name,
                thinking_block_count=1 if thinking else 0,
            )

        use_adaptive = _uses_adaptive_thinking(self.model)

        if use_adaptive:
            effort = BUDGET_TO_EFFORT.get(requested_profile, "high")
            if max_tokens is None:
                max_tokens = self.max_output_tokens if full_output_budget else self.adaptive_max_tokens
            manual_budget_tokens = None
        else:
            effort = None
            manual_budget_tokens = int(requested_profile)
            # Use larger buffer (49152) to avoid JSON truncation in dense batches
            # on older manual-thinking models.
            if max_tokens is None:
                max_tokens = manual_budget_tokens + 49152
            elif max_tokens <= manual_budget_tokens:
                max_tokens = manual_budget_tokens + 16384

        # Cap at model/proxy limit
        if max_tokens > self.max_output_tokens:
            logger.debug(f"Capping max_tokens from {max_tokens} to {self.max_output_tokens} (model limit)")
            max_tokens = self.max_output_tokens

        # If capping pushed max_tokens below the manual budget, reduce it too
        # (only meaningful on the manual-thinking path)
        if not use_adaptive and max_tokens <= manual_budget_tokens:
            manual_budget_tokens = max(max_tokens - 8192, max_tokens // 2)
            logger.info(
                f"Reduced manual thinking budget to {manual_budget_tokens} "
                f"to fit within {self.max_output_tokens} token limit"
            )

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages
        }

        if use_adaptive:
            # Opus 4.8+ path: adaptive thinking with effort. Manual thinking
            # and non-default sampling parameters return 400 on these models.
            # `thinking` is a typed SDK param in anthropic>=0.75.0; keep it
            # top-level so Opus 4.8 cannot silently run with thinking disabled.
            # `output_config` is not typed in this SDK yet, so effort goes
            # through extra_body as a passthrough.
            kwargs["thinking"] = {"type": "adaptive", "display": "summarized"}
            kwargs["extra_body"] = {"output_config": {"effort": effort}}
            logger.debug(
                f"Calling with adaptive thinking: analysis_profile={profile_name}, "
                f"effort={effort}, max_tokens={max_tokens}"
            )
        else:
            # Opus 4.6 and earlier: manual thinking with an explicit token budget.
            if temperature != 1.0:
                logger.warning("Temperature must be 1.0 for thinking mode, overriding")
                temperature = 1.0
            kwargs["temperature"] = temperature
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": manual_budget_tokens}
            logger.debug(
                f"Calling with manual thinking: profile={profile_name}, "
                f"budget={manual_budget_tokens}, max_tokens={max_tokens}"
            )

        if system:
            kwargs["system"] = system

        response = self._client.messages.create(**kwargs)

        # Log stop_reason for diagnostics (helps debug proxy behavior)
        logger.debug(f"Response stop_reason: {response.stop_reason}, output_tokens: {response.usage.output_tokens}")

        # Check for truncation
        if response.stop_reason == "max_tokens":
            logger.warning(f"Response truncated at max_tokens ({max_tokens}). Output may be incomplete.")

        # Extract thinking and text content
        thinking_blocks = []
        text_blocks = []

        for block in response.content:
            if block.type == "thinking":
                thinking_blocks.append(block.thinking)
            elif block.type == "text":
                text_blocks.append(block.text)

        # On the manual path, absent thinking blocks historically signaled a
        # proxy misconfiguration (e.g. LiteLLM routing through the wrong
        # endpoint). On the adaptive path, thinking blocks are often absent
        # legitimately — the proxy may strip them, or the model may skip
        # thinking for simple prompts — so we skip this guard there.
        if not use_adaptive and manual_budget_tokens > 0 and not thinking_blocks:
            error_msg = (
                f"Extended thinking requested (budget_tokens={manual_budget_tokens}) but no thinking "
                f"blocks returned. This is required for quality analysis.\n\n"
            )
            if self.mode == "openai-compatible":
                error_msg += (
                    f"You are using openai-compatible mode with base_url={self.base_url}. "
                    f"If using LiteLLM, ensure you're using the Anthropic passthrough endpoint "
                    f"(e.g., http://proxy:4000/anthropic) not the OpenAI chat/completions endpoint. "
                    f"See: https://docs.litellm.ai/docs/pass_through/anthropic_completion"
                )
            else:
                error_msg += (
                    f"Check that the model '{self.model}' supports manual thinking "
                    f"and that the API endpoint is responding correctly."
                )
            raise RuntimeError(error_msg)

        return LLMResponse(
            content="\n".join(text_blocks),
            thinking="\n\n".join(thinking_blocks) if thinking_blocks else None,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            },
            model=response.model,
            stop_reason=response.stop_reason,
            thinking_type="adaptive" if use_adaptive else "enabled",
            adaptive_effort=effort,
            analysis_profile=profile_name,
            thinking_block_count=len(thinking_blocks)
        )

    def call_json(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        budget_tokens: Optional[int] = None,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Make an API call expecting JSON response.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            system: Optional system prompt.
            budget_tokens: If provided, enables thinking with this budget.
            max_tokens: Maximum tokens in response.

        Returns:
            Parsed JSON dict from response.
        """
        if budget_tokens:
            response = self.call_with_thinking(
                messages=messages,
                system=system,
                budget_tokens=budget_tokens,
                max_tokens=max_tokens
            )
        else:
            response = self.call(
                messages=messages,
                system=system,
                max_tokens=max_tokens
            )

        # Try to parse JSON from response
        content = response.content.strip()

        # Handle markdown code blocks
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        try:
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response content: {response.content[:500]}")
            raise ValueError(f"Invalid JSON in response: {e}")

    def close(self):
        """Close the HTTP client."""
        if self._http_client is not None:
            self._http_client.close()
        if self._gemini_client is not None and hasattr(self._gemini_client, "close"):
            self._gemini_client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Async version for parallel operations
class AsyncAnthropicClient:
    """
    Async version of AnthropicClient for parallel operations.

    Supports mode-based authentication:
    - anthropic: Direct Anthropic API with x-api-key header
    - openai-compatible: OpenAI-compatible proxies with Bearer token
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 600.0,
        mode: str = "anthropic",
        max_output_tokens: Optional[int] = None,
        provider_id: Optional[str] = None,
        max_concurrent_requests: Optional[int] = None,
        max_retries: Optional[int] = None,
        requests_per_minute: Optional[int] = None,
        tokens_per_minute: Optional[int] = None,
        requests_per_day: Optional[int] = None,
        route_profiles: Optional[List[str]] = None,
        caller_patterns: Optional[List[str]] = None,
        fallback_route_id: Optional[str] = None,
        allow_cross_route_fallback: bool = True,
        route_priority: int = 0,
    ):
        default_api_key_env = (
            'OPENROUTER_API_KEY' if mode == "openrouter"
            else 'GEMINI_API_KEY' if mode == "gemini"
            else 'ANTHROPIC_API_KEY'
        )
        default_base_url = (
            OPENROUTER_DEFAULT_BASE_URL if mode == "openrouter"
            else GEMINI_DEFAULT_BASE_URL if mode == "gemini"
            else None
        )
        self.api_key = api_key or os.environ.get(default_api_key_env)
        if mode == "gemini" and not self.api_key:
            self.api_key = os.environ.get("GOOGLE_API_KEY")
        self.base_url = base_url or os.environ.get('ANTHROPIC_API_BASE') or default_base_url
        self.model = model or os.environ.get('ANTHROPIC_MODEL', 'claude-4.8-opus-aws')
        self.provider_id = provider_id or self.model
        self.timeout = _env_float("LLM_TIMEOUT_SECONDS", timeout, minimum=1.0)
        self.mode = mode
        self.max_output_tokens = max_output_tokens or DEFAULT_MODEL_MAX_TOKENS
        self.adaptive_max_tokens = min(
            _env_int("LLM_ADAPTIVE_MAX_TOKENS", DEFAULT_ADAPTIVE_MAX_TOKENS, minimum=1024),
            self.max_output_tokens,
        )
        self.trust_env_proxy = _env_bool("LLM_TRUST_ENV_PROXY", False)
        self.max_concurrent_requests = (
            max_concurrent_requests
            if max_concurrent_requests is not None
            else _env_int("LLM_MAX_CONCURRENT_REQUESTS", 8)
        )
        self.max_retries = (
            max_retries
            if max_retries is not None
            else _env_int("LLM_MAX_RETRIES", 1, minimum=0)
        )
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.requests_per_day = requests_per_day
        self.route_profiles = set(route_profiles or [])
        self.caller_patterns = list(caller_patterns or [])
        self.fallback_route_id = fallback_route_id
        self.allow_cross_route_fallback = allow_cross_route_fallback
        self.route_priority = route_priority
        self._rate_limiter = _get_rate_limiter(
            self.mode,
            self.base_url or "",
            self.model,
            self.requests_per_minute,
            self.tokens_per_minute,
            self.requests_per_day,
        )
        self.log_requests = _env_bool("LLM_LOG_REQUESTS", True)
        self.heartbeat_seconds = _env_float("LLM_HEARTBEAT_SECONDS", 60.0, minimum=0.0)
        self.metrics_path = os.environ.get("LLM_METRICS_PATH", "").strip()
        self._request_semaphore = (
            asyncio.Semaphore(self.max_concurrent_requests)
            if self.max_concurrent_requests > 0
            else None
        )
        self._request_lock = asyncio.Lock()
        self._metrics_lock = asyncio.Lock()
        self._request_sequence = 0
        self._active_requests = 0
        self._queued_requests = 0

        if not self.api_key:
            raise ValueError(f"{default_api_key_env} environment variable or api_key parameter required")
        if not self.base_url:
            raise ValueError("base_url parameter required")

        # Select auth based on mode
        if self.mode == "anthropic":
            auth = ApiKeyAuth(self.api_key)
        elif self.mode in {"openai-compatible", "openrouter"}:
            auth = BearerAuth(self.api_key)
        elif self.mode == "gemini":
            auth = None
        else:
            raise ValueError(
                f"Unknown mode: {self.mode}. Expected anthropic, openai-compatible, "
                "openrouter, or gemini."
            )

        self._http_client = None
        if not _uses_gemini(self.mode):
            self._http_client = httpx.AsyncClient(
                auth=auth,
                timeout=httpx.Timeout(self.timeout),
                trust_env=self.trust_env_proxy
            )

        self._client = None
        self._gemini_client = None
        self._openai_client = None
        if _uses_gemini(self.mode):
            self._gemini_client = genai.Client(
                api_key=self.api_key,
                http_options=genai_types.HttpOptions(timeout=int(self.timeout * 1000)),
            )
        elif self.mode == "openai-compatible":
            self._openai_client = openai.AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                http_client=self._http_client,
                max_retries=self.max_retries,
            )
        elif not _uses_openrouter(self.mode):
            self._client = anthropic.AsyncAnthropic(
                base_url=self.base_url,
                api_key=self.api_key,  # SDK sends this as x-api-key header
                http_client=self._http_client,
                max_retries=self.max_retries,
            )

        logger.info(
            f"AsyncAnthropicClient initialized with provider_id={self.provider_id}, "
            f"mode={self.mode}, model={self.model}, "
            f"timeout={self.timeout}s, sdk_max_retries={self.max_retries}, "
            f"heartbeat_seconds={self.heartbeat_seconds}, "
            f"max_concurrent_requests={self.max_concurrent_requests or 'unlimited'}, "
            f"rpm={self.requests_per_minute or 'unlimited'}, "
            f"tpm={self.tokens_per_minute or 'unlimited'}, "
            f"rpd={self.requests_per_day or 'unlimited'}, "
            f"trust_env_proxy={self.trust_env_proxy}, request_logging={self.log_requests}, "
            f"metrics_path={self.metrics_path or 'disabled'}"
        )

    def _format_request_context(self, request_context: Optional[Dict[str, Any]]) -> str:
        context = request_context or {}
        parts = [
            f"caller={context.get('caller', 'unknown')}",
            f"kind={context.get('kind', 'message')}",
            f"provider_id={context.get('provider_id', self.provider_id)}",
            f"provider_model={context.get('provider_model', self.model)}",
        ]
        for key in (
            "thinking_type",
            "analysis_profile",
            "adaptive_effort",
            "manual_budget_tokens",
            "response_max_tokens",
            "thinking_blocks",
            "attempt",
            "same_provider_retry",
            "fallback_from",
            "retry_reason",
            "message_count",
            "message_chars",
            "system_chars",
        ):
            value = context.get(key)
            if value is not None:
                parts.append(f"{key}={value}")
        return " ".join(parts)

    async def _register_queued_request(self, request_context: Optional[Dict[str, Any]]) -> Tuple[int, int, int]:
        async with self._request_lock:
            self._request_sequence += 1
            request_id = self._request_sequence
            self._queued_requests += 1
            active = self._active_requests
            queued = self._queued_requests
        logger.debug(
            f"LLM queued #{request_id} {self._format_request_context(request_context)} "
            f"active={active} queued={queued} cap={self.max_concurrent_requests or 'unlimited'}"
        )
        return request_id, active, queued

    async def _mark_request_started(
        self,
        request_id: int,
        request_context: Optional[Dict[str, Any]],
        queued_at: float,
    ) -> float:
        async with self._request_lock:
            self._queued_requests = max(0, self._queued_requests - 1)
            self._active_requests += 1
            active = self._active_requests
            queued = self._queued_requests
        wait_seconds = time.time() - queued_at
        logger.debug(
            f"LLM start #{request_id} {self._format_request_context(request_context)} "
            f"active={active} queued={queued} waited={wait_seconds:.1f}s"
        )
        return wait_seconds

    async def _mark_request_finished(
        self,
        request_id: int,
        request_context: Optional[Dict[str, Any]],
        started_at: float,
        wait_seconds: float,
        response: Optional[Any] = None,
        error: Optional[BaseException] = None,
    ) -> None:
        async with self._request_lock:
            self._active_requests = max(0, self._active_requests - 1)
            active = self._active_requests
            queued = self._queued_requests

        duration = time.time() - started_at
        if error is not None:
            logger.info(
                f"LLM failed #{request_id} {self._format_request_context(request_context)} "
                f"active={active} queued={queued} duration={duration:.1f}s "
                f"error={type(error).__name__}: {error}"
            )
            await self._write_metric({
                "event": "failed",
                "request_id": request_id,
                "context": request_context or {},
                "wait_seconds": round(wait_seconds, 3),
                "duration_seconds": round(duration, 3),
                "active_after": active,
                "queued_after": queued,
                "error_type": type(error).__name__,
                "error": str(error),
            })
            return

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        stop_reason = getattr(response, "stop_reason", None)
        content_blocks = getattr(response, "content", []) or []
        thinking_block_count = sum(
            1 for block in content_blocks if getattr(block, "type", None) == "thinking"
        )
        text_block_count = sum(
            1 for block in content_blocks if getattr(block, "type", None) == "text"
        )
        logger.info(
            f"LLM done #{request_id} {self._format_request_context(request_context)} "
            f"active={active} queued={queued} duration={duration:.1f}s "
            f"stop_reason={stop_reason} input_tokens={input_tokens} output_tokens={output_tokens} "
            f"thinking_blocks={thinking_block_count} text_blocks={text_block_count}"
        )
        await self._write_metric({
            "event": "done",
            "request_id": request_id,
            "context": request_context or {},
            "wait_seconds": round(wait_seconds, 3),
            "duration_seconds": round(duration, 3),
            "active_after": active,
            "queued_after": queued,
            "stop_reason": stop_reason,
            "thinking_blocks": thinking_block_count,
            "text_blocks": text_block_count,
            "response_model": getattr(response, "model", None),
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", None),
                "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", None),
            },
        })

    async def _cancel_queued_request(
        self,
        request_id: int,
        request_context: Optional[Dict[str, Any]],
        queued_at: float,
        error: BaseException,
    ) -> None:
        async with self._request_lock:
            self._queued_requests = max(0, self._queued_requests - 1)
            active = self._active_requests
            queued = self._queued_requests
        logger.info(
            f"LLM cancelled before start #{request_id} {self._format_request_context(request_context)} "
            f"active={active} queued={queued} waited={time.time() - queued_at:.1f}s "
            f"error={type(error).__name__}: {error}"
        )
        await self._write_metric({
            "event": "cancelled_before_start",
            "request_id": request_id,
            "context": request_context or {},
            "wait_seconds": round(time.time() - queued_at, 3),
            "active_after": active,
            "queued_after": queued,
            "error_type": type(error).__name__,
            "error": str(error),
        })

    def _start_heartbeat(
        self,
        request_id: int,
        request_context: Optional[Dict[str, Any]],
        started_at: float,
    ) -> Optional[asyncio.Task]:
        if self.heartbeat_seconds <= 0:
            return None
        return asyncio.create_task(
            self._log_request_heartbeat(request_id, request_context, started_at)
        )

    async def _log_request_heartbeat(
        self,
        request_id: int,
        request_context: Optional[Dict[str, Any]],
        started_at: float,
    ) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            async with self._request_lock:
                active = self._active_requests
                queued = self._queued_requests
            duration = time.time() - started_at
            logger.info(
                f"LLM running #{request_id} {self._format_request_context(request_context)} "
                f"active={active} queued={queued} duration={duration:.1f}s"
            )
            await self._write_metric({
                "event": "heartbeat",
                "request_id": request_id,
                "context": request_context or {},
                "duration_seconds": round(duration, 3),
                "active": active,
                "queued": queued,
            })

    async def _write_metric(self, record: Dict[str, Any]) -> None:
        if not self.metrics_path:
            return

        base_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider_id": self.provider_id,
            "provider_model": self.model,
            "configured_model": self.model,
            "mode": self.mode,
            "timeout_seconds": self.timeout,
            "sdk_max_retries": self.max_retries,
            "max_concurrent_requests": self.max_concurrent_requests or None,
            "trust_env_proxy": self.trust_env_proxy,
        }
        base_record.update(record)

        async with self._metrics_lock:
            await asyncio.to_thread(self._append_metric_record, base_record)

    def _append_metric_record(self, record: Dict[str, Any]) -> None:
        metrics_file = Path(self.metrics_path)
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        with metrics_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    async def _create_openrouter_completion(
        self,
        request_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> ProviderResponse:
        payload = {
            "model": kwargs["model"],
            "messages": _build_openrouter_messages(kwargs["messages"], kwargs.get("system")),
            "max_tokens": kwargs["max_tokens"],
        }
        if "temperature" in kwargs and kwargs["temperature"] is not None:
            payload["temperature"] = kwargs["temperature"]
        if "chat_template_kwargs" in kwargs:
            payload["chat_template_kwargs"] = kwargs["chat_template_kwargs"]
        elif kwargs.get("is_thinking_call", False):
            payload["chat_template_kwargs"] = {"thinking": True}
        if "reasoning" in kwargs:
            payload["reasoning"] = kwargs["reasoning"]
        provider_preferences = _openrouter_provider_preferences(kwargs["model"])
        if provider_preferences:
            payload["provider"] = provider_preferences

        if not self.log_requests:
            response = await self._http_client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            return _normalize_openrouter_response(response.json())

        queued_at = time.time()
        request_id, _, _ = await self._register_queued_request(request_context)
        acquired = False
        started_at = queued_at
        heartbeat_task = None

        try:
            if self._request_semaphore is not None:
                await self._request_semaphore.acquire()
            acquired = True
            started_at = time.time()
            wait_seconds = await self._mark_request_started(request_id, request_context, queued_at)
            heartbeat_task = self._start_heartbeat(request_id, request_context, started_at)
            raw_response = await self._http_client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
            raw_response.raise_for_status()
            response = _normalize_openrouter_response(raw_response.json())
            await self._mark_request_finished(
                request_id,
                request_context,
                started_at,
                wait_seconds,
                response=response,
            )
            return response
        except Exception as error:
            if acquired:
                await self._mark_request_finished(
                    request_id,
                    request_context,
                    started_at,
                    wait_seconds if 'wait_seconds' in locals() else 0.0,
                    error=error,
                )
            else:
                await self._cancel_queued_request(request_id, request_context, queued_at, error)
            raise
        finally:
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                with suppress(asyncio.CancelledError):
                    await heartbeat_task
            if acquired and self._request_semaphore is not None:
                self._request_semaphore.release()

    async def _create_message(self, request_context: Optional[Dict[str, Any]] = None, **kwargs):
        """Create a message under the optional global async LLM concurrency cap."""
        if _uses_openrouter(self.mode):
            return await self._create_openrouter_completion(request_context=request_context, **kwargs)
        if self.mode == "openai-compatible":
            return await self._create_openai_completion(request_context=request_context, **kwargs)
        if not self.log_requests:
            if self._request_semaphore is None:
                return await self._client.messages.create(**kwargs)
            async with self._request_semaphore:
                return await self._client.messages.create(**kwargs)

        queued_at = time.time()
        request_id, _, _ = await self._register_queued_request(request_context)
        acquired = False
        started_at = queued_at
        heartbeat_task = None

        try:
            if self._request_semaphore is not None:
                await self._request_semaphore.acquire()
            acquired = True
            started_at = time.time()
            wait_seconds = await self._mark_request_started(request_id, request_context, queued_at)
            heartbeat_task = self._start_heartbeat(request_id, request_context, started_at)
            response = await self._client.messages.create(**kwargs)
            await self._mark_request_finished(
                request_id,
                request_context,
                started_at,
                wait_seconds,
                response=response,
            )
            return response
        except BaseException as error:
            if acquired:
                await self._mark_request_finished(
                    request_id,
                    request_context,
                    started_at,
                    wait_seconds if 'wait_seconds' in locals() else 0.0,
                    error=error,
                )
            else:
                await self._cancel_queued_request(request_id, request_context, queued_at, error)
            raise
        finally:
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                with suppress(asyncio.CancelledError):
                    await heartbeat_task
            if acquired and self._request_semaphore is not None:
                self._request_semaphore.release()

    async def _create_openai_completion(
        self,
        request_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> ProviderResponse:
        openai_messages = _build_openrouter_messages(kwargs["messages"], kwargs.get("system"))
        payload = {
            "model": kwargs["model"],
            "messages": openai_messages,
        }
        if "max_tokens" in kwargs:
            # NVIDIA's hosted NIM examples expose the legacy ``max_tokens``
            # field, while newer OpenAI-compatible providers use
            # ``max_completion_tokens``.
            token_field = (
                "max_tokens" if "nvidia.com" in self.base_url
                else "max_completion_tokens"
            )
            payload[token_field] = kwargs["max_tokens"]
        if "temperature" in kwargs and kwargs["temperature"] is not None:
            payload["temperature"] = kwargs["temperature"]
        if "extra_body" in kwargs:
            payload["extra_body"] = kwargs["extra_body"]
            
        # NVIDIA NIM provider-specific reasoning controls.  The generic
        # ``thinking`` argument is internal and is not part of Chat Completions.
        if "nvidia.com" in self.base_url and "deepseek" in kwargs["model"]:
            if "thinking" in kwargs and kwargs["thinking"].get("budget_tokens", 0) > 0:
                payload["extra_body"] = payload.get("extra_body", {})
                payload["extra_body"]["chat_template_kwargs"] = {"thinking": True}
        elif "nvidia.com" in self.base_url and "nemotron-3-nano" in kwargs["model"]:
            thinking_budget = kwargs.get("thinking", {}).get("budget_tokens", 0)
            payload["top_p"] = 1
            if thinking_budget > 0:
                payload["extra_body"] = payload.get("extra_body", {})
                # The hosted integrate.api.nvidia.com endpoint accepts
                # ``reasoning_budget``. ``max_thinking_tokens`` is exposed by
                # some self-hosted NIM deployments but is rejected by hosted NIM.
                payload["extra_body"]["reasoning_budget"] = thinking_budget
        elif "nvidia.com" in self.base_url and kwargs["model"] == "z-ai/glm-5.2":
            # Match the provider's recommended hosted-endpoint parameters.
            payload["top_p"] = 1
            payload["seed"] = 42
        
        if not self.log_requests:
            raw_response = await self._openai_client.chat.completions.create(**payload)
            choice = raw_response.choices[0]
            content = choice.message.content or ""
            thinking_text = None
            if choice.message.model_extra and ("reasoning_content" in choice.message.model_extra or "reasoning" in choice.message.model_extra):
                thinking_text = choice.message.model_extra.get("reasoning_content") or choice.message.model_extra.get("reasoning")
            elif "<think>" in content and "</think>" in content:
                start = content.find("<think>") + len("<think>")
                end = content.find("</think>")
                thinking_text = content[start:end].strip()
                content = content[end + len("</think>"):].strip()
                
            blocks = []
            if thinking_text:
                blocks.append(ResponseBlock(type="thinking", thinking=thinking_text))
            blocks.append(ResponseBlock(type="text", text=content))
            usage = ResponseUsage(
                input_tokens=raw_response.usage.prompt_tokens if raw_response.usage else 0,
                output_tokens=raw_response.usage.completion_tokens if raw_response.usage else 0,
            )
            return ProviderResponse(
                content=blocks,
                usage=usage,
                model=raw_response.model,
                stop_reason=choice.finish_reason,
            )

        queued_at = time.time()
        request_id, _, _ = await self._register_queued_request(request_context)
        acquired = False
        started_at = queued_at
        heartbeat_task = None

        try:
            if self._request_semaphore is not None:
                await self._request_semaphore.acquire()
            acquired = True
            started_at = time.time()
            wait_seconds = await self._mark_request_started(request_id, request_context, queued_at)
            heartbeat_task = self._start_heartbeat(request_id, request_context, started_at)
            
            raw_response = await self._openai_client.chat.completions.create(**payload)
            
            choice = raw_response.choices[0]
            content = choice.message.content or ""
            
            thinking_text = None
            if choice.message.model_extra and ("reasoning_content" in choice.message.model_extra or "reasoning" in choice.message.model_extra):
                thinking_text = choice.message.model_extra.get("reasoning_content") or choice.message.model_extra.get("reasoning")
            elif "<think>" in content and "</think>" in content:
                start = content.find("<think>") + len("<think>")
                end = content.find("</think>")
                thinking_text = content[start:end].strip()
                content = content[end + len("</think>"):].strip()
                
            blocks = []
            if thinking_text:
                blocks.append(ResponseBlock(type="thinking", thinking=thinking_text))
            blocks.append(ResponseBlock(type="text", text=content))
            
            usage = ResponseUsage(
                input_tokens=raw_response.usage.prompt_tokens if raw_response.usage else 0,
                output_tokens=raw_response.usage.completion_tokens if raw_response.usage else 0,
            )
            response = ProviderResponse(
                content=blocks,
                usage=usage,
                model=raw_response.model,
                stop_reason=choice.finish_reason,
            )
            
            await self._mark_request_finished(
                request_id,
                request_context,
                started_at,
                wait_seconds,
                response=response,
            )
            return response
        except BaseException as error:
            if acquired:
                await self._mark_request_finished(
                    request_id,
                    request_context,
                    started_at,
                    wait_seconds if 'wait_seconds' in locals() else 0.0,
                    error=error,
                )
            else:
                await self._cancel_queued_request(request_id, request_context, queued_at, error)
            raise
        finally:
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                with suppress(asyncio.CancelledError):
                    await heartbeat_task
            if acquired and self._request_semaphore is not None:
                self._request_semaphore.release()

    @classmethod
    def from_config(cls, config: 'LLMProviderConfig') -> 'AsyncAnthropicClient':
        """
        Create client from LLMProviderConfig.

        Args:
            config: LLMProviderConfig with api_key, base_url, model, timeout, mode

        Returns:
            Configured AsyncAnthropicClient instance
        """
        return cls(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            timeout=config.timeout,
            mode=config.mode,
            max_output_tokens=getattr(config, 'max_output_tokens', DEFAULT_MODEL_MAX_TOKENS),
            requests_per_minute=getattr(config, 'requests_per_minute', None),
            tokens_per_minute=getattr(config, 'tokens_per_minute', None),
            requests_per_day=getattr(config, 'requests_per_day', None),
        )

    @classmethod
    def from_route_config(
        cls,
        config: 'ResolvedLLMRouteConfig',
        max_retries: Optional[int] = None
    ) -> 'AsyncAnthropicClient':
        """Create a concrete async client from a resolved route config."""
        return cls(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            timeout=config.timeout,
            mode=config.mode,
            max_output_tokens=config.max_output_tokens,
            provider_id=config.id,
            max_concurrent_requests=config.max_concurrent_requests,
            max_retries=max_retries,
            requests_per_minute=config.requests_per_minute,
            tokens_per_minute=config.tokens_per_minute,
            requests_per_day=config.requests_per_day,
            route_profiles=config.profiles,
            caller_patterns=config.caller_patterns,
            fallback_route_id=config.fallback_route_id,
            allow_cross_route_fallback=config.allow_cross_route_fallback,
            route_priority=config.priority,
        )

    async def _create_gemini_completion(
        self,
        *,
        messages: List[Dict[str, Any]],
        system: Optional[str],
        max_tokens: int,
        temperature: Optional[float],
        thinking_level: str,
        request_context: Dict[str, Any],
    ) -> LLMResponse:
        estimated_input_tokens = max(
            1,
            (_messages_char_count(messages) + _content_char_count(system) + 3) // 4,
        )
        await asyncio.to_thread(self._rate_limiter.acquire, estimated_input_tokens)

        async def invoke():
            config_kwargs = {
                "system_instruction": system,
                "max_output_tokens": max_tokens,
                "thinking_config": genai_types.ThinkingConfig(
                    thinking_level=thinking_level,
                    include_thoughts=True,
                ),
            }
            # Gemini 3.6+ deprecated sampling controls and may reject them.
            # Older Gemini models still accept temperature, so retain the
            # existing behavior only outside the new model family.
            if not re.match(r"^gemini-3\.(?:[6-9]|\d{2,})-", self.model):
                config_kwargs["temperature"] = temperature
            return await self._gemini_client.aio.models.generate_content(
                model=self.model,
                contents=_build_gemini_contents(messages),
                config=genai_types.GenerateContentConfig(**config_kwargs),
            )

        started_at = time.time()
        logger.info(
            "Gemini start %s estimated_input_tokens=%s",
            self._format_request_context(request_context),
            estimated_input_tokens,
        )
        try:
            if self._request_semaphore is None:
                raw_response = await invoke()
            else:
                async with self._request_semaphore:
                    raw_response = await invoke()
            response = _normalize_gemini_response(raw_response, self.model)
        except BaseException as error:
            duration = time.time() - started_at
            logger.info(
                "Gemini failed %s duration=%.1fs error=%s: %s",
                self._format_request_context(request_context),
                duration,
                type(error).__name__,
                error,
            )
            await self._write_metric({
                "event": "failed",
                "context": request_context,
                "duration_seconds": round(duration, 3),
                "error_type": type(error).__name__,
                "error": str(error),
            })
            raise
        duration = time.time() - started_at
        logger.info(
            "Gemini done %s duration=%.1fs input_tokens=%s output_tokens=%s "
            "thinking_tokens=%s stop_reason=%s",
            self._format_request_context(request_context),
            duration,
            response.usage.get("input_tokens", 0),
            response.usage.get("output_tokens", 0),
            response.usage.get("thinking_tokens", 0),
            response.stop_reason,
        )
        await self._write_metric({
            "event": "done",
            "context": request_context,
            "duration_seconds": round(duration, 3),
            "stop_reason": response.stop_reason,
            "response_model": response.model,
            "usage": {
                "input_tokens": response.usage.get("input_tokens", 0),
                "output_tokens": response.usage.get("output_tokens", 0),
                "thinking_tokens": response.usage.get("thinking_tokens", 0),
            },
        })
        return response

    async def call_with_thinking(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        budget_tokens: int = ThinkingLevel.STANDARD,
        profile: Optional[int] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        caller: Optional[str] = None,
        routing_context: Optional[Dict[str, Any]] = None,
        full_output_budget: bool = False
    ) -> LLMResponse:
        """Async version of call_with_thinking.

        When ``full_output_budget`` is True (used by single-shot
        ranking/summary/topic calls), the default response ceiling is raised to
        the full model output limit so that max-effort thinking cannot starve
        the visible output. Effort is never reduced. The map phase deliberately
        leaves this False because it has its own split-and-retry recovery.
        """
        requested_profile = profile if profile is not None else budget_tokens
        profile_name = THINKING_LEVEL_NAMES.get(requested_profile, str(requested_profile))

        if _uses_gemini(self.mode):
            thinking_level = GEMINI_PROFILE_TO_THINKING.get(requested_profile, "medium")
            if max_tokens is None:
                max_tokens = self.max_output_tokens
            max_tokens = min(max_tokens, self.max_output_tokens)
            request_context = {
                "caller": caller or "async_gemini_call_with_thinking",
                "kind": "gemini_native",
                "provider_id": self.provider_id,
                "provider_model": self.model,
                "thinking_type": "adaptive",
                "analysis_profile": profile_name,
                "adaptive_effort": thinking_level,
                "response_max_tokens": max_tokens,
                "message_count": len(messages),
                "message_chars": _messages_char_count(messages),
                "system_chars": _content_char_count(system),
            }
            if routing_context:
                request_context.update(routing_context)
            started_at = time.time()
            response = await self._create_gemini_completion(
                messages=messages,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                thinking_level=thinking_level,
                request_context=request_context,
            )
            response.analysis_profile = profile_name
            response.adaptive_effort = thinking_level
            get_tracker().record_call(
                caller=caller or "async_gemini_call_with_thinking",
                usage=response.usage,
                thinking_level=None,
                duration_seconds=time.time() - started_at,
                model=response.model,
                provider_id=self.provider_id,
                analysis_profile=profile_name,
                adaptive_effort=thinking_level,
                **_routing_record_fields(routing_context),
            )
            return response

        if _uses_openrouter(self.mode):
            if max_tokens is None:
                max_tokens = (
                    self.max_output_tokens
                    if full_output_budget
                    else min(self.max_output_tokens, 16384)
                )
            effort = BUDGET_TO_EFFORT.get(requested_profile, "high")

            start_time = time.time()
            request_context = {
                "caller": caller or "async_openrouter_call_with_thinking",
                "kind": "openrouter_chat",
                "provider_id": self.provider_id,
                "provider_model": self.model,
                "thinking_type": "adaptive",
                "analysis_profile": profile_name,
                "adaptive_effort": effort,
                "response_max_tokens": max_tokens,
                "message_count": len(messages),
                "message_chars": _messages_char_count(messages),
                "system_chars": _content_char_count(system),
            }
            if routing_context:
                request_context.update(routing_context)

            response = await self._create_message(
                request_context=request_context,
                model=self.model,
                max_tokens=max_tokens,
                messages=messages,
                system=system,
                temperature=temperature,
                reasoning={"effort": effort, "exclude": False},
            )
            duration = time.time() - start_time
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
            get_tracker().record_call(
                caller=caller or "async_openrouter_call_with_thinking",
                usage=usage,
                thinking_level=None,
                duration_seconds=duration,
                model=response.model or self.model,
                provider_id=self.provider_id,
                analysis_profile=profile_name,
                adaptive_effort=effort,
                **_routing_record_fields(routing_context),
            )
            thinking = "\n\n".join(
                block.thinking or "" for block in response.content if block.type == "thinking"
            ) or None
            return LLMResponse(
                content="\n".join(block.text or "" for block in response.content if block.type == "text"),
                thinking=thinking,
                usage=usage,
                model=response.model or self.model,
                stop_reason=response.stop_reason,
                thinking_type="adaptive",
                adaptive_effort=effort,
                analysis_profile=profile_name,
                thinking_block_count=1 if thinking else 0,
            )

        use_adaptive = _uses_adaptive_thinking(self.model)

        if use_adaptive:
            effort = BUDGET_TO_EFFORT.get(requested_profile, "high")
            if max_tokens is None:
                # These callers get the full combined thinking+output budget up
                # front so max-effort thinking cannot clip the output.
                max_tokens = self.max_output_tokens if full_output_budget else self.adaptive_max_tokens
            manual_budget_tokens = None
        else:
            effort = None
            manual_budget_tokens = int(requested_profile)
            # Use larger buffer (49152) to avoid JSON truncation in dense batches
            # on older manual-thinking models.
            if max_tokens is None:
                max_tokens = manual_budget_tokens + 49152
            elif max_tokens <= manual_budget_tokens:
                max_tokens = manual_budget_tokens + 16384

        # Cap at model/proxy limit
        if max_tokens > self.max_output_tokens:
            logger.debug(f"Capping max_tokens from {max_tokens} to {self.max_output_tokens} (model limit)")
            max_tokens = self.max_output_tokens

        # If capping pushed max_tokens below the manual budget, reduce it too
        # (only meaningful on the manual-thinking path)
        if not use_adaptive and max_tokens <= manual_budget_tokens:
            manual_budget_tokens = max(max_tokens - 8192, max_tokens // 2)
            logger.info(
                f"Reduced manual thinking budget to {manual_budget_tokens} "
                f"to fit within {self.max_output_tokens} token limit"
            )

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages
        }

        if use_adaptive:
            # Opus 4.8+ path: adaptive thinking with effort. See the sync
            # method for the thinking/output_config rationale.
            kwargs["thinking"] = {"type": "adaptive", "display": "summarized"}
            kwargs["extra_body"] = {"output_config": {"effort": effort}}
        else:
            # Opus 4.6 and earlier: manual thinking with an explicit budget.
            if temperature != 1.0:
                temperature = 1.0
            kwargs["temperature"] = temperature
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": manual_budget_tokens}

        if system:
            kwargs["system"] = system

        start_time = time.time()
        request_context = {
            "caller": caller or "async_call_with_thinking",
            "kind": "adaptive_thinking" if use_adaptive else "manual_thinking",
            "provider_id": self.provider_id,
            "provider_model": self.model,
            "thinking_type": "adaptive" if use_adaptive else "enabled",
            "analysis_profile": profile_name,
            "adaptive_effort": effort if use_adaptive else None,
            "manual_budget_tokens": manual_budget_tokens if not use_adaptive else None,
            "response_max_tokens": max_tokens,
            "message_count": len(messages),
            "message_chars": _messages_char_count(messages),
            "system_chars": _content_char_count(system),
        }
        if routing_context:
            request_context.update(routing_context)

        response = await self._create_message(request_context=request_context, **kwargs)
        duration = time.time() - start_time

        # Log stop_reason for diagnostics (helps debug proxy behavior)
        logger.debug(f"Response stop_reason: {response.stop_reason}, output_tokens: {response.usage.output_tokens}")

        # Check for truncation. Callers that pass full_output_budget already run
        # at the model's max output ceiling, so there is no larger budget to
        # grant -- we surface it loudly rather than degrading thinking effort.
        if response.stop_reason == "max_tokens":
            logger.warning(f"Response truncated at max_tokens ({max_tokens}). Output may be incomplete.")

        thinking_blocks = []
        text_blocks = []

        for block in response.content:
            if block.type == "thinking":
                thinking_blocks.append(block.thinking)
            elif block.type == "text":
                text_blocks.append(block.text)

        # Only enforce thinking-block presence on the manual path; see
        # the sync method for rationale.
        # Anthropic native responses have a stable thinking-block contract.
        # OpenAI-compatible providers expose reasoning inconsistently (for
        # example reasoning_content, reasoning, <think>, or content only), so a
        # valid visible response must not be rejected for missing metadata.
        expects_thinking_blocks = self.mode == "anthropic"
        if (
            not use_adaptive
            and manual_budget_tokens > 0
            and expects_thinking_blocks
            and not thinking_blocks
        ):
            error_msg = (
                f"Extended thinking requested (budget_tokens={manual_budget_tokens}) but no thinking "
                f"blocks returned. This is required for quality analysis.\n\n"
            )
            if self.mode == "openai-compatible":
                error_msg += (
                    f"You are using openai-compatible mode with base_url={self.base_url}. "
                    f"If using LiteLLM, ensure you're using the Anthropic passthrough endpoint "
                    f"(e.g., http://proxy:4000/anthropic) not the OpenAI chat/completions endpoint. "
                    f"See: https://docs.litellm.ai/docs/pass_through/anthropic_completion"
                )
            else:
                error_msg += (
                    f"Check that the model '{self.model}' supports manual thinking "
                    f"and that the API endpoint is responding correctly."
                )
            raise RuntimeError(error_msg)

        # Build usage dict with all available fields
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        }
        # Add cache tokens if present
        if hasattr(response.usage, 'cache_creation_input_tokens'):
            usage["cache_creation_input_tokens"] = response.usage.cache_creation_input_tokens or 0
        if hasattr(response.usage, 'cache_read_input_tokens'):
            usage["cache_read_input_tokens"] = response.usage.cache_read_input_tokens or 0

        # Track cost — label by the caller's original intent (not any
        # capped-down value) so the cost report stays legible.
        get_tracker().record_call(
            caller=caller or "async_call_with_thinking",
            usage=usage,
            thinking_level=None if use_adaptive else profile_name,
            duration_seconds=duration,
            model=response.model,
            provider_id=self.provider_id,
            analysis_profile=profile_name if use_adaptive else None,
            adaptive_effort=effort if use_adaptive else None,
            **_routing_record_fields(routing_context),
        )

        return LLMResponse(
            content="\n".join(text_blocks),
            thinking="\n\n".join(thinking_blocks) if thinking_blocks else None,
            usage=usage,
            model=response.model,
            stop_reason=response.stop_reason,
            thinking_type="adaptive" if use_adaptive else "enabled",
            adaptive_effort=effort,
            analysis_profile=profile_name,
            thinking_block_count=len(thinking_blocks)
        )

    async def call(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        caller: Optional[str] = None,
        routing_context: Optional[Dict[str, Any]] = None
    ) -> LLMResponse:
        """Async plain call; Opus 4.8+ still uses adaptive thinking metadata."""
        if _uses_gemini(self.mode):
            max_tokens = min(max_tokens, self.max_output_tokens)
            request_context = {
                "caller": caller or "async_gemini_call",
                "kind": "gemini_native",
                "provider_id": self.provider_id,
                "provider_model": self.model,
                "thinking_type": "adaptive",
                "analysis_profile": "plain",
                "adaptive_effort": "minimal",
                "response_max_tokens": max_tokens,
                "message_count": len(messages),
                "message_chars": _messages_char_count(messages),
                "system_chars": _content_char_count(system),
            }
            if routing_context:
                request_context.update(routing_context)
            started_at = time.time()
            response = await self._create_gemini_completion(
                messages=messages,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                thinking_level="minimal",
                request_context=request_context,
            )
            response.thinking = None
            response.analysis_profile = "plain"
            response.adaptive_effort = "minimal"
            get_tracker().record_call(
                caller=caller or "async_gemini_call",
                usage=response.usage,
                thinking_level=None,
                duration_seconds=time.time() - started_at,
                model=response.model,
                provider_id=self.provider_id,
                analysis_profile="plain",
                adaptive_effort="minimal",
                **_routing_record_fields(routing_context),
            )
            return response

        if _uses_openrouter(self.mode):
            start_time = time.time()
            request_context = {
                "caller": caller or "async_openrouter_call",
                "kind": "openrouter_chat",
                "provider_id": self.provider_id,
                "provider_model": self.model,
                "response_max_tokens": max_tokens,
                "message_count": len(messages),
                "message_chars": _messages_char_count(messages),
                "system_chars": _content_char_count(system),
            }
            if routing_context:
                request_context.update(routing_context)

            response = await self._create_message(
                request_context=request_context,
                model=self.model,
                max_tokens=max_tokens,
                messages=messages,
                system=system,
                temperature=temperature,
            )
            duration = time.time() - start_time
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
            get_tracker().record_call(
                caller=caller or "async_openrouter_call",
                usage=usage,
                thinking_level=None,
                duration_seconds=duration,
                model=response.model or self.model,
                provider_id=self.provider_id,
                analysis_profile="plain",
                adaptive_effort=None,
                **_routing_record_fields(routing_context),
            )
            content = "".join(block.text or "" for block in response.content)
            return LLMResponse(
                content=content,
                thinking=None,
                usage=usage,
                model=response.model or self.model,
                stop_reason=response.stop_reason,
                thinking_type=None,
                adaptive_effort=None,
                analysis_profile="plain",
                thinking_block_count=0,
            )

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages
        }

        use_adaptive = _uses_adaptive_thinking(self.model)
        if use_adaptive:
            kwargs["thinking"] = {"type": "adaptive", "display": "summarized"}
            kwargs["extra_body"] = {"output_config": {"effort": "high"}}
        else:
            kwargs["temperature"] = temperature

        if system:
            kwargs["system"] = system

        start_time = time.time()
        request_context = {
            "caller": caller or "async_call",
            "kind": "adaptive_message" if use_adaptive else "message",
            "provider_id": self.provider_id,
            "provider_model": self.model,
            "thinking_type": "adaptive" if use_adaptive else None,
            "analysis_profile": "plain" if use_adaptive else None,
            "adaptive_effort": "high" if use_adaptive else None,
            "response_max_tokens": max_tokens,
            "message_count": len(messages),
            "message_chars": _messages_char_count(messages),
            "system_chars": _content_char_count(system),
        }
        if routing_context:
            request_context.update(routing_context)

        response = await self._create_message(request_context=request_context, **kwargs)
        duration = time.time() - start_time

        content = ""
        thinking_block_count = 0
        for block in response.content:
            if getattr(block, "type", None) == "thinking":
                thinking_block_count += 1
            if hasattr(block, 'text'):
                content += block.text

        # Build usage dict with all available fields
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        }
        if hasattr(response.usage, 'cache_creation_input_tokens'):
            usage["cache_creation_input_tokens"] = response.usage.cache_creation_input_tokens or 0
        if hasattr(response.usage, 'cache_read_input_tokens'):
            usage["cache_read_input_tokens"] = response.usage.cache_read_input_tokens or 0

        # Track cost
        get_tracker().record_call(
            caller=caller or "async_call",
            usage=usage,
            thinking_level=None,
            duration_seconds=duration,
            model=response.model,
            provider_id=self.provider_id,
            analysis_profile="plain" if use_adaptive else None,
            adaptive_effort="high" if use_adaptive else None,
            **_routing_record_fields(routing_context),
        )

        return LLMResponse(
            content=content,
            thinking=None,
            usage=usage,
            model=response.model,
            thinking_type="adaptive" if use_adaptive else None,
            adaptive_effort="high" if use_adaptive else None,
            analysis_profile="plain" if use_adaptive else None,
            thinking_block_count=thinking_block_count
        )

    async def call_json(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        budget_tokens: Optional[int] = None,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """Async version of call_json."""
        if budget_tokens:
            response = await self.call_with_thinking(
                messages=messages,
                system=system,
                budget_tokens=budget_tokens,
                max_tokens=max_tokens
            )
        else:
            response = await self.call(
                messages=messages,
                system=system,
                max_tokens=max_tokens
            )

        content = response.content.strip()

        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        try:
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise ValueError(f"Invalid JSON in response: {e}")

    async def close(self):
        """Close the async HTTP client."""
        if self._http_client is not None:
            await self._http_client.aclose()
        if self._gemini_client is not None and hasattr(self._gemini_client, "close"):
            self._gemini_client.close()
        if self._openai_client is not None:
            await self._openai_client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class AsyncLLMRouter:
    """Round-robin async LLM router with per-provider caps and failover."""

    def __init__(self, clients: List[AsyncAnthropicClient]):
        if not clients:
            raise ValueError("AsyncLLMRouter requires at least one route client")
        self.clients = clients
        self._route_lock = asyncio.Lock()
        self._next_route_index = 0
        self._cooldown_base_seconds = _env_float(
            "LLM_ROUTE_COOLDOWN_SECONDS", 120.0, minimum=1.0
        )
        self._cooldown_max_seconds = _env_float(
            "LLM_ROUTE_MAX_COOLDOWN_SECONDS", 1800.0, minimum=self._cooldown_base_seconds
        )
        self._route_health: Dict[str, Dict[str, Any]] = {
            client.provider_id: {
                "successes": 0,
                "failures": 0,
                "consecutive_failures": 0,
                "cooldown_until": 0.0,
                "cooldown_skips": 0,
                "last_error": None,
                "disabled_reason": None,
            }
            for client in clients
        }
        finite_caps = [client.max_concurrent_requests for client in clients]
        self.max_total_concurrent_requests = (
            sum(finite_caps)
            if all(cap > 0 for cap in finite_caps)
            else None
        )
        logger.info(
            "AsyncLLMRouter initialized with routes=%s per_provider_caps=%s "
            "max_total_concurrent_requests=%s",
            ", ".join(f"{client.provider_id}:{client.model}" for client in clients),
            ", ".join(
                f"{client.provider_id}:{client.max_concurrent_requests or 'unlimited'}"
                for client in clients
            ),
            self.max_total_concurrent_requests or "unlimited",
        )

    def _route_is_cooling_down(self, client: AsyncAnthropicClient) -> bool:
        state = self._route_health[client.provider_id]
        return float(state["cooldown_until"]) > time.monotonic()

    def _record_route_success(self, client: AsyncAnthropicClient) -> None:
        state = self._route_health[client.provider_id]
        state["successes"] += 1
        state["consecutive_failures"] = 0
        state["cooldown_until"] = 0.0
        state["last_error"] = None
        state["disabled_reason"] = None

    def _record_route_failure(
        self,
        client: AsyncAnthropicClient,
        reason: str,
        error: Exception,
    ) -> None:
        state = self._route_health[client.provider_id]
        state["failures"] += 1
        state["consecutive_failures"] += 1
        state["last_error"] = f"{type(error).__name__}: {error}"
        if reason in {
            "http_404",
            "http_410",
            "provider_rpd_exhausted",
            "request_compatibility_http_400",
        }:
            state["disabled_reason"] = reason
            logger.warning(
                "LLM route %s disabled for this run after %s",
                client.provider_id,
                reason,
            )
            return
        multiplier = 2 ** min(int(state["consecutive_failures"]) - 1, 4)
        delay = min(self._cooldown_max_seconds, self._cooldown_base_seconds * multiplier)
        if reason in {"http_429", "provider_rpd_exhausted"}:
            delay = max(delay, min(self._cooldown_max_seconds, 300.0))
        state["cooldown_until"] = time.monotonic() + delay
        logger.warning(
            "LLM route %s cooling down for %.0fs after %s (consecutive failures=%s)",
            client.provider_id,
            delay,
            reason,
            state["consecutive_failures"],
        )

    def get_health_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Return prompt-free per-route reliability counters for diagnostics."""
        now = time.monotonic()
        return {
            provider_id: {
                "successes": int(state["successes"]),
                "failures": int(state["failures"]),
                "consecutive_failures": int(state["consecutive_failures"]),
                "cooldown_skips": int(state["cooldown_skips"]),
                "cooldown_remaining_seconds": round(
                    max(0.0, float(state["cooldown_until"]) - now), 1
                ),
                "last_error": state["last_error"],
                "disabled_reason": state["disabled_reason"],
            }
            for provider_id, state in self._route_health.items()
        }

    @classmethod
    def from_config(cls, config: 'LLMProviderConfig') -> 'AsyncLLMRouter | AsyncAnthropicClient':
        """Create a routed client when llm.routes is configured."""
        routes = config.get_route_configs()
        if len(routes) == 1:
            return AsyncAnthropicClient.from_route_config(routes[0])

        # In routed mode, provider failover is the retry strategy. Disable SDK
        # retries so a retryable provider failure moves to another route.
        clients = [
            AsyncAnthropicClient.from_route_config(route, max_retries=0)
            for route in routes
        ]
        return cls(clients)

    async def _next_start_index(self) -> int:
        async with self._route_lock:
            start_index = self._next_route_index
            self._next_route_index = (self._next_route_index + 1) % len(self.clients)
        return start_index

    def _ordered_clients(self, start_index: int) -> List[AsyncAnthropicClient]:
        return [
            self.clients[(start_index + offset) % len(self.clients)]
            for offset in range(len(self.clients))
        ]

    def _ordered_clients_for_call(
        self,
        start_index: int,
        caller: Optional[str],
        profile_name: Optional[str],
    ) -> List[AsyncAnthropicClient]:
        rotated = self._ordered_clients(start_index)
        scored = []
        # Plain calls are lightweight classification/sentiment work and belong
        # to the bulk QUICK tier. Route profiles intentionally expose only the
        # four analysis-profile names used by call_with_thinking().
        eligibility_profile = "QUICK" if profile_name == "plain" else profile_name
        fallback_targets = {
            client.fallback_route_id
            for client in self.clients
            if getattr(client, "fallback_route_id", None)
        }
        for position, client in enumerate(rotated):
            route_profiles = getattr(client, "route_profiles", set())
            caller_patterns = getattr(client, "caller_patterns", [])
            if route_profiles and eligibility_profile not in route_profiles:
                continue
            caller_match = (
                any(fnmatch.fnmatch(caller or "", pattern) for pattern in caller_patterns)
                if caller_patterns
                else False
            )
            if caller_patterns and not caller_match:
                continue
            # Explicit caller matches select quality routes. Root routes select
            # the start of a fallback chain; referenced routes remain available
            # only after their primary or when no matching root exists.
            is_chain_root = client.provider_id not in fallback_targets
            score = (
                (4 if caller_match else 0)
                + (2 if is_chain_root else 0)
                + (1 if route_profiles else 0)
            )
            priority = int(getattr(client, "route_priority", 0))
            scored.append((priority, score, position, client))

        scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
        return [client for _, _, _, client in scored]

    @staticmethod
    def _retry_reason(error: Exception) -> Optional[str]:
        """Return retry reason for transient provider failures."""
        retryable_types = (
            httpx.TimeoutException,
            httpx.TransportError,
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
            openai.APITimeoutError,
            openai.APIConnectionError,
        )
        if isinstance(error, retryable_types):
            return type(error).__name__
        if isinstance(error, OpenRouterResponseError):
            return "invalid_openrouter_response"
        if isinstance(error, json.JSONDecodeError):
            # The provider returned a non-JSON/truncated HTTP body. This is a
            # transport-level response failure, not an application schema
            # error, so move to the configured fallback route immediately.
            return "invalid_provider_json"
        if isinstance(error, ProviderQuotaExhaustedError):
            return "provider_rpd_exhausted"

        status_code = getattr(error, "status_code", None)
        if status_code is None:
            status_code = getattr(error, "code", None)
        response = getattr(error, "response", None)
        if status_code is None and response is not None:
            status_code = getattr(response, "status_code", None)

        if status_code == 429:
            error_text = str(error).lower()
            if any(marker in error_text for marker in (
                "generaterequestsperday",
                "requestsperday",
                "per day",
                "daily quota",
                "rpd",
            )):
                return "provider_rpd_exhausted"
            return "http_429"
        if status_code == 400 and "unsupported parameter" in str(error).lower():
            return "request_compatibility_http_400"
        if status_code in {404, 410}:
            return f"http_{status_code}"
        if isinstance(status_code, int) and status_code >= 500:
            return f"http_{status_code}"

        return None

    @staticmethod
    def _should_retry_same_provider(
        error: Exception,
        reason: Optional[str],
        elapsed_seconds: float,
    ) -> bool:
        """Retry once only for fast transient failures on the current route.

        Full request timeouts, rate limits, quota exhaustion, removed models,
        and compatibility errors should fail over immediately. Retrying those
        on the same provider only adds latency or consumes another paid call.
        """
        if elapsed_seconds > 30.0:
            return False
        if isinstance(error, (
            httpx.TimeoutException,
            anthropic.APITimeoutError,
            openai.APITimeoutError,
        )):
            return False
        if isinstance(error, (
            httpx.ConnectError,
            anthropic.APIConnectionError,
            openai.APIConnectionError,
        )):
            return True
        return reason in {"http_500", "http_502", "http_503", "http_504"}

    async def _call_with_failover(
        self,
        method_name: str,
        call_kwargs: Dict[str, Any],
    ) -> LLMResponse:
        start_index = await self._next_start_index()
        caller = call_kwargs.get("caller")
        profile = call_kwargs.get("profile")
        if profile is None and method_name == "call_with_thinking":
            profile = call_kwargs.get("budget_tokens", ThinkingLevel.STANDARD)
        profile_name = (
            THINKING_LEVEL_NAMES.get(profile, str(profile))
            if profile is not None
            else "plain"
        )
        fallback_from = None
        retry_reason = None
        last_error = None

        ordered_clients = self._ordered_clients_for_call(start_index, caller, profile_name)
        if not ordered_clients:
            raise RuntimeError(
                f"No LLM route is eligible for caller={caller or 'unknown'} "
                f"profile={profile_name}"
            )
        # Some best-effort phases deliberately own a closed fallback chain.
        # Keep only the root and its explicitly configured descendants so a
        # disabled/cooling route cannot make later calls wander to an
        # unrelated paid model.
        if not getattr(ordered_clients[0], "allow_cross_route_fallback", True):
            route_by_id = {client.provider_id: client for client in ordered_clients}
            exclusive_chain = []
            current = ordered_clients[0]
            seen_ids = set()
            while current and current.provider_id not in seen_ids:
                exclusive_chain.append(current)
                seen_ids.add(current.provider_id)
                current = route_by_id.get(getattr(current, "fallback_route_id", None))
            ordered_clients = exclusive_chain
        for attempt, client in enumerate(ordered_clients, start=1):
            later_clients = ordered_clients[attempt:]
            state = self._route_health[client.provider_id]
            if state["disabled_reason"] is not None:
                state["cooldown_skips"] += 1
                logger.info(
                    "Skipping disabled LLM route %s (%s)",
                    client.provider_id,
                    state["disabled_reason"],
                )
                continue
            if self._route_is_cooling_down(client) and any(
                not self._route_is_cooling_down(candidate)
                for candidate in later_clients
            ):
                self._route_health[client.provider_id]["cooldown_skips"] += 1
                logger.info(
                    "Skipping LLM route %s during cooldown for caller=%s",
                    client.provider_id,
                    caller or "unknown",
                )
                continue
            same_provider_retry = 0
            while True:
                routing_context = {
                    "attempt": attempt,
                    "same_provider_retry": same_provider_retry,
                    "fallback_from": fallback_from,
                    "retry_reason": retry_reason,
                }
                started_at = time.monotonic()
                try:
                    response = await getattr(client, method_name)(
                        **call_kwargs,
                        routing_context=routing_context,
                    )
                    self._record_route_success(client)
                    return response
                except Exception as error:
                    last_error = error
                    reason = self._retry_reason(error)
                    elapsed_seconds = time.monotonic() - started_at
                    get_tracker().record_failure(
                        caller=caller or "unknown",
                        model=client.model,
                        provider_id=client.provider_id,
                        duration_seconds=elapsed_seconds,
                        error_type=type(error).__name__,
                        retry_reason=reason,
                        attempt=attempt,
                        same_provider_retry=same_provider_retry,
                        fallback_from=fallback_from,
                    )
                    if reason is not None:
                        self._record_route_failure(client, reason, error)

                    is_link_enrichment = (caller or "").startswith((
                        "link_enricher.",
                        "link_enricher_fallback.",
                        "link_enricher_paid.",
                    ))
                    if (
                        same_provider_retry == 0
                        and not is_link_enrichment
                        and self._should_retry_same_provider(
                            error,
                            reason,
                            elapsed_seconds,
                        )
                    ):
                        same_provider_retry = 1
                        retry_reason = reason
                        logger.warning(
                            "Retrying LLM call once on the same provider %s after "
                            "%s failed in %.1fs",
                            client.provider_id,
                            reason,
                            elapsed_seconds,
                        )
                        await asyncio.sleep(0.25)
                        continue
                
                    base_url_info = getattr(client, "base_url", None) or "default"
                    logger.error(
                        f"❌ [LLM ENDPOINT FAIL] Route: '{client.provider_id}' | Model: '{client.model}' | "
                        f"BaseURL: '{base_url_info}' | Error: {type(error).__name__}: {error}"
                    )
                
                    # Prefer the configured route chain for every retryable provider
                    # failure. Previously this was limited to quota/429 errors, so
                    # OpenAI-compatible timeouts could wander to an unrelated route
                    # (or abort before failover altogether).
                    explicit_fallback_available = False
                    if getattr(client, "fallback_route_id", None) and reason is not None:
                        fallback_id = client.fallback_route_id
                        fallback_client = next((c for c in self.clients if getattr(c, "provider_id", None) == fallback_id), None)
                        if fallback_client and fallback_client in ordered_clients:
                            explicit_fallback_available = True
                            try:
                                ordered_clients.remove(fallback_client)
                                ordered_clients.insert(attempt, fallback_client)
                                logger.warning(
                                    f"⚡ [ROUTE FALLBACK] Route '{client.provider_id}' failed "
                                    f"({reason}). Activating fallback route: '{fallback_id}'"
                                )
                            except ValueError:
                                pass
                
                    if reason is None or attempt >= len(ordered_clients):
                        raise
                    if (
                        not getattr(client, "allow_cross_route_fallback", True)
                        and not explicit_fallback_available
                    ):
                        logger.warning(
                            "Route %s is configured without cross-route fallback; "
                            "returning control to the caller",
                            client.provider_id,
                        )
                        raise

                    logger.warning(
                        "Retrying LLM call on another provider after %s failed: %s: %s",
                        client.provider_id,
                        type(error).__name__,
                        error,
                    )
                    fallback_from = client.provider_id
                    retry_reason = reason
                    break

        if last_error is not None:
            raise last_error
        raise RuntimeError("LLM router had no route to call")

    async def call_with_thinking(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        budget_tokens: int = ThinkingLevel.STANDARD,
        profile: Optional[int] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        caller: Optional[str] = None,
        full_output_budget: bool = False
    ) -> LLMResponse:
        """Route an adaptive/manual thinking call across configured providers."""
        return await self._call_with_failover(
            "call_with_thinking",
            {
                "messages": messages,
                "system": system,
                "budget_tokens": budget_tokens,
                "profile": profile,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "caller": caller,
                "full_output_budget": full_output_budget,
            },
        )

    async def call(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        caller: Optional[str] = None
    ) -> LLMResponse:
        """Route a plain message call across configured providers."""
        return await self._call_with_failover(
            "call",
            {
                "messages": messages,
                "system": system,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "caller": caller,
            },
        )

    async def call_json(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        budget_tokens: Optional[int] = None,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """Route a JSON helper call across configured providers."""
        if budget_tokens:
            response = await self.call_with_thinking(
                messages=messages,
                system=system,
                budget_tokens=budget_tokens,
                max_tokens=max_tokens,
            )
        else:
            response = await self.call(
                messages=messages,
                system=system,
                max_tokens=max_tokens,
            )

        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        try:
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise ValueError(f"Invalid JSON in response: {e}")

    async def close(self):
        """Close all routed async clients."""
        logger.info("LLM ROUTE HEALTH: %s", json.dumps(self.get_health_snapshot(), ensure_ascii=False))
        for client in self.clients:
            await client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
