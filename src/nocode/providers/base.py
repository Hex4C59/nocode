"""Provider protocol and shared turn result for LLM backends."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from anthropic.types import ToolParam

from nocode.messages import ContentBlock

DEFAULT_MAX_TOKENS = 8192


@dataclass(frozen=True, slots=True)
class TurnResult:
    """One assistant turn projected into local content blocks."""

    content_blocks: list[ContentBlock]
    text: str = ""


class LLMProvider(Protocol):
    """Interface implemented by every local provider backend."""

    @property
    def provider_id(self) -> str: ...

    @property
    def supports_tools(self) -> bool: ...

    async def stream_turn(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        tools: list[ToolParam] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        on_text_delta: Callable[[str], None] | None = None,
    ) -> TurnResult: ...

    async def stream_text(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> AsyncIterator[str]: ...

    def format_error(self, error: Exception) -> str | None: ...
