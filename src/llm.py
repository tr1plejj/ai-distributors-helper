"""
LLM-слой ассистента.

Модель выбирает один из разрешённых инструментов, код выполняет расчёты,
а затем модель формулирует финальный ответ на основе результата инструмента.
"""
from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

try:
    from src.cleaning import PreparedData
    from src.prompts import load_instructions_for_tool, load_system_prompt
    from src.tools import TOOLS, parse_tool_arguments, run_tool
except ModuleNotFoundError:
    from cleaning import PreparedData
    from prompts import load_instructions_for_tool, load_system_prompt
    from tools import TOOLS, parse_tool_arguments, run_tool


DEFAULT_MODEL = "gpt-5.4-mini"


def answer_question(question: str, data: PreparedData) -> str:
    """Отвечает на вопрос пользователя через OpenAI function calling."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY не задан. Добавьте ключ в .env")

    client = OpenAI()
    system_prompt = load_system_prompt()
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    first_response = client.responses.create(
        model=model,
        instructions=system_prompt,
        input=question,
        tools=TOOLS,
        tool_choice="auto",
        parallel_tool_calls=False,
    )

    function_calls = _get_function_calls(first_response)

    if not function_calls:
        return first_response.output_text

    tool_outputs = []
    selected_tool_name = _get_attr(function_calls[0], "name")

    for function_call in function_calls:
        arguments = parse_tool_arguments(_get_attr(function_call, "arguments"))
        tool_name = _get_attr(function_call, "name")
        output = run_tool(tool_name, arguments, data)
        tool_outputs.append(
            {
                "type": "function_call_output",
                "call_id": _get_attr(function_call, "call_id"),
                "output": output,
            }
        )

    final_response = client.responses.create(
        model=model,
        instructions=load_instructions_for_tool(selected_tool_name),
        input=[
            {"role": "user", "content": question},
            *_response_items(first_response),
            *tool_outputs,
        ],
        tools=TOOLS,
        parallel_tool_calls=False,
    )

    return final_response.output_text


def _get_function_calls(response: Any) -> list[Any]:
    return [item for item in getattr(response, "output", []) if _get_attr(item, "type") == "function_call"]


def _response_items(response: Any) -> list[Any]:
    return [_to_plain_item(item) for item in getattr(response, "output", [])]


def _get_attr(item: Any, name: str) -> Any:
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def _to_plain_item(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump(exclude_none=True)
    if hasattr(item, "dict"):
        return item.dict(exclude_none=True)
    return {
        "type": _get_attr(item, "type"),
        "call_id": _get_attr(item, "call_id"),
        "name": _get_attr(item, "name"),
        "arguments": _get_attr(item, "arguments"),
    }
