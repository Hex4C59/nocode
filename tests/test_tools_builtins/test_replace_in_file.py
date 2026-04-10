"""Tests for the `replace_in_file` builtin tool handler."""

from __future__ import annotations

import json

import pytest

from nocode.tools.builtins.replace_in_file import handler


async def test_replace_in_file_replaces_one_unique_match(runtime) -> None:
    path = runtime.workspace_root / "notes.txt"
    path.write_text("hello world", encoding="utf-8")

    result = json.loads(
        await handler(
            runtime,
            {
                "path": "notes.txt",
                "old_string": "world",
                "new_string": "agent",
            },
        )
    )

    assert result["ok"] is True
    assert result["replacements"] == 1
    assert path.read_text(encoding="utf-8") == "hello agent"


async def test_replace_in_file_replaces_all_matches_when_requested(runtime) -> None:
    path = runtime.workspace_root / "notes.txt"
    path.write_text("a a a", encoding="utf-8")

    result = json.loads(
        await handler(
            runtime,
            {
                "path": "notes.txt",
                "old_string": "a",
                "new_string": "b",
                "replace_all": True,
            },
        )
    )

    assert result["replacements"] == 3
    assert path.read_text(encoding="utf-8") == "b b b"


async def test_replace_in_file_requires_existing_old_string(runtime) -> None:
    path = runtime.workspace_root / "notes.txt"
    path.write_text("hello world", encoding="utf-8")

    with pytest.raises(ValueError, match="old_string not found"):
        await handler(
            runtime,
            {
                "path": "notes.txt",
                "old_string": "agent",
                "new_string": "world",
            },
        )


async def test_replace_in_file_requires_unique_match_when_not_replacing_all(runtime) -> None:
    path = runtime.workspace_root / "notes.txt"
    path.write_text("a a", encoding="utf-8")

    with pytest.raises(ValueError, match="matches multiple times"):
        await handler(
            runtime,
            {
                "path": "notes.txt",
                "old_string": "a",
                "new_string": "b",
            },
        )
