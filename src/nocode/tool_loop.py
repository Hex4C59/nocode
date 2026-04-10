# 本地工具循环：执行 Anthropic `tool_use -> tool_result` 闭环，并复用统一工具注册表与运行时上下文。
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from anthropic.types import ToolParam

from nocode.env import project_root
from nocode.messages import ChatSession, ToolResultBlock, ToolUseBlock, extract_tool_use_blocks
from nocode.streaming import DEFAULT_MAX_TOKENS, stream_anthropic_turn
from nocode.tools import (
    ToolRuntime,
    ToolSpec,
    UserQuestion,
    build_default_registry,
    build_tool_params,
)

DEFAULT_MAX_TOOL_ROUNDS = 4
MAX_TOOL_RESULT_CHARS = 12_000


class MaxToolRoundsExceededError(RuntimeError):
    """工具回合超过上限，停止继续请求模型。"""


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
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    system: str | None = None,
    tools: list[ToolParam] | None = None,
    registry: dict[str, ToolSpec] | None = None,
    runtime: ToolRuntime | None = None,
    max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS,
    on_text_delta: Callable[[str], None] | None = None,
    on_session_change: Callable[[], None] | None = None,
) -> None:
    """
    运行最小工具循环。

    每轮先流式展示文本，再把最终 assistant message 写回会话；若含 `tool_use`，执行本地工具并回传
    `tool_result`，直到没有工具调用或达到上限。
    """
    active_registry = registry if registry is not None else build_default_registry()
    active_tools = tools if tools is not None else build_tool_params(active_registry)
    active_runtime = runtime if runtime is not None else ToolRuntime(project_root())
    tool_rounds = 0

    while True:
        final_message = await stream_anthropic_turn(
            session.to_json_serializable(),
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=active_tools,
            on_text_delta=on_text_delta,
        )
        assistant_blocks = session.append_assistant_api_content(final_message.content)
        if on_session_change is not None:
            on_session_change()

        tool_uses = extract_tool_use_blocks(assistant_blocks)
        if not tool_uses:
            return

        tool_rounds += 1
        if tool_rounds > max_tool_rounds:
            raise MaxToolRoundsExceededError(
                f"工具调用超过上限（max_tool_rounds={max_tool_rounds}）。",
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
