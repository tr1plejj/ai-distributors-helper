"""
Загрузка промптов из папки prompts.
"""
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"
TOOL_PROMPTS = {
    "get_client_profile": "client_profile",
    "get_stock_risks": "stock_risks",
    "get_sales_summary": "sales_summary",
}


def load_prompt(name: str) -> str:
    """Читает markdown-промпт по имени файла без расширения."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8").strip()


def load_system_prompt() -> str:
    """Читает общий системный промпт."""
    return load_prompt("system")


def load_instructions_for_tool(tool_name: str) -> str:
    """Собирает общий промпт и сценарную инструкцию для выбранного инструмента."""
    scenario_prompt = TOOL_PROMPTS.get(tool_name)

    if scenario_prompt is None:
        return load_system_prompt()

    return "\n\n".join([load_system_prompt(), load_prompt(scenario_prompt)])
