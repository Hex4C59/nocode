"""RichLog-friendly formatting helpers for local chat history display."""

from __future__ import annotations

import json

from rich.markup import escape

from nocode.messages.types import ApiMessage


def _preview_text(text: str, limit: int = 120) -> str:
    compact = " ".join(text.splitlines())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def _preview_json(data: object, limit: int = 120) -> str:
    raw = json.dumps(data, ensure_ascii=False)
    return _preview_text(raw, limit=limit)


def format_api_message_markup(message: ApiMessage) -> str:
    """Project one API-shaped message into one Rich markup line."""
    role = message["role"]
    speaker_label = "你" if role == "user" else "助手"
    style = "bold green" if role == "user" else "bold blue"
    content = message["content"]
    if isinstance(content, str):
        return f"[{style}]{speaker_label}[/]: {escape(content)}"
    parts: list[str] = []
    for block in content:
        if block["type"] == "text":
            parts.append(escape(block["text"]))
            continue
        if block["type"] == "image":
            parts.append(f"[图·{escape(block['source']['media_type'])}]")
            continue
        if block["type"] == "tool_use":
            preview = _preview_json(block["input"])
            parts.append(f"[工具 {escape(block['name'])}] {escape(preview)}")
            continue
        preview = _preview_text(block["content"])
        tool_label = "tool_error" if block.get("is_error") else "tool_result"
        parts.append(f"[{tool_label}] {escape(preview)}")
    body = " ".join(parts) if parts else "(空)"
    return f"[{style}]{speaker_label}[/]: {body}"
