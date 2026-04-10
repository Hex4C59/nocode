"""Tests for the provider-driven local tool execution loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from nocode.messages import ChatSession, make_text_block
from nocode.providers.base import TurnResult
from nocode.tools.loop import MaxToolRoundsExceededError, run_tool_loop
from nocode.tools.types import ToolRuntime, ToolSpec


class _FakeProvider:
    """Return canned turns to drive the local tool loop in tests."""

    provider_id = "fake"
    supports_tools = True

    def __init__(self, turns: list[TurnResult]) -> None:
        self._turns = turns
        self.calls = 0

    async def stream_turn(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        tools: list[dict[str, object]] | None = None,
        max_tokens: int = 0,
        on_text_delta=None,
    ) -> TurnResult:
        _ = messages, system, tools, max_tokens, on_text_delta
        turn = self._turns[self.calls]
        self.calls += 1
        return turn

    async def stream_text(self, *args, **kwargs):  # pragma: no cover - unused in these tests
        _ = args, kwargs
        if False:
            yield ""

    def format_error(self, error: Exception) -> str | None:
        return str(error)


async def _echo_handler(_runtime: ToolRuntime, _input_obj: dict[str, object]) -> str:
    return "tool output"


async def _failing_handler(_runtime: ToolRuntime, _input_obj: dict[str, object]) -> str:
    raise ValueError("boom")


def _tool_use_block() -> dict[str, object]:
    return {"type": "tool_use", "id": "tool-1", "name": "echo", "input": {"value": "hi"}}


def _runtime(tmp_path: Path) -> ToolRuntime:
    return ToolRuntime(workspace_root=tmp_path)


async def test_run_tool_loop_returns_when_provider_stops_requesting_tools(tmp_path: Path) -> None:
    provider = _FakeProvider([TurnResult(content_blocks=[make_text_block("done")], text="done")])
    session = ChatSession()

    await run_tool_loop(session, provider=provider, runtime=_runtime(tmp_path))

    assert provider.calls == 1
    assert session.messages == [{"role": "assistant", "content": [{"type": "text", "text": "done"}]}]


async def test_run_tool_loop_executes_tool_use_and_continues_to_next_turn(tmp_path: Path) -> None:
    provider = _FakeProvider(
        [
            TurnResult(content_blocks=[_tool_use_block()], text=""),
            TurnResult(content_blocks=[make_text_block("final")], text="final"),
        ]
    )
    session = ChatSession()
    registry = {
        "echo": ToolSpec(
            name="echo",
            description="Echo output.",
            input_schema={"type": "object"},
            handler=_echo_handler,
        )
    }

    await run_tool_loop(
        session,
        provider=provider,
        registry=registry,
        runtime=_runtime(tmp_path),
    )

    assert provider.calls == 2
    assert session.messages[0]["role"] == "assistant"
    assert session.messages[0]["content"][0]["type"] == "tool_use"
    assert session.messages[1]["role"] == "user"
    assert session.messages[1]["content"][0]["content"] == "tool output"
    assert session.messages[2] == {"role": "assistant", "content": [{"type": "text", "text": "final"}]}


async def test_run_tool_loop_raises_when_max_rounds_is_exceeded(tmp_path: Path) -> None:
    provider = _FakeProvider([TurnResult(content_blocks=[_tool_use_block()], text="")])
    session = ChatSession()
    registry = {
        "echo": ToolSpec(
            name="echo",
            description="Echo output.",
            input_schema={"type": "object"},
            handler=_echo_handler,
        )
    }

    with pytest.raises(MaxToolRoundsExceededError):
        await run_tool_loop(
            session,
            provider=provider,
            registry=registry,
            runtime=_runtime(tmp_path),
            max_tool_rounds=0,
        )

    assert session.messages == [{"role": "assistant", "content": [_tool_use_block()]}]


async def test_run_tool_loop_records_tool_errors_in_tool_result_blocks(tmp_path: Path) -> None:
    provider = _FakeProvider(
        [
            TurnResult(content_blocks=[_tool_use_block()], text=""),
            TurnResult(content_blocks=[make_text_block("after error")], text="after error"),
        ]
    )
    session = ChatSession()
    registry = {
        "echo": ToolSpec(
            name="echo",
            description="Echo output.",
            input_schema={"type": "object"},
            handler=_failing_handler,
        )
    }

    await run_tool_loop(
        session,
        provider=provider,
        registry=registry,
        runtime=_runtime(tmp_path),
    )

    tool_result = session.messages[1]["content"][0]
    error_payload = json.loads(tool_result["content"])

    assert tool_result["is_error"] is True
    assert error_payload == {
        "ok": False,
        "error_type": "ValueError",
        "message": "boom",
    }
    assert session.messages[2]["content"][0]["text"] == "after error"
