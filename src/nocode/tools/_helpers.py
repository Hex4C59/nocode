"""Shared helpers for local tool implementations."""

from __future__ import annotations

import json
from fnmatch import fnmatch
from pathlib import Path

MAX_TOOL_RESULT_CHARS = 12_000
MAX_LIST_DIR_ENTRIES = 500
SKIP_SEARCH_DIRS = {".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache"}


def serialize_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def truncate_text(text: str, limit: int = MAX_TOOL_RESULT_CHARS) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return f"{text[:limit]}\n\n... truncated {omitted} chars ..."


def resolve_workspace_path(workspace_root: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    target = candidate if candidate.is_absolute() else workspace_root / candidate
    resolved = target.resolve(strict=False)
    resolved.relative_to(workspace_root.resolve())
    return resolved


def relative_display_path(workspace_root: Path, path: Path) -> str:
    return path.resolve().relative_to(workspace_root.resolve()).as_posix()


def iter_search_files(base: Path, glob_pattern: str | None) -> list[Path]:
    files: list[Path] = []
    for path in base.rglob("*"):
        if any(part in SKIP_SEARCH_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        relative = path.relative_to(base).as_posix()
        if glob_pattern and not fnmatch(relative, glob_pattern):
            continue
        files.append(path)
    return files


def numbered_lines(text: str, *, offset: int | None, limit: int | None) -> str:
    lines = text.splitlines()
    start = 0 if offset is None else offset
    if start < 0:
        start = max(len(lines) + start, 0)
    stop = len(lines) if limit is None else max(start + limit, start)
    selected = lines[start:stop]
    numbered = [f"{index}|{line}" for index, line in enumerate(selected, start=start + 1)]
    if numbered:
        return "\n".join(numbered)
    return "File is empty."
