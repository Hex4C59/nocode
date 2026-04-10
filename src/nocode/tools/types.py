# 本地工具类型：定义工具 schema、运行时上下文、待办状态与提问回调，供工具注册与执行共用。
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from anthropic.types import ToolParam

TodoStatus = Literal["pending", "in_progress", "completed", "cancelled"]


@dataclass(slots=True)
class TodoItemState:
    """单条待办状态，供 `todo_write` 与 TUI 展示复用。"""

    id: str
    content: str
    status: TodoStatus


@dataclass(slots=True)
class UserQuestion:
    """提问类工具的最小交互对象。"""

    question: str
    options: list[str] = field(default_factory=list)
    allow_multiple: bool = False


AskUserHandler = Callable[[UserQuestion], Awaitable[str]]
TodoUpdateHandler = Callable[[list[TodoItemState]], None]
ToolHandler = Callable[["ToolRuntime", dict[str, Any]], Awaitable[str]]


@dataclass(slots=True)
class ToolRuntime:
    """工具执行期间共享的本地状态与回调。"""

    workspace_root: Path
    todos: dict[str, TodoItemState] = field(default_factory=dict)
    ask_user: AskUserHandler | None = None
    on_todos_changed: TodoUpdateHandler | None = None


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """单个内置工具的本地定义。"""

    name: str
    description: str
    input_schema: dict[str, object]
    handler: ToolHandler
    dangerous: bool = False
    requires_confirmation: bool = False

    def as_tool_param(self) -> ToolParam:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
