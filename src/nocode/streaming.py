"""
LLM 流式请求：支持 Anthropic Messages API 与 Moonshot（Kimi）OpenAI 兼容 chat/completions。

TUI 只消费 `stream_assistant()` 的文本增量。
"""

from __future__ import annotations

from collections.abc import Callable
import os
from typing import Any, AsyncIterator

from anthropic import (
    APIConnectionError as AnthropicAPIConnectionError,
    APIError as AnthropicAPIError,
    APIStatusError as AnthropicAPIStatusError,
    APITimeoutError as AnthropicAPITimeoutError,
    AsyncAnthropic,
    AuthenticationError as AnthropicAuthenticationError,
    RateLimitError as AnthropicRateLimitError,
)
from anthropic.types import Message as AnthropicMessage
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

from nocode.env import (
    NOCODE_LLM_MOONSHOT,
    anthropic_base_url_mismatch_hint,
    anthropic_sdk_auth_kwargs,
    is_kimi_coding_anthropic_base,
    is_moonshot_anthropic_messages_base,
    load_project_env,
    moonshot_api_key,
    resolved_anthropic_base_url,
    resolved_llm_provider,
    resolved_moonshot_base_url,
    resolved_moonshot_model,
)


class MissingAnthropicApiKeyError(RuntimeError):
    """未配置 Anthropic API Key。"""


class MissingMoonshotApiKeyError(RuntimeError):
    """未配置 Moonshot（Kimi）API Key。"""


DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 8192

_anthropic_client: AsyncAnthropic | None = None
_moonshot_client: AsyncOpenAI | None = None


def _resolve_anthropic_model() -> str:
    load_project_env()
    override = os.environ.get("ANTHROPIC_MODEL", "").strip()
    if override:
        return override
    base = resolved_anthropic_base_url()
    if is_moonshot_anthropic_messages_base(base) or is_kimi_coding_anthropic_base(base):
        return "kimi-k2.5"
    return DEFAULT_MODEL


def effective_anthropic_model() -> str:
    """当前 Anthropic 分支将使用的 model（供 `--print-config`）。"""
    return _resolve_anthropic_model()


def effective_moonshot_model() -> str:
    """当前 Moonshot 分支将使用的 model（供 `--print-config`）。"""
    return resolved_moonshot_model()


def _get_anthropic_client() -> AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        auth = anthropic_sdk_auth_kwargs()
        if not auth:
            msg = (
                "未找到 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN：请在仓库根 .env 中设置其一"
                "（与 Claude Code 使用 Kimi 时相同可用 ANTHROPIC_AUTH_TOKEN），"
                "或导出环境变量后再启动。"
            )
            raise MissingAnthropicApiKeyError(msg)
        _anthropic_client = AsyncAnthropic(
            **auth,
            base_url=resolved_anthropic_base_url(),
        )
    return _anthropic_client


def _get_moonshot_client() -> AsyncOpenAI:
    global _moonshot_client
    if _moonshot_client is None:
        load_project_env()
        key = moonshot_api_key()
        if not key:
            msg = (
                "使用 Kimi（Moonshot）时请在 .env 设置 MOONSHOT_API_KEY，"
                "并设置 NOCODE_LLM=moonshot。"
            )
            raise MissingMoonshotApiKeyError(msg)
        _moonshot_client = AsyncOpenAI(
            api_key=key,
            base_url=resolved_moonshot_base_url(),
        )
    return _moonshot_client


def _api_messages_to_openai_chat(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将当前会话中的 Anthropic 形消息转为 OpenAI chat 的 messages 列表。"""
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m["role"]
        if role not in ("user", "assistant"):
            continue
        content = m["content"]
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue
        parts: list[dict[str, Any]] = []
        for block in content:
            bt = block["type"]
            if bt == "text":
                parts.append({"type": "text", "text": block["text"]})
            elif bt == "image":
                mt = block["source"]["media_type"]
                b64 = block["source"]["data"]
                data_url = f"data:{mt};base64,{b64}"
                parts.append({"type": "image_url", "image_url": {"url": data_url}})
            elif bt == "tool_use":
                parts.append(
                    {"type": "text", "text": f"[tool_use {block['name']}]"},
                )
            elif bt == "tool_result":
                parts.append({"type": "text", "text": block.get("content", "")})
        if not parts:
            continue
        if len(parts) == 1 and parts[0]["type"] == "text":
            out.append({"role": role, "content": parts[0]["text"]})
        else:
            out.append({"role": role, "content": parts})
    return out


async def _stream_anthropic(
    messages: list[dict[str, Any]],
    *,
    model: str,
    max_tokens: int,
    system: str | None,
) -> AsyncIterator[str]:
    params: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        params["system"] = system
    client = _get_anthropic_client()
    async with client.messages.stream(**params) as stream:
        async for text in stream.text_stream:
            yield text
        _ = await stream.get_final_message()


async def stream_anthropic_turn(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    system: str | None = None,
    tools: list[ToolParam] | None = None,
    on_text_delta: Callable[[str], None] | None = None,
) -> AnthropicMessage:
    """
    执行一轮 Anthropic Messages 流式请求。

    回调仅负责文本增量展示；完整 `Message` 在流结束后返回，供工具循环解析 `tool_use`。
    """
    resolved_model = model if model is not None else _resolve_anthropic_model()
    params: dict[str, Any] = {
        "model": resolved_model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        params["system"] = system
    if tools:
        params["tools"] = tools
    client = _get_anthropic_client()
    async with client.messages.stream(**params) as stream:
        async for text in stream.text_stream:
            if on_text_delta is not None:
                on_text_delta(text)
        return await stream.get_final_message()


async def _stream_moonshot(
    messages: list[dict[str, Any]],
    *,
    model: str,
    max_tokens: int,
    system: str | None,
) -> AsyncIterator[str]:
    openai_messages = _api_messages_to_openai_chat(messages)
    if system:
        openai_messages = [
            {"role": "system", "content": system},
            *openai_messages,
        ]
    client = _get_moonshot_client()
    stream = await client.chat.completions.create(
        model=model,
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


async def stream_assistant(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    system: str | None = None,
) -> AsyncIterator[str]:
    """按顺序产出助手文本增量；根据 `NOCODE_LLM` 走 Anthropic 或 Moonshot。"""
    load_project_env()
    if resolved_llm_provider() == NOCODE_LLM_MOONSHOT:
        resolved_model = model if model is not None else resolved_moonshot_model()
        async for t in _stream_moonshot(
            messages,
            model=resolved_model,
            max_tokens=max_tokens,
            system=system,
        ):
            yield t
        return

    resolved_model = model if model is not None else _resolve_anthropic_model()
    async for t in _stream_anthropic(
        messages,
        model=resolved_model,
        max_tokens=max_tokens,
        system=system,
    ):
        yield t


def format_stream_error(error: Exception) -> str:
    """将 SDK 异常转为适合 TUI 展示的短消息。"""
    if isinstance(
        error,
        (MissingAnthropicApiKeyError, MissingMoonshotApiKeyError),
    ):
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
        base = resolved_anthropic_base_url()
        mismatch = anthropic_base_url_mismatch_hint(base)
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
            "https://api.moonshot.cn/v1 或 https://api.moonshot.ai/v1）以及 MOONSHOT_MODEL（如 kimi-k2.5）。"
            f" 详情：{error.message}"
        )
    if isinstance(error, OpenAIAPIError):
        return str(error)

    return f"{error.__class__.__name__}: {error}"
