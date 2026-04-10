"""Moonshot OpenAI-compatible provider implementation."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any, cast

from anthropic.types import ToolParam
from openai import (
    APIConnectionError as OpenAIAPIConnectionError,
    APIError as OpenAIAPIError,
    APIStatusError as OpenAIAPIStatusError,
    APITimeoutError as OpenAIAPITimeoutError,
    AsyncOpenAI,
    AuthenticationError as OpenAIAuthenticationError,
    RateLimitError as OpenAIRateLimitError,
)

from nocode.config import MoonshotConfig, ProviderConfig
from nocode.messages import ContentBlock, make_text_block
from nocode.providers import register_provider
from nocode.providers.base import DEFAULT_MAX_TOKENS, TurnResult

PROVIDER_ID = "moonshot"


class MissingMoonshotApiKeyError(RuntimeError):
    """Raised when no Moonshot API key is configured."""


def _api_messages_to_openai_chat(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert local Anthropic-shaped messages into OpenAI chat messages."""
    converted: list[dict[str, Any]] = []
    for message in messages:
        role = message["role"]
        if role not in {"user", "assistant"}:
            continue
        content = message["content"]
        if isinstance(content, str):
            converted.append({"role": role, "content": content})
            continue
        parts: list[dict[str, Any]] = []
        for block in content:
            block_type = block["type"]
            if block_type == "text":
                parts.append({"type": "text", "text": block["text"]})
                continue
            if block_type == "image":
                media_type = block["source"]["media_type"]
                data = block["source"]["data"]
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{data}"},
                    }
                )
                continue
            if block_type == "tool_use":
                parts.append({"type": "text", "text": f"[tool_use {block['name']}]"})
                continue
            parts.append({"type": "text", "text": block.get("content", "")})
        if not parts:
            continue
        if len(parts) == 1 and parts[0]["type"] == "text":
            converted.append({"role": role, "content": parts[0]["text"]})
            continue
        converted.append({"role": role, "content": parts})
    return converted


class MoonshotProvider:
    """LLM provider backed by Moonshot's OpenAI-compatible streaming API."""

    provider_id = PROVIDER_ID
    supports_tools = False

    def __init__(self, config: MoonshotConfig) -> None:
        self._config = config
        self._client: AsyncOpenAI | None = None

    def _client_or_raise(self) -> AsyncOpenAI:
        if self._client is None:
            if not self._config.api_key:
                raise MissingMoonshotApiKeyError(
                    "使用 Kimi（Moonshot）时请在 .env 设置 MOONSHOT_API_KEY，"
                    "并设置 NOCODE_LLM=moonshot。"
                )
            self._client = AsyncOpenAI(
                api_key=self._config.api_key,
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
        openai_messages = _api_messages_to_openai_chat(messages)
        if system:
            openai_messages = [{"role": "system", "content": system}, *openai_messages]
        client = self._client_or_raise()
        stream = await client.chat.completions.create(
            model=self._config.model,
            messages=openai_messages,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    async def stream_turn(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        tools: list[ToolParam] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        on_text_delta: Callable[[str], None] | None = None,
    ) -> TurnResult:
        _ = tools
        text_parts: list[str] = []
        async for text in self.stream_text(
            messages,
            system=system,
            max_tokens=max_tokens,
        ):
            text_parts.append(text)
            if on_text_delta is not None:
                on_text_delta(text)
        content_blocks: list[ContentBlock] = []
        text = "".join(text_parts)
        if text:
            content_blocks.append(make_text_block(text))
        return TurnResult(content_blocks=content_blocks, text=text)

    def format_error(self, error: Exception) -> str | None:
        if isinstance(error, MissingMoonshotApiKeyError):
            return str(error)
        if isinstance(error, OpenAIAuthenticationError):
            return "Moonshot：API Key 无效或未设置；请检查 MOONSHOT_API_KEY。"
        if isinstance(error, OpenAIRateLimitError):
            return "Moonshot：请求过于频繁，已被限流；请稍后再试。"
        if isinstance(error, OpenAIAPITimeoutError):
            return "Moonshot：请求超时；请检查网络后重试。"
        if isinstance(error, OpenAIAPIConnectionError):
            return "Moonshot：无法连接 API；请检查网络与 MOONSHOT_BASE_URL。"
        if isinstance(error, OpenAIAPIStatusError) and error.status_code == 404:
            return (
                "Moonshot：HTTP 404。请检查 MOONSHOT_BASE_URL（须为 …/v1，例如 "
                "https://api.moonshot.cn/v1 或 https://api.moonshot.ai/v1）以及 "
                f"MOONSHOT_MODEL（如 kimi-k2.5）。 详情：{error.message}"
            )
        if isinstance(error, OpenAIAPIError):
            return str(error)
        return None


def create(config: ProviderConfig) -> MoonshotProvider:
    """Create the Moonshot provider from the active config union."""
    return MoonshotProvider(cast(MoonshotConfig, config))


register_provider(PROVIDER_ID, create)
