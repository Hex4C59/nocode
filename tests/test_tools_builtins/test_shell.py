"""Tests for the `run_shell_command` builtin tool handler."""

from __future__ import annotations

import json
import sys

import pytest

from nocode.tools.builtins.shell import handler


async def test_run_shell_command_executes_argv_and_captures_output(runtime) -> None:
    result = json.loads(
        await handler(
            runtime,
            {
                "argv": [sys.executable, "-c", "print('hello')"],
            },
        )
    )

    assert result["argv"][0] == sys.executable
    assert result["exit_code"] == 0
    assert result["stdout"] == "hello\n"
    assert result["stderr"] == ""


async def test_run_shell_command_respects_cwd(runtime) -> None:
    (runtime.workspace_root / "nested").mkdir()

    result = json.loads(
        await handler(
            runtime,
            {
                "argv": [sys.executable, "-c", "from pathlib import Path; print(Path.cwd().name)"],
                "cwd": "nested",
            },
        )
    )

    assert result["cwd"].endswith("nested")
    assert result["stdout"] == "nested\n"


async def test_run_shell_command_times_out(runtime) -> None:
    with pytest.raises(TimeoutError, match="timed out"):
        await handler(
            runtime,
            {
                "argv": [sys.executable, "-c", "import time; time.sleep(0.2)"],
                "timeout_seconds": 0.01,
            },
        )
