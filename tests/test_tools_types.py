"""Tests for the local tool runtime dataclasses and tool specs."""

from __future__ import annotations

from pathlib import Path

from nocode.tools.types import ToolRuntime, ToolSpec


async def _dummy_handler(_runtime: ToolRuntime, _input_obj: dict[str, object]) -> str:
    return "ok"


def test_tool_runtime_defaults_are_empty_and_optional(tmp_path: Path) -> None:
    runtime = ToolRuntime(workspace_root=tmp_path)

    assert runtime.workspace_root == tmp_path
    assert runtime.todos == {}
    assert runtime.ask_user is None
    assert runtime.on_todos_changed is None


def test_tool_spec_as_tool_param_returns_expected_shape(tmp_path: Path) -> None:
    runtime = ToolRuntime(workspace_root=tmp_path)
    spec = ToolSpec(
        name="echo",
        description="Echo one string.",
        input_schema={"type": "object", "properties": {"value": {"type": "string"}}},
        handler=_dummy_handler,
        dangerous=True,
        requires_confirmation=True,
    )

    tool_param = spec.as_tool_param()

    assert runtime.workspace_root == tmp_path
    assert tool_param == {
        "name": "echo",
        "description": "Echo one string.",
        "input_schema": {"type": "object", "properties": {"value": {"type": "string"}}},
    }
