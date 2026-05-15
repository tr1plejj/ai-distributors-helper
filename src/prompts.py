"""
Загрузка промптов из папки prompts.
"""
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"


def load_prompt(name: str) -> str:
    """Читает markdown-промпт по имени файла без расширения."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8").strip()
