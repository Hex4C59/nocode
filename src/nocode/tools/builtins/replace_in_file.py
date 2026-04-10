"""Replace exact text inside one UTF-8 file."""

from __future__ import annotations

from nocode.tools._helpers import relative_display_path, resolve_workspace_path, serialize_json
from nocode.tools.types import ToolRuntime, ToolSpec


async def handler(runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    path = resolve_workspace_path(runtime.workspace_root, str(input_obj["path"]))
    old_string = str(input_obj["old_string"])
    new_string = str(input_obj["new_string"])
    replace_all = bool(input_obj.get("replace_all", False))
    if not old_string:
        raise ValueError("old_string must not be empty")
    text = path.read_text(encoding="utf-8")
    if old_string not in text:
        raise ValueError("old_string not found in file (no changes written)")
    if replace_all:
        updated = text.replace(old_string, new_string)
        replacements = text.count(old_string)
    else:
        if text.count(old_string) > 1:
            raise ValueError(
                "old_string matches multiple times; set replace_all=true or make old_string unique",
            )
        updated = text.replace(old_string, new_string, 1)
        replacements = 1
    path.write_text(updated, encoding="utf-8")
    return serialize_json(
        {
            "ok": True,
            "path": relative_display_path(runtime.workspace_root, path),
            "replacements": replacements,
        }
    )


SPEC = ToolSpec(
    name="replace_in_file",
    description=(
        "Replace exact text in a UTF-8 file. When replace_all is false, old_string must match "
        "exactly once; when true, every occurrence is replaced."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_string": {"type": "string"},
            "new_string": {"type": "string"},
            "replace_all": {"type": "boolean"},
        },
        "required": ["path", "old_string", "new_string"],
    },
    handler=handler,
    dangerous=True,
    requires_confirmation=True,
)
