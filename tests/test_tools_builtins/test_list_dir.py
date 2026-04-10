"""Tests for the `list_dir` builtin tool handler."""

from __future__ import annotations

import json

import pytest

from nocode.tools.builtins.list_dir import handler


async def test_list_dir_lists_direct_children_with_expected_sorting(runtime) -> None:
    (runtime.workspace_root / "z_dir").mkdir()
    (runtime.workspace_root / "A_dir").mkdir()
    (runtime.workspace_root / "b.txt").write_text("b", encoding="utf-8")
    (runtime.workspace_root / "a.txt").write_text("a", encoding="utf-8")

    result = json.loads(await handler(runtime, {"path": "."}))

    assert result["path"] == "."
    assert [entry["path"] for entry in result["entries"]] == [
        "A_dir",
        "z_dir",
        "a.txt",
        "b.txt",
    ]


async def test_list_dir_rejects_non_directory_paths(runtime) -> None:
    (runtime.workspace_root / "notes.txt").write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError, match="not a directory"):
        await handler(runtime, {"path": "notes.txt"})
