"""Session state and block conversion helpers for chat history management."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from typing import Any, cast

from nocode.messages.image import make_text_block
from nocode.messages.types import ApiMessage, ContentBlock, ToolResultBlock, ToolUseBlock


def build_assistant_content_blocks(api_content: Sequence[Any]) -> list[ContentBlock]:
    """Convert Anthropic SDK content blocks into local `ContentBlock` values."""
    blocks: list[ContentBlock] = []
    for block in api_content:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            blocks.append(make_text_block(getattr(block, "text")))
            continue
        if block_type == "tool_use":
            blocks.append(
                {
                    "type": "tool_use",
                    "id": getattr(block, "id"),
                    "name": getattr(block, "name"),
                    "input": dict(getattr(block, "input")),
                }
            )
    return blocks


def extract_tool_use_blocks(blocks: Sequence[ContentBlock]) -> list[ToolUseBlock]:
    """Return all tool-use blocks from one assistant message."""
    results: list[ToolUseBlock] = []
    for block in blocks:
        if block["type"] == "tool_use":
            results.append(block)
    return results


class ChatSession:
    """In-memory chat history using the Anthropic Messages API shape."""

    def __init__(self) -> None:
        self.messages: list[ApiMessage] = []

    def append_user_text(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def append_user_content_blocks(self, blocks: list[ContentBlock]) -> None:
        self.messages.append({"role": "user", "content": blocks})

    def append_assistant_text(self, text: str) -> None:
        self.messages.append({"role": "assistant", "content": text})

    def append_assistant_content_blocks(self, blocks: list[ContentBlock]) -> None:
        self.messages.append({"role": "assistant", "content": blocks})

    def append_assistant_api_content(self, api_content: Sequence[Any]) -> list[ContentBlock]:
        blocks = build_assistant_content_blocks(api_content)
        self.append_assistant_content_blocks(blocks)
        return blocks

    def append_tool_result_blocks(self, blocks: list[ToolResultBlock]) -> None:
        self.messages.append({"role": "user", "content": cast(list[ContentBlock], blocks)})

    def append_assistant_tool_use_example(
        self,
        tool_use_id: str,
        name: str,
        input_obj: dict[str, Any],
    ) -> None:
        block: ToolUseBlock = {
            "type": "tool_use",
            "id": tool_use_id,
            "name": name,
            "input": input_obj,
        }
        self.messages.append({"role": "assistant", "content": [block]})

    def to_json_serializable(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], copy.deepcopy(self.messages))
