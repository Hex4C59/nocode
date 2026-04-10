"""Tests for chat-session mutation and assistant block conversion."""

from __future__ import annotations

from types import SimpleNamespace

from nocode.messages.session import (
    ChatSession,
    build_assistant_content_blocks,
    extract_tool_use_blocks,
)


def test_build_assistant_content_blocks_converts_supported_sdk_blocks() -> None:
    api_content = [
        SimpleNamespace(type="text", text="hello"),
        SimpleNamespace(
            type="tool_use",
            id="tool-1",
            name="read_file",
            input={"path": "src/nocode/cli.py"},
        ),
        SimpleNamespace(type="unsupported"),
    ]

    blocks = build_assistant_content_blocks(api_content)

    assert blocks == [
        {"type": "text", "text": "hello"},
        {
            "type": "tool_use",
            "id": "tool-1",
            "name": "read_file",
            "input": {"path": "src/nocode/cli.py"},
        },
    ]


def test_extract_tool_use_blocks_filters_mixed_content() -> None:
    blocks = [
        {"type": "text", "text": "hello"},
        {"type": "tool_use", "id": "tool-1", "name": "read_file", "input": {}},
        {"type": "tool_result", "tool_use_id": "tool-1", "content": "done"},
    ]

    assert extract_tool_use_blocks(blocks) == [blocks[1]]


def test_chat_session_append_methods_and_json_copy() -> None:
    session = ChatSession()

    session.append_user_text("hello")
    session.append_user_content_blocks([{"type": "text", "text": "from block"}])
    session.append_assistant_text("world")
    session.append_assistant_content_blocks([{"type": "text", "text": "from assistant block"}])
    session.append_assistant_tool_use_example("tool-1", "read_file", {"path": "file.txt"})
    session.append_tool_result_blocks(
        [{"type": "tool_result", "tool_use_id": "tool-1", "content": "ok"}]
    )

    payload = session.to_json_serializable()
    payload[0]["content"] = "changed"

    assert session.messages[0]["content"] == "hello"
    assert session.messages[1]["content"][0]["text"] == "from block"
    assert session.messages[2]["content"] == "world"
    assert session.messages[3]["content"][0]["text"] == "from assistant block"
    assert session.messages[4]["content"][0]["name"] == "read_file"
    assert session.messages[5]["content"][0]["content"] == "ok"


def test_chat_session_append_assistant_api_content_converts_and_stores_blocks() -> None:
    session = ChatSession()
    api_content = [SimpleNamespace(type="text", text="hello")]

    blocks = session.append_assistant_api_content(api_content)

    assert blocks == [{"type": "text", "text": "hello"}]
    assert session.messages == [{"role": "assistant", "content": blocks}]
