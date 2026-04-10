"""Tests for the `write_file` builtin tool handler."""

from __future__ import annotations

import json

from nocode.tools.builtins.write_file import handler


async def test_write_file_creates_parent_directories_and_writes_content(runtime) -> None:
    result = json.loads(
        await handler(
            runtime,
            {
                "path": "nested/output.txt",
                "content": "hello",
            },
        )
    )

    assert result["ok"] is True
    assert result["path"] == "nested/output.txt"
    assert (runtime.workspace_root / "nested" / "output.txt").read_text(encoding="utf-8") == "hello"


async def test_write_file_overwrites_existing_file(runtime) -> None:
    path = runtime.workspace_root / "notes.txt"
    path.write_text("before", encoding="utf-8")

    await handler(runtime, {"path": "notes.txt", "content": "after"})

    assert path.read_text(encoding="utf-8") == "after"
