"""Fetch a web page and return its response text."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

import requests

from nocode.tools._helpers import serialize_json, truncate_text
from nocode.tools.types import ToolRuntime, ToolSpec


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
    return serialize_json(
        {
            "url": response.url,
            "status_code": response.status_code,
            "content": truncate_text(text, limit=max_chars),
        }
    )


async def handler(_runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    url = str(input_obj["url"])
    max_chars = int(input_obj.get("max_chars", 8000))
    return await asyncio.to_thread(_fetch_url_sync, url, max_chars)


SPEC = ToolSpec(
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
    handler=handler,
)
