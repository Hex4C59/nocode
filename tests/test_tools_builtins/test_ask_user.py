"""Tests for the `ask_user` builtin tool handler."""

from __future__ import annotations

import json

import pytest

from nocode.tools.builtins.ask_user import handler
from nocode.tools.types import UserQuestion


async def test_ask_user_calls_runtime_callback(runtime) -> None:
    asked: list[UserQuestion] = []

    async def fake_ask_user(question: UserQuestion) -> str:
        asked.append(question)
        return "yes"

    runtime.ask_user = fake_ask_user

    result = json.loads(
        await handler(
            runtime,
            {
                "question": "Continue?",
                "options": ["yes", "no"],
                "allow_multiple": False,
            },
        )
    )

    assert result == {"answer": "yes"}
    assert asked[0].question == "Continue?"
    assert asked[0].options == ["yes", "no"]


async def test_ask_user_requires_runtime_callback(runtime) -> None:
    with pytest.raises(RuntimeError, match="ask_user is not configured"):
        await handler(runtime, {"question": "Continue?"})
