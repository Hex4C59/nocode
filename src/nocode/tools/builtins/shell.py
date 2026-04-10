"""Run one subprocess from argv without `shell=True`."""

from __future__ import annotations

import asyncio

from nocode.tools._helpers import resolve_workspace_path, serialize_json, truncate_text
from nocode.tools.types import ToolRuntime, ToolSpec


async def handler(runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    argv = [str(part) for part in input_obj["argv"]]
    cwd = runtime.workspace_root
    if "cwd" in input_obj and input_obj["cwd"]:
        cwd = resolve_workspace_path(runtime.workspace_root, str(input_obj["cwd"]))
    timeout_seconds = float(input_obj.get("timeout_seconds", 30))
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout_seconds)
    except TimeoutError:
        process.kill()
        await process.communicate()
        raise TimeoutError(f"command timed out after {timeout_seconds} seconds")
    return serialize_json(
        {
            "argv": argv,
            "cwd": str(cwd),
            "exit_code": process.returncode,
            "stdout": truncate_text(stdout.decode("utf-8", errors="replace")),
            "stderr": truncate_text(stderr.decode("utf-8", errors="replace")),
        }
    )


SPEC = ToolSpec(
    name="run_shell_command",
    description=(
        "Run a command as argv without shell=True. "
        "Use this for git, python, uv, npm, and other CLI tools."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "argv": {
                "type": "array",
                "items": {"type": "string"},
            },
            "cwd": {"type": "string"},
            "timeout_seconds": {"type": "number"},
        },
        "required": ["argv"],
    },
    handler=handler,
    dangerous=True,
    requires_confirmation=True,
)
