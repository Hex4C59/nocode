"""Tests for the `search_text` builtin tool handler."""

from __future__ import annotations

from nocode.tools.builtins.search_text import handler


async def test_search_text_finds_matches_across_files(runtime) -> None:
    (runtime.workspace_root / "one.py").write_text("hello\nworld", encoding="utf-8")
    (runtime.workspace_root / "two.txt").write_text("say hello", encoding="utf-8")

    result = await handler(runtime, {"pattern": "hello", "case_sensitive": True})

    assert result == "one.py:1:hello\ntwo.txt:1:say hello"


async def test_search_text_can_match_case_insensitively(runtime) -> None:
    (runtime.workspace_root / "one.py").write_text("Hello", encoding="utf-8")
    (runtime.workspace_root / "two.txt").write_text("hello", encoding="utf-8")

    result = await handler(runtime, {"pattern": "hello", "case_sensitive": False})

    assert result == "one.py:1:Hello\ntwo.txt:1:hello"


async def test_search_text_respects_glob_filters(runtime) -> None:
    (runtime.workspace_root / "one.py").write_text("needle", encoding="utf-8")
    (runtime.workspace_root / "two.txt").write_text("needle", encoding="utf-8")

    result = await handler(runtime, {"pattern": "needle", "glob": "*.py"})

    assert result == "one.py:1:needle"


async def test_search_text_returns_empty_marker_when_no_matches(runtime) -> None:
    (runtime.workspace_root / "one.py").write_text("hello", encoding="utf-8")

    result = await handler(runtime, {"pattern": "missing"})

    assert result == "No matches found."
