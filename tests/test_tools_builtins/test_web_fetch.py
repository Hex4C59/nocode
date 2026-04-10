"""Tests for the `web_fetch` builtin tool handler."""

from __future__ import annotations

import json

import pytest

from nocode.tools.builtins import web_fetch as web_fetch_module
from nocode.tools.builtins.web_fetch import handler


class _FakeResponse:
    def __init__(self, *, url: str, status_code: int, text: str) -> None:
        self.url = url
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        return None


async def test_web_fetch_returns_response_payload(runtime, monkeypatch) -> None:
    def fake_get(url: str, timeout: int, headers: dict[str, str]) -> _FakeResponse:
        assert timeout == 20
        assert headers["User-Agent"] == "nocode/0.1"
        return _FakeResponse(url=url, status_code=200, text="  hello world  ")

    monkeypatch.setattr(web_fetch_module.requests, "get", fake_get)

    result = json.loads(await handler(runtime, {"url": "https://example.com"}))

    assert result == {
        "url": "https://example.com",
        "status_code": 200,
        "content": "hello world",
    }


async def test_web_fetch_rejects_non_http_urls(runtime) -> None:
    with pytest.raises(ValueError, match="url must start with http:// or https://"):
        await handler(runtime, {"url": "file:///tmp/example.txt"})
