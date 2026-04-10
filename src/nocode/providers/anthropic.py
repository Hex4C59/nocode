"""Anthropic Messages API provider implementation."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any, cast

from anthropic import (
    APIConnectionError as AnthropicAPIConnectionError,
    APIError as AnthropicAPIError,
    APIStatusError as AnthropicAPIStatusError,
    APITimeoutError as AnthropicAPITimeoutError,
    AsyncAnthropic,
    AuthenticationError as AnthropicAuthenticationError,
    RateLimitError as AnthropicRateLimitError,
)
from anthropic.types import ToolParam

from nocode.config import AnthropicConfig, ProviderConfig
from nocode.messages import build_assistant_content_blocks
from nocode.providers import register_provider
from nocode.providers.base import DEFAULT_MAX_TOKENS, TurnResult

PROVIDER_ID = "anthropic"


class MissingAnthropicCredentialError(RuntimeError):
    """Raised when no Anthropic credential is configured."""


class AnthropicProvider:
    """LLM provider backed by `AsyncAnthropic.messages.stream()`."""

    provider_id = PROVIDER_ID
    supports_tools = True

    def __init__(self, config: AnthropicConfig) -> None:
        self._config = config
        self._client: AsyncAnthropic | None = None

    def _client_or_raise(self) -> AsyncAnthropic:
        if self._client is None:
            auth_kwargs = self._config.auth_kwargs()
            if not auth_kwargs:
                raise MissingAnthropicCredentialError(
                    "未找到 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN："
                    "请在仓库根 .env 中设置其一，或导出环境变量后再启动。"
                )
            self._client = AsyncAnthropic(
                **auth_kwargs,
                base_url=self._config.base_url,
            )
        return self._client

    async def stream_text(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> AsyncIterator[str]:
        params: dict[str, Any] = {
            "model": self._config.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            params["system"] = system
        client = self._client_or_raise()
        async with client.messages.stream(**params) as stream:
            async for text in stream.text_stream:
                yield text
            _ = await stream.get_final_message()

    async def stream_turn(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        tools: list[ToolParam] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        on_text_delta: Callable[[str], None] | None = None,
    ) -> TurnResult:
        params: dict[str, Any] = {
            "model": self._config.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            params["system"] = system
        if tools:
            params["tools"] = tools
        text_parts: list[str] = []
        client = self._client_or_raise()
        async with client.messages.stream(**params) as stream:
            async for text in stream.text_stream:
                text_parts.append(text)
                if on_text_delta is not None:
                    on_text_delta(text)
            final_message = await stream.get_final_message()
        return TurnResult(
            content_blocks=build_assistant_content_blocks(final_message.content),
            text="".join(text_parts),
        )

    def format_error(self, error: Exception) -> str | None:
        if isinstance(error, MissingAnthropicCredentialError):
            return str(error)
        if isinstance(error, TypeError) and "authentication" in str(error).lower():
            return (
                "无法认证：请确认已在仓库根目录 .env 中设置相应 API Key，"
                "或已导出环境变量。"
            )
        if isinstance(error, AnthropicAuthenticationError):
            return "Anthropic API key 无效或缺失；请检查 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN。"
        if isinstance(error, AnthropicRateLimitError):
            return "Anthropic：请求过于频繁，已被限流；请稍后再试。"
        if isinstance(error, AnthropicAPITimeoutError):
            return "Anthropic：请求超时；请检查网络后重试。"
        if isinstance(error, AnthropicAPIConnectionError):
            return "Anthropic：无法连接 API；请检查网络。"
        if isinstance(error, AnthropicAPIStatusError) and error.status_code == 404:
            mismatch = self._config.mismatch_hint()
            parts = [
                "HTTP 404：当前请求的接口地址不存在。",
                "1) 官方 Anthropic：删除 ANTHROPIC_BASE_URL，或设为 https://api.anthropic.com（不要带 /v1）。",
                "2) 第三方中转：确认对方提供的是 Anthropic Messages API（POST …/v1/messages），"
                "而非仅 OpenAI 兼容的 /v1/chat/completions。",
                "3) 若用 Kimi 的 Anthropic 兼容口，请设 ANTHROPIC_BASE_URL=…/anthropic（见 .env.example）；"
                "若用 OpenAI 兼容口则设 NOCODE_LLM=moonshot 与 MOONSHOT_API_KEY。",
                "4) 若需特定模型名，可在 .env 设置 ANTHROPIC_MODEL=。",
                f"详情：{error.message}",
            ]
            if mismatch:
                parts.insert(1, mismatch)
            return "\n".join(parts)
        if isinstance(error, AnthropicAPIError):
            return str(error)
        return None


def create(config: ProviderConfig) -> AnthropicProvider:
    """Create the Anthropic provider from the active config union."""
    return AnthropicProvider(cast(AnthropicConfig, config))


register_provider(PROVIDER_ID, create)
