"""Tests for builtin tool discovery and Anthropic tool-param projection."""

from __future__ import annotations

from nocode.tools.registry import build_default_registry, build_tool_params


def test_build_default_registry_discovers_expected_tools() -> None:
    registry = build_default_registry()

    assert set(registry) == {
        "ask_user",
        "glob_files",
        "list_dir",
        "read_file",
        "replace_in_file",
        "run_shell_command",
        "search_text",
        "todo_write",
        "web_fetch",
        "write_file",
    }


def test_build_tool_params_projects_registry_entries() -> None:
    registry = build_default_registry()

    params = build_tool_params(registry)

    assert {param["name"] for param in params} == set(registry)
    assert all("description" in param for param in params)
    assert all("input_schema" in param for param in params)
