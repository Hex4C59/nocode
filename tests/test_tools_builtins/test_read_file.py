"""Tests for the `read_file` builtin tool handler."""

from __future__ import annotations

from pathlib import Path

import pytest

from nocode.tools.builtins.read_file import handler


async def test_read_file_reads_existing_file(runtime) -> None:
    path = runtime.workspace_root / "notes.txt"
    path.write_text("alpha\nbeta", encoding="utf-8")

    result = await handler(runtime, {"path": "notes.txt"})

    assert result == "1|alpha\n2|beta"


async def test_read_file_supports_offset_and_limit(runtime) -> None:
    path = runtime.workspace_root / "notes.txt"
    path.write_text("alpha\nbeta\ngamma", encoding="utf-8")

    result = await handler(runtime, {"path": "notes.txt", "offset": 1, "limit": 1})

    assert result == "2|beta"


async def test_read_file_raises_for_missing_file(runtime) -> None:
    with pytest.raises(FileNotFoundError):
        await handler(runtime, {"path": "missing.txt"})


async def test_read_file_rejects_outside_workspace(runtime, tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"

    with pytest.raises(ValueError):
        await handler(runtime, {"path": str(outside)})
