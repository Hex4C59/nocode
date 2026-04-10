# 本地工具注册表：提供 Claude Code 风格的可落地工具子集，并统一工具 schema 与执行逻辑。
from __future__ import annotations

import asyncio
import json
import re
from fnmatch import fnmatch
from pathlib import Path
from urllib.parse import urlparse

import requests

from nocode.tools.types import TodoItemState, ToolRuntime, ToolSpec, UserQuestion

MAX_TOOL_RESULT_CHARS = 12_000
SKIP_SEARCH_DIRS = {".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache"}


def _serialize_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _truncate_text(text: str, limit: int = MAX_TOOL_RESULT_CHARS) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return f"{text[:limit]}\n\n... truncated {omitted} chars ..."


def _resolve_workspace_path(workspace_root: Path, raw_path: str) -> Path:
    base = Path(raw_path)
    candidate = base if base.is_absolute() else workspace_root / base
    resolved = candidate.resolve(strict=False)
    resolved.relative_to(workspace_root.resolve())
    return resolved


def _relative_display_path(workspace_root: Path, path: Path) -> str:
    return path.resolve().relative_to(workspace_root.resolve()).as_posix()


def _iter_search_files(base: Path, glob_pattern: str | None) -> list[Path]:
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


def _numbered_lines(text: str, *, offset: int | None, limit: int | None) -> str:
    lines = text.splitlines()
    start = 0 if offset is None else offset
    if start < 0:
        start = max(len(lines) + start, 0)
    stop = len(lines) if limit is None else max(start + limit, start)
    selected = lines[start:stop]
    numbered = [f"{idx}|{line}" for idx, line in enumerate(selected, start=start + 1)]
    return "\n".join(numbered) if numbered else "File is empty."


async def _read_file(runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    path = _resolve_workspace_path(runtime.workspace_root, str(input_obj["path"]))
    offset = int(input_obj["offset"]) if "offset" in input_obj else None
    limit = int(input_obj["limit"]) if "limit" in input_obj else None
    text = path.read_text(encoding="utf-8")
    return _numbered_lines(text, offset=offset, limit=limit)


async def _glob_files(runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    pattern = str(input_obj["pattern"]).strip()
    if not pattern:
        raise ValueError("pattern must not be empty")
    search_pattern = pattern if pattern.startswith("**/") else f"**/{pattern}"
    matches = [
        _relative_display_path(runtime.workspace_root, path)
        for path in runtime.workspace_root.glob(search_pattern)
        if path.is_file()
    ]
    return _serialize_json({"matches": matches[:200]})


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
    for path in _iter_search_files(base, glob_pattern):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not regex.search(line):
                continue
            display_path = _relative_display_path(workspace_root, path)
            matches.append(f"{display_path}:{line_no}:{line}")
            if len(matches) >= max_matches:
                return "\n".join(matches)
    return "\n".join(matches) if matches else "No matches found."


async def _search_text(runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    pattern = str(input_obj["pattern"])
    base = runtime.workspace_root
    if "path" in input_obj and input_obj["path"]:
        base = _resolve_workspace_path(runtime.workspace_root, str(input_obj["path"]))
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


async def _run_shell_command(runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    argv = [str(part) for part in input_obj["argv"]]
    cwd = runtime.workspace_root
    if "cwd" in input_obj and input_obj["cwd"]:
        cwd = _resolve_workspace_path(runtime.workspace_root, str(input_obj["cwd"]))
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
    return _serialize_json(
        {
            "argv": argv,
            "cwd": str(cwd),
            "exit_code": process.returncode,
            "stdout": _truncate_text(stdout.decode("utf-8", errors="replace")),
            "stderr": _truncate_text(stderr.decode("utf-8", errors="replace")),
        }
    )


async def _todo_write(runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    merge = bool(input_obj.get("merge", False))
    if not merge:
        runtime.todos.clear()
    for raw in input_obj["todos"]:
        item = TodoItemState(
            id=str(raw["id"]),
            content=str(raw["content"]),
            status=str(raw["status"]),
        )
        runtime.todos[item.id] = item
    items = list(runtime.todos.values())
    if runtime.on_todos_changed is not None:
        runtime.on_todos_changed(items)
    return _serialize_json(
        {
            "todos": [
                {"id": item.id, "content": item.content, "status": item.status}
                for item in items
            ]
        }
    )


async def _ask_user(runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    if runtime.ask_user is None:
        raise RuntimeError("ask_user is not configured in runtime")
    question = UserQuestion(
        question=str(input_obj["question"]),
        options=[str(option) for option in input_obj.get("options", [])],
        allow_multiple=bool(input_obj.get("allow_multiple", False)),
    )
    answer = await runtime.ask_user(question)
    return _serialize_json({"answer": answer})


def _fetch_url_sync(url: str, max_chars: int) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("url must start with http:// or https://")
    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "nocode/0.1"},
    )
    response.raise_for_status()
    text = response.text.strip()
    return _serialize_json(
        {
            "url": response.url,
            "status_code": response.status_code,
            "content": _truncate_text(text, limit=max_chars),
        }
    )


async def _web_fetch(_runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    url = str(input_obj["url"])
    max_chars = int(input_obj.get("max_chars", 8000))
    return await asyncio.to_thread(_fetch_url_sync, url, max_chars)


def build_default_registry() -> dict[str, ToolSpec]:
    return {
        "read_file": ToolSpec(
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
            handler=_read_file,
        ),
        "glob_files": ToolSpec(
            name="glob_files",
            description="Find files in the workspace using a glob pattern.",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                },
                "required": ["pattern"],
            },
            handler=_glob_files,
        ),
        "search_text": ToolSpec(
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
            handler=_search_text,
        ),
        "run_shell_command": ToolSpec(
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
            handler=_run_shell_command,
            dangerous=True,
            requires_confirmation=True,
        ),
        "todo_write": ToolSpec(
            name="todo_write",
            description="Create or update a lightweight in-memory todo list for the current session.",
            input_schema={
                "type": "object",
                "properties": {
                    "merge": {"type": "boolean"},
                    "todos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "content": {"type": "string"},
                                "status": {
                                    "type": "string",
                                    "enum": ["pending", "in_progress", "completed", "cancelled"],
                                },
                            },
                            "required": ["id", "content", "status"],
                        },
                    },
                },
                "required": ["merge", "todos"],
            },
            handler=_todo_write,
        ),
        "ask_user": ToolSpec(
            name="ask_user",
            description="Ask the user a focused question and wait for a text answer.",
            input_schema={
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "allow_multiple": {"type": "boolean"},
                },
                "required": ["question"],
            },
            handler=_ask_user,
        ),
        "web_fetch": ToolSpec(
            name="web_fetch",
            description="Fetch a web page over HTTP(S) and return its response text.",
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "max_chars": {"type": "integer"},
                },
                "required": ["url"],
            },
            handler=_web_fetch,
        ),
    }


def build_tool_params(registry: dict[str, ToolSpec]) -> list[dict[str, object]]:
    return [registry[name].as_tool_param() for name in registry]
