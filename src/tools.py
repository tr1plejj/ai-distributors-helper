"""
Инструменты, которые LLM может вызывать через function calling.

Слой связывает JSON schema для модели с детерминированными функциями из analytics.py.
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date
from typing import Any

try:
    from src.analytics import get_client_profile, get_sales_summary, get_stock_risks
    from src.cleaning import PreparedData
except ModuleNotFoundError:
    from analytics import get_client_profile, get_sales_summary, get_stock_risks
    from cleaning import PreparedData


TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "get_client_profile",
        "description": (
            "Use when the user asks about a specific client, their order history, preferences, "
            "notes, last order, or what to offer them next."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Client id, name, contact person, or the original user phrase used to find the client.",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_stock_risks",
        "description": (
            "Use when the user asks which products may run out, what should be replenished, "
            "or which stock levels are risky compared with recent sales."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Sales history period in days. Use 90 if the user does not specify a period.",
                }
            },
            "required": ["days"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_sales_summary",
        "description": (
            "Use when the user asks for a sales summary, revenue, top clients, top products, "
            "order statuses, anomalies, or what happened in sales for a period. "
            "If the user asks for all revenue or the whole available history, pass days as null."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": ["integer", "null"],
                    "description": (
                        "Sales summary period in days. Use 30 if the user does not specify a period. "
                        "Use null for all available history."
                    ),
                }
            },
            "required": ["days"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def run_tool(name: str, arguments: dict[str, Any], data: PreparedData) -> str:
    """Выполняет разрешённый инструмент и возвращает JSON-строку с фактами."""
    if name == "get_client_profile":
        result = get_client_profile(data, str(arguments.get("query", "")))
    elif name == "get_stock_risks":
        result = get_stock_risks(data, days=_safe_days(arguments.get("days"), default=90))
    elif name == "get_sales_summary":
        result = get_sales_summary(data, days=_safe_optional_days(arguments.get("days"), default=30))
    else:
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)

    return json.dumps(_to_jsonable(result), ensure_ascii=False, indent=2)


def parse_tool_arguments(raw_arguments: str | dict[str, Any] | None) -> dict[str, Any]:
    """Превращает arguments из ответа модели в словарь."""
    if raw_arguments is None:
        return {}
    if isinstance(raw_arguments, dict):
        return raw_arguments
    try:
        return json.loads(raw_arguments)
    except json.JSONDecodeError:
        return {}


def _safe_days(value: Any, default: int) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError):
        days = default
    return max(7, min(days, 365))


def _safe_optional_days(value: Any, default: int) -> int | None:
    if value is None:
        return None
    return _safe_days(value, default)


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, date):
        return value.isoformat()
    return value
