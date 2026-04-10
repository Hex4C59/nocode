"""Image and user-content helpers for the local Anthropic-shaped message model."""

from __future__ import annotations

import base64

from nocode.messages.types import ContentBlock, ImageBlock, ImageSourceBase64, TextBlock


def sniff_media_type(raw: bytes) -> str:
    """Guess an `image/*` MIME type from magic bytes."""
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


def make_text_block(text: str) -> TextBlock:
    return {"type": "text", "text": text}


def make_image_block(raw: bytes, media_type: str | None = None) -> ImageBlock:
    resolved_media_type = media_type or sniff_media_type(raw)
    data = base64.standard_b64encode(raw).decode("ascii")
    source: ImageSourceBase64 = {
        "type": "base64",
        "media_type": resolved_media_type,
        "data": data,
    }
    return {"type": "image", "source": source}


def build_user_content_blocks(
    *,
    text: str | None,
    image_raw: list[tuple[bytes, str | None]],
) -> list[ContentBlock]:
    """Build one user message from optional text plus zero or more images."""
    blocks: list[ContentBlock] = []
    if text and text.strip():
        blocks.append(make_text_block(text.strip()))
    for raw, media_type in image_raw:
        blocks.append(make_image_block(raw, media_type))
    return blocks
