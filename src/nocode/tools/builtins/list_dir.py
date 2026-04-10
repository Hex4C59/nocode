"""List direct children under one workspace directory."""

from __future__ import annotations

from nocode.tools._helpers import (
    MAX_LIST_DIR_ENTRIES,
    relative_display_path,
    resolve_workspace_path,
    serialize_json,
)
from nocode.tools.types import ToolRuntime, ToolSpec


async def handler(runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    raw_path = str(input_obj.get("path", ".")).strip() or "."
    base = resolve_workspace_path(runtime.workspace_root, raw_path)
    if not base.is_dir():
        raise ValueError(f"not a directory: {raw_path}")
    children = sorted(base.iterdir(), key=lambda path: (not path.is_dir(), path.name.lower()))
    truncated = len(children) > MAX_LIST_DIR_ENTRIES
    if truncated:
        children = children[:MAX_LIST_DIR_ENTRIES]
    entries: list[dict[str, object]] = []
    for child in children:
        entries.append(
            {
                "path": relative_display_path(runtime.workspace_root, child),
                "kind": "dir" if child.is_dir() else "file",
            }
        )
    payload: dict[str, object] = {
        "path": relative_display_path(runtime.workspace_root, base),
        "entries": entries,
    }
    if truncated:
        payload["truncated"] = True
    return serialize_json(payload)


SPEC = ToolSpec(
    name="list_dir",
    description=(
        "List files and subdirectories directly under a workspace directory (non-recursive). "
        "Results are capped; use glob_files or search_text for deeper discovery."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
        },
        "required": [],
    },
    handler=handler,
)
