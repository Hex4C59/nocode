"""Tests for image sniffing and user-content block construction."""

from __future__ import annotations

import base64

import pytest

from nocode.messages.image import (
    build_user_content_blocks,
    make_image_block,
    make_text_block,
    sniff_media_type,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"\x89PNG\r\n\x1a\nrest", "image/png"),
        (b"\xff\xd8\xffrest", "image/jpeg"),
        (b"GIF87arest", "image/gif"),
        (b"GIF89arest", "image/gif"),
        (b"RIFFxxxxWEBPrest", "image/webp"),
        (b"II*\x00rest", "image/tiff"),
        (b"MM\x00*rest", "image/tiff"),
        (b"unknown", "image/png"),
    ],
)
def test_sniff_media_type(raw: bytes, expected: str) -> None:
    assert sniff_media_type(raw) == expected


def test_make_text_block_returns_expected_shape() -> None:
    assert make_text_block("hello") == {"type": "text", "text": "hello"}


def test_make_image_block_encodes_bytes_as_base64() -> None:
    raw = b"\x89PNG\r\n\x1a\npayload"

    block = make_image_block(raw)

    assert block["type"] == "image"
    assert block["source"]["media_type"] == "image/png"
    assert base64.standard_b64decode(block["source"]["data"]) == raw


def test_make_image_block_respects_explicit_media_type() -> None:
    block = make_image_block(b"raw-data", "image/webp")

    assert block["source"]["media_type"] == "image/webp"


def test_build_user_content_blocks_supports_text_and_images() -> None:
    blocks = build_user_content_blocks(
        text="  hello world  ",
        image_raw=[(b"\xff\xd8\xffrest", None)],
    )

    assert blocks[0] == {"type": "text", "text": "hello world"}
    assert blocks[1]["type"] == "image"
    assert blocks[1]["source"]["media_type"] == "image/jpeg"


def test_build_user_content_blocks_handles_images_only() -> None:
    blocks = build_user_content_blocks(text=None, image_raw=[(b"raw", "image/webp")])

    assert blocks == [make_image_block(b"raw", "image/webp")]


def test_build_user_content_blocks_returns_empty_for_empty_input() -> None:
    assert build_user_content_blocks(text="   ", image_raw=[]) == []
