"""Create or overwrite a UTF-8 text file in the workspace."""

from __future__ import annotations

from nocode.tools._helpers import relative_display_path, resolve_workspace_path, serialize_json
from nocode.tools.types import ToolRuntime, ToolSpec


async def handler(runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    path = resolve_workspace_path(runtime.workspace_root, str(input_obj["path"]))
    content = str(input_obj["content"])
    create_parents = bool(input_obj.get("create_parents", True))
    if create_parents:
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return serialize_json(
        {
            "ok": True,
            "path": relative_display_path(runtime.workspace_root, path),
            "bytes_written": len(content.encode("utf-8")),
        }
    )


SPEC = ToolSpec(
    name="write_file",
    description=(
        "Create or overwrite a UTF-8 text file in the workspace. "
        "Prefer replace_in_file for small edits to existing files."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "create_parents": {"type": "boolean"},
        },
        "required": ["path", "content"],
    },
    handler=handler,
    dangerous=True,
    requires_confirmation=True,
)
