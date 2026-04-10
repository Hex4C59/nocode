"""Tests for the `todo_write` builtin tool handler."""

from __future__ import annotations

import json

from nocode.tools.builtins.todo import handler


async def test_todo_write_replaces_items_when_merge_is_false(runtime) -> None:
    changes: list[list[object]] = []
    runtime.on_todos_changed = lambda items: changes.append(list(items))

    result = json.loads(
        await handler(
            runtime,
            {
                "merge": False,
                "todos": [{"id": "a", "content": "first", "status": "pending"}],
            },
        )
    )

    assert result["todos"] == [{"id": "a", "content": "first", "status": "pending"}]
    assert list(runtime.todos) == ["a"]
    assert len(changes) == 1


async def test_todo_write_merges_items_when_requested(runtime) -> None:
    await handler(
        runtime,
        {
            "merge": False,
            "todos": [{"id": "a", "content": "first", "status": "pending"}],
        },
    )

    result = json.loads(
        await handler(
            runtime,
            {
                "merge": True,
                "todos": [{"id": "b", "content": "second", "status": "completed"}],
            },
        )
    )

    assert {item["id"] for item in result["todos"]} == {"a", "b"}
    assert runtime.todos["b"].status == "completed"
