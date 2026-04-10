# 会话与消息：与 Anthropic Messages API 的 messages[] 形状对齐；ChatSession 为唯一真实来源。
from __future__ import annotations

import base64
import copy
import json
from collections.abc import Sequence
from typing import Any, Literal, NotRequired, TypedDict, cast

from rich.markup import escape

# --- Content blocks (对齐 API type 字段) ---


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


def sniff_media_type(raw: bytes) -> str:
    """根据魔数推断 image/*，未知时退回 image/png。"""
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if raw[:4] == b"RIFF" and len(raw) >= 12 and raw[8:12] == b"WEBP":
        return "image/webp"
    if raw.startswith(b"II*\x00") or raw.startswith(b"MM\x00*"):
        return "image/tiff"
    return "image/png"


def make_image_block(raw: bytes, media_type: str | None = None) -> ImageBlock:
    mt = media_type or sniff_media_type(raw)
    b64 = base64.standard_b64encode(raw).decode("ascii")
    src: ImageSourceBase64 = {"type": "base64", "media_type": mt, "data": b64}
    return {"type": "image", "source": src}


def make_text_block(text: str) -> TextBlock:
    return {"type": "text", "text": text}


def _preview_text(text: str, limit: int = 120) -> str:
    compact = " ".join(text.splitlines())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def _preview_json(data: object, limit: int = 120) -> str:
    raw = json.dumps(data, ensure_ascii=False)
    return _preview_text(raw, limit=limit)


def build_user_content_blocks(
    *,
    text: str | None,
    image_raw: list[tuple[bytes, str | None]],
) -> list[ContentBlock]:
    """
    组装单条 user 消息的 content 列表：可选 text + 若干 image。
    text 为 None 或仅空白且无任何图时返回空列表（调用方勿提交空 user）。
    """
    blocks: list[ContentBlock] = []
    if text and text.strip():
        blocks.append(make_text_block(text.strip()))
    for raw, mt in image_raw:
        blocks.append(make_image_block(raw, mt))
    return blocks


def build_assistant_content_blocks(api_content: Sequence[Any]) -> list[ContentBlock]:
    """
    将 Anthropic `Message.content` 映射为本项目的 `ContentBlock`。

    第一版仅保留 `text` 与 `tool_use`，其余块先忽略，避免把 SDK 专有结构直接写入会话。
    """
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
    """从一条助手消息里提取全部 `tool_use`。"""
    out: list[ToolUseBlock] = []
    for block in blocks:
        if block["type"] == "tool_use":
            out.append(block)
    return out


class ChatSession:
    """
    一轮（无工具）：user → assistant。
    多跳（工具）：assistant 含 tool_use → user 含 tool_result → 再请求（见 05）。
    """

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
        """将 Anthropic `Message.content` 转为本地块后写入会话，并返回该块列表。"""
        blocks = build_assistant_content_blocks(api_content)
        self.append_assistant_content_blocks(blocks)
        return blocks

    def append_tool_result_blocks(self, blocks: list[ToolResultBlock]) -> None:
        """助手 tool_use 之后追加 tool_result 用户消息（05 调用）。"""
        self.messages.append(
            {"role": "user", "content": cast(list[ContentBlock], blocks)}
        )

    def append_assistant_tool_use_example(
        self, tool_use_id: str, name: str, input_obj: dict[str, Any]
    ) -> None:
        """占位：单条仅含 tool_use 的助手消息（05 填真实流式组装）。"""
        block: ToolUseBlock = {
            "type": "tool_use",
            "id": tool_use_id,
            "name": name,
            "input": input_obj,
        }
        self.messages.append({"role": "assistant", "content": [block]})

    def to_json_serializable(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.messages)  # type: ignore[return-value]


def format_api_message_markup(msg: ApiMessage) -> str:
    """将一条 API 形消息投影为一行 Rich markup（TUI RichLog）。"""
    role = msg["role"]
    label = "你" if role == "user" else "助手"
    style = "bold green" if role == "user" else "bold blue"
    content = msg["content"]
    if isinstance(content, str):
        return f"[{style}]{label}[/]: {escape(content)}"
    parts: list[str] = []
    for block in content:
        if block["type"] == "text":
            parts.append(escape(block["text"]))
        elif block["type"] == "image":
            parts.append(f"[图·{escape(block['source']['media_type'])}]")
        elif block["type"] == "tool_use":
            preview = _preview_json(block["input"])
            parts.append(f"[工具 {escape(block['name'])}] {escape(preview)}")
        elif block["type"] == "tool_result":
            preview = _preview_text(block["content"])
            label = "tool_error" if block.get("is_error") else "tool_result"
            parts.append(f"[{label}] {escape(preview)}")
    body = " ".join(parts) if parts else "(空)"
    return f"[{style}]{label}[/]: {body}"


def _demo_sample() -> ChatSession:
    """手写样例：多轮对话 + 一条含 image 的用户消息 + 迷你 tool 链。"""
    s = ChatSession()
    s.append_user_text("你好")
    s.append_assistant_text("你好，有什么可以帮你？")

    png_1x1 = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    blocks: list[ContentBlock] = [
        make_text_block("请看这张图"),
        make_image_block(png_1x1, "image/png"),
    ]
    s.append_user_content_blocks(blocks)
    s.append_assistant_text("收到了一张图。")

    s.append_assistant_tool_use_example("toolu_01", "get_weather", {"city": "SF"})
    tr: ToolResultBlock = {
        "type": "tool_result",
        "tool_use_id": "toolu_01",
        "content": '{"temp": 18}',
    }
    s.append_tool_result_blocks([tr])
    s.append_assistant_text("旧金山当前约 18°C。")
    return s


if __name__ == "__main__":
    demo = _demo_sample()
    print(json.dumps(demo.to_json_serializable(), indent=2, ensure_ascii=False))
