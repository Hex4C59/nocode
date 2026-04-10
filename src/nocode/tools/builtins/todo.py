"""Maintain the in-memory todo list for the current session."""

from __future__ import annotations

from nocode.tools._helpers import serialize_json
from nocode.tools.types import TodoItemState, ToolRuntime, ToolSpec


async def handler(runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    merge = bool(input_obj.get("merge", False))
    if not merge:
        runtime.todos.clear()
    for raw in input_obj["todos"]:
        item = TodoItemState(
            id=str(raw["id"]),
            content=str(raw["content"]),
            status=str(raw["status"]),
        )
        runtime.todos[item.id] = item
    items = list(runtime.todos.values())
    if runtime.on_todos_changed is not None:
        runtime.on_todos_changed(items)
    return serialize_json(
        {
            "todos": [
                {"id": item.id, "content": item.content, "status": item.status}
                for item in items
            ]
        }
    )


SPEC = ToolSpec(
    name="todo_write",
    description="Create or update a lightweight in-memory todo list for the current session.",
    input_schema={
        "type": "object",
        "properties": {
            "merge": {"type": "boolean"},
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "content": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed", "cancelled"],
                        },
                    },
                    "required": ["id", "content", "status"],
                },
            },
        },
        "required": ["merge", "todos"],
    },
    handler=handler,
)
