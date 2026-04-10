"""Read a UTF-8 text file from the current workspace."""

from __future__ import annotations

from nocode.tools._helpers import numbered_lines, resolve_workspace_path
from nocode.tools.types import ToolRuntime, ToolSpec


async def handler(runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    path = resolve_workspace_path(runtime.workspace_root, str(input_obj["path"]))
    offset = int(input_obj["offset"]) if "offset" in input_obj else None
    limit = int(input_obj["limit"]) if "limit" in input_obj else None
    text = path.read_text(encoding="utf-8")
    return numbered_lines(text, offset=offset, limit=limit)


SPEC = ToolSpec(
    name="read_file",
    description="Read a UTF-8 text file from the workspace with optional line offsets.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "offset": {"type": "integer"},
            "limit": {"type": "integer"},
        },
        "required": ["path"],
    },
    handler=handler,
)
