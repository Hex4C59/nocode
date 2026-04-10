"""Tests for Rich markup projection of API-shaped chat messages."""

from __future__ import annotations

from nocode.messages.format import format_api_message_markup


def test_format_api_message_markup_for_user_text_message() -> None:
    rendered = format_api_message_markup({"role": "user", "content": "hello"})

    assert rendered == "[bold green]你[/]: hello"


def test_format_api_message_markup_for_assistant_text_message() -> None:
    rendered = format_api_message_markup({"role": "assistant", "content": "hello"})

    assert rendered == "[bold blue]助手[/]: hello"


def test_format_api_message_markup_for_tool_use_block() -> None:
    rendered = format_api_message_markup(
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool-1",
                    "name": "read_file",
                    "input": {"path": "src/nocode/cli.py"},
                }
            ],
        }
    )

    assert "[工具 read_file]" in rendered
    assert '"path": "src/nocode/cli.py"' in rendered


def test_format_api_message_markup_for_tool_result_block() -> None:
    rendered = format_api_message_markup(
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool-1",
                    "content": "done",
                    "is_error": True,
                }
            ],
        }
    )

    assert "[tool_error] done" in rendered


def test_format_api_message_markup_for_image_block() -> None:
    rendered = format_api_message_markup(
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": "Zm9v",
                    },
                }
            ],
        }
    )

    assert "[图·image/png]" in rendered


def test_format_api_message_markup_uses_empty_marker_for_empty_content() -> None:
    rendered = format_api_message_markup({"role": "assistant", "content": []})

    assert rendered == "[bold blue]助手[/]: (空)"
