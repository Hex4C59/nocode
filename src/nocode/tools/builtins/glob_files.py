"""Find files in the workspace with glob patterns."""

from __future__ import annotations

from nocode.tools._helpers import relative_display_path, serialize_json
from nocode.tools.types import ToolRuntime, ToolSpec


async def handler(runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    pattern = str(input_obj["pattern"]).strip()
    if not pattern:
        raise ValueError("pattern must not be empty")
    search_pattern = pattern if pattern.startswith("**/") else f"**/{pattern}"
    matches = [
        relative_display_path(runtime.workspace_root, path)
        for path in runtime.workspace_root.glob(search_pattern)
        if path.is_file()
    ]
    return serialize_json({"matches": matches[:200]})


SPEC = ToolSpec(
    name="glob_files",
    description="Find files in the workspace using a glob pattern.",
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
        },
        "required": ["pattern"],
    },
    handler=handler,
)
