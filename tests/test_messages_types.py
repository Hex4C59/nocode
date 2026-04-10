"""Smoke tests for message block and API message shapes."""

from __future__ import annotations

from nocode.messages.types import ApiMessage, ContentBlock


def test_content_blocks_can_be_constructed_as_runtime_dicts() -> None:
    text_block: ContentBlock = {"type": "text", "text": "hello"}
    image_block: ContentBlock = {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": "Zm9v",
        },
    }
    tool_use_block: ContentBlock = {
        "type": "tool_use",
        "id": "tool-1",
        "name": "read_file",
        "input": {"path": "README.md"},
    }
    tool_result_block: ContentBlock = {
        "type": "tool_result",
        "tool_use_id": "tool-1",
        "content": '{"ok": true}',
        "is_error": False,
    }

    assert text_block["text"] == "hello"
    assert image_block["source"]["media_type"] == "image/png"
    assert tool_use_block["name"] == "read_file"
    assert tool_result_block["tool_use_id"] == "tool-1"


def test_api_messages_can_hold_string_or_block_content() -> None:
    text_message: ApiMessage = {"role": "user", "content": "hello"}
    block_message: ApiMessage = {
        "role": "assistant",
        "content": [{"type": "text", "text": "world"}],
    }

    assert text_message["role"] == "user"
    assert text_message["content"] == "hello"
    assert block_message["content"][0]["text"] == "world"
