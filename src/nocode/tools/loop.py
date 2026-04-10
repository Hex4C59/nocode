"""Tool loop for executing provider-emitted `tool_use` blocks locally."""

from __future__ import annotations

import json
from collections.abc import Callable

from anthropic.types import ToolParam

from nocode.config import project_root
from nocode.messages import ChatSession, ToolResultBlock, ToolUseBlock, extract_tool_use_blocks
from nocode.providers.base import DEFAULT_MAX_TOKENS, LLMProvider
from nocode.tools.registry import build_default_registry, build_tool_params
from nocode.tools.types import ToolRuntime, ToolSpec, UserQuestion

DEFAULT_MAX_TOOL_ROUNDS = 4
MAX_TOOL_RESULT_CHARS = 12_000


class MaxToolRoundsExceededError(RuntimeError):
    """Raised when the provider keeps asking for tools beyond the limit."""


def _truncate_result(text: str) -> str:
    if len(text) <= MAX_TOOL_RESULT_CHARS:
        return text
    omitted = len(text) - MAX_TOOL_RESULT_CHARS
    return f"{text[:MAX_TOOL_RESULT_CHARS]}\n\n... truncated {omitted} chars ..."


async def _confirm_tool_execution(spec: ToolSpec, runtime: ToolRuntime) -> bool:
    if not spec.requires_confirmation:
        return True
    if runtime.ask_user is None:
        return False
    answer = await runtime.ask_user(
        UserQuestion(
            question=f"工具 `{spec.name}` 请求执行。请输入 yes 继续，或输入其他内容取消。"
        )
    )
    return answer.strip().casefold() in {"y", "yes", "approve", "approved"}


def _tool_error_result(block: ToolUseBlock, error: Exception | str) -> ToolResultBlock:
    message = str(error) if isinstance(error, Exception) else error
    error_type = error.__class__.__name__ if isinstance(error, Exception) else "ToolError"
    return {
        "type": "tool_result",
        "tool_use_id": block["id"],
        "content": json.dumps(
            {
                "ok": False,
                "error_type": error_type,
                "message": message,
            },
            ensure_ascii=False,
        ),
        "is_error": True,
    }


async def _execute_tool_use(
    block: ToolUseBlock,
    *,
    registry: dict[str, ToolSpec],
    runtime: ToolRuntime,
) -> ToolResultBlock:
    spec = registry.get(block["name"])
    if spec is None:
        return _tool_error_result(block, f"unknown tool: {block['name']}")
    approved = await _confirm_tool_execution(spec, runtime)
    if not approved:
        return _tool_error_result(block, f"tool execution denied: {spec.name}")
    try:
        content = await spec.handler(runtime, block["input"])
    except Exception as error:
        return _tool_error_result(block, error)
    return {
        "type": "tool_result",
        "tool_use_id": block["id"],
        "content": _truncate_result(content),
    }


async def run_tool_loop(
    session: ChatSession,
    *,
    provider: LLMProvider,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    system: str | None = None,
    tools: list[ToolParam] | None = None,
    registry: dict[str, ToolSpec] | None = None,
    runtime: ToolRuntime | None = None,
    max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS,
    on_text_delta: Callable[[str], None] | None = None,
    on_session_change: Callable[[], None] | None = None,
) -> None:
    """Run assistant turns until the provider stops asking for tools."""
    active_registry = registry if registry is not None else build_default_registry()
    active_tools = tools if tools is not None else build_tool_params(active_registry)
    active_runtime = runtime if runtime is not None else ToolRuntime(project_root())
    tool_rounds = 0

    while True:
        turn_result = await provider.stream_turn(
            session.to_json_serializable(),
            system=system,
            tools=active_tools,
            max_tokens=max_tokens,
            on_text_delta=on_text_delta,
        )
        session.append_assistant_content_blocks(turn_result.content_blocks)
        if on_session_change is not None:
            on_session_change()

        tool_uses = extract_tool_use_blocks(turn_result.content_blocks)
        if not tool_uses:
            return

        tool_rounds += 1
        if tool_rounds > max_tool_rounds:
            raise MaxToolRoundsExceededError(
                f"工具调用超过上限（max_tool_rounds={max_tool_rounds}）。"
            )

        tool_results: list[ToolResultBlock] = []
        for block in tool_uses:
            tool_results.append(
                await _execute_tool_use(
                    block,
                    registry=active_registry,
                    runtime=active_runtime,
                )
            )
        session.append_tool_result_blocks(tool_results)
        if on_session_change is not None:
            on_session_change()
