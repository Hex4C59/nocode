"""Tests for the `glob_files` builtin tool handler."""

from __future__ import annotations

import json

import pytest

from nocode.tools.builtins.glob_files import handler


async def test_glob_files_matches_nested_files(runtime) -> None:
    (runtime.workspace_root / "src").mkdir()
    (runtime.workspace_root / "src" / "a.py").write_text("print('a')", encoding="utf-8")
    (runtime.workspace_root / "src" / "b.txt").write_text("b", encoding="utf-8")
    (runtime.workspace_root / "nested").mkdir()
    (runtime.workspace_root / "nested" / "c.py").write_text("print('c')", encoding="utf-8")

    result = json.loads(await handler(runtime, {"pattern": "*.py"}))

    assert set(result["matches"]) == {"src/a.py", "nested/c.py"}


async def test_glob_files_requires_non_empty_pattern(runtime) -> None:
    with pytest.raises(ValueError, match="pattern must not be empty"):
        await handler(runtime, {"pattern": "  "})
