"""Tests for construction of the default system prompt text."""

from __future__ import annotations

from nocode.core.system_prompt import build_system_prompt


def test_build_system_prompt_includes_sorted_tool_names_and_guidance() -> None:
    prompt = build_system_prompt(["write_file", "ask_user", "read_file"])

    assert prompt.startswith("You are a local coding agent")
    assert "Available tools in this runtime: ask_user, read_file, write_file" in prompt
    assert "Use `read_file`, `list_dir`, `glob_files`, and `search_text`" in prompt
    assert "Keep behavior cross-platform across macOS, Linux, and Windows." in prompt
