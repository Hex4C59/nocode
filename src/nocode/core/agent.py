"""UI-agnostic conversation loop that composes providers, tools, and session state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nocode.messages import ChatSession, ContentBlock
from nocode.providers.base import DEFAULT_MAX_TOKENS, LLMProvider
from nocode.tools import ToolRuntime, ToolSpec, run_tool_loop


@dataclass(slots=True)
class AgentLoop:
    """Drive one conversation without any dependency on Textual widgets."""

    session: ChatSession
    provider: LLMProvider
    tool_registry: dict[str, ToolSpec]
    tool_runtime: ToolRuntime
    system_prompt: str
    max_tokens: int = DEFAULT_MAX_TOKENS

    async def submit(
        self,
        blocks: list[ContentBlock],
        *,
        on_text_delta: Callable[[str], None] | None = None,
        on_session_change: Callable[[], None] | None = None,
        on_tool_fallback: Callable[[], None] | None = None,
    ) -> None:
        """Append one user message and execute the matching assistant turn."""
        self.session.append_user_content_blocks(blocks)
        if on_session_change is not None:
            on_session_change()

        if self.provider.supports_tools:
            await run_tool_loop(
                self.session,
                provider=self.provider,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                registry=self.tool_registry,
                runtime=self.tool_runtime,
                on_text_delta=on_text_delta,
                on_session_change=on_session_change,
            )
            return

        if on_tool_fallback is not None and self.tool_registry:
            on_tool_fallback()

        text_parts: list[str] = []
        async for delta in self.provider.stream_text(
            self.session.to_json_serializable(),
            system=self.system_prompt,
            max_tokens=self.max_tokens,
        ):
            text_parts.append(delta)
            if on_text_delta is not None:
                on_text_delta(delta)
        text = "".join(text_parts)
        if text:
            self.session.append_assistant_text(text)
            if on_session_change is not None:
                on_session_change()

    def format_error(self, error: Exception) -> str:
        """Format provider errors for display, with a generic fallback."""
        formatted = self.provider.format_error(error)
        if formatted is not None:
            return formatted
        return f"{error.__class__.__name__}: {error}"
