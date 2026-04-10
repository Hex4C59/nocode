"""Search UTF-8 workspace files with a regular expression."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from nocode.tools._helpers import iter_search_files, relative_display_path
from nocode.tools.types import ToolRuntime, ToolSpec


def _search_text_sync(
    workspace_root: Path,
    pattern: str,
    base: Path,
    glob_pattern: str | None,
    max_matches: int,
    case_sensitive: bool,
) -> str:
    flags = 0 if case_sensitive else re.IGNORECASE
    regex = re.compile(pattern, flags)
    matches: list[str] = []
    for path in iter_search_files(base, glob_pattern):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not regex.search(line):
                continue
            display_path = relative_display_path(workspace_root, path)
            matches.append(f"{display_path}:{line_no}:{line}")
            if len(matches) >= max_matches:
                return "\n".join(matches)
    if matches:
        return "\n".join(matches)
    return "No matches found."


async def handler(runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    pattern = str(input_obj["pattern"])
    base = runtime.workspace_root
    if "path" in input_obj and input_obj["path"]:
        from nocode.tools._helpers import resolve_workspace_path

        base = resolve_workspace_path(runtime.workspace_root, str(input_obj["path"]))
    max_matches = int(input_obj.get("max_matches", 20))
    glob_pattern = str(input_obj["glob"]) if "glob" in input_obj else None
    case_sensitive = bool(input_obj.get("case_sensitive", True))
    return await asyncio.to_thread(
        _search_text_sync,
        runtime.workspace_root,
        pattern,
        base,
        glob_pattern,
        max_matches,
        case_sensitive,
    )


SPEC = ToolSpec(
    name="search_text",
    description="Search UTF-8 text files in the workspace with a regular expression.",
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string"},
            "glob": {"type": "string"},
            "max_matches": {"type": "integer"},
            "case_sensitive": {"type": "boolean"},
        },
        "required": ["pattern"],
    },
    handler=handler,
)
