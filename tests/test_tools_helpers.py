"""Tests for shared helpers used by the builtin local tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from nocode.tools._helpers import (
    iter_search_files,
    numbered_lines,
    relative_display_path,
    resolve_workspace_path,
    truncate_text,
)


def test_truncate_text_leaves_short_text_unchanged() -> None:
    assert truncate_text("hello", limit=10) == "hello"


def test_truncate_text_marks_long_text_as_truncated() -> None:
    rendered = truncate_text("abcdefghij", limit=5)

    assert rendered.startswith("abcde")
    assert "truncated 5 chars" in rendered


def test_resolve_workspace_path_supports_relative_and_absolute_paths(tmp_path: Path) -> None:
    relative = resolve_workspace_path(tmp_path, "src/nocode/cli.py")
    absolute = resolve_workspace_path(tmp_path, str(tmp_path / "src" / "nocode" / "cli.py"))

    assert relative == tmp_path / "src" / "nocode" / "cli.py"
    assert absolute == tmp_path / "src" / "nocode" / "cli.py"


def test_resolve_workspace_path_rejects_paths_outside_workspace(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"

    with pytest.raises(ValueError):
        resolve_workspace_path(tmp_path, str(outside))


def test_relative_display_path_uses_posix_format(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "file.txt"

    assert relative_display_path(tmp_path, path) == "nested/file.txt"


def test_iter_search_files_skips_ignored_directories_and_respects_glob(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "hidden.py").write_text("hidden", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "skip.py").write_text("skip", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "match.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "root.txt").write_text("root", encoding="utf-8")

    all_files = {path.relative_to(tmp_path).as_posix() for path in iter_search_files(tmp_path, None)}
    py_files = {
        path.relative_to(tmp_path).as_posix()
        for path in iter_search_files(tmp_path, "nested/*.py")
    }

    assert all_files == {"nested/match.py", "root.txt"}
    assert py_files == {"nested/match.py"}


def test_numbered_lines_supports_offsets_limits_and_negative_offsets() -> None:
    text = "alpha\nbeta\ngamma\ndelta"

    assert numbered_lines(text, offset=None, limit=None) == "1|alpha\n2|beta\n3|gamma\n4|delta"
    assert numbered_lines(text, offset=1, limit=2) == "2|beta\n3|gamma"
    assert numbered_lines(text, offset=-1, limit=None) == "4|delta"


def test_numbered_lines_returns_empty_marker_for_empty_text() -> None:
    assert numbered_lines("", offset=None, limit=None) == "File is empty."
