"""Ask the user a focused question through the active runtime callback."""

from __future__ import annotations

from nocode.tools._helpers import serialize_json
from nocode.tools.types import ToolRuntime, ToolSpec, UserQuestion


async def handler(runtime: ToolRuntime, input_obj: dict[str, object]) -> str:
    if runtime.ask_user is None:
        raise RuntimeError("ask_user is not configured in runtime")
    question = UserQuestion(
        question=str(input_obj["question"]),
        options=[str(option) for option in input_obj.get("options", [])],
        allow_multiple=bool(input_obj.get("allow_multiple", False)),
    )
    answer = await runtime.ask_user(question)
    return serialize_json({"answer": answer})


SPEC = ToolSpec(
    name="ask_user",
    description="Ask the user a focused question and wait for a text answer.",
    input_schema={
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "options": {
                "type": "array",
                "items": {"type": "string"},
            },
            "allow_multiple": {"type": "boolean"},
        },
        "required": ["question"],
    },
    handler=handler,
)
