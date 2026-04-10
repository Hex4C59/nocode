"""Message block types shared by providers, tools, and the TUI projection."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class TextBlock(TypedDict):
    type: Literal["text"]
    text: str


class ImageSourceBase64(TypedDict):
    type: Literal["base64"]
    media_type: str
    data: str


class ImageBlock(TypedDict):
    type: Literal["image"]
    source: ImageSourceBase64


class ToolUseBlock(TypedDict):
    type: Literal["tool_use"]
    id: str
    name: str
    input: dict[str, Any]


class ToolResultBlock(TypedDict):
    type: Literal["tool_result"]
    tool_use_id: str
    content: str
    is_error: NotRequired[bool]


ContentBlock = TextBlock | ImageBlock | ToolUseBlock | ToolResultBlock


class UserMessage(TypedDict):
    role: Literal["user"]
    content: str | list[ContentBlock]


class AssistantMessage(TypedDict):
    role: Literal["assistant"]
    content: str | list[ContentBlock]


ApiMessage = UserMessage | AssistantMessage
