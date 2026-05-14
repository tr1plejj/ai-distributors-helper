"""
Entry point. Реши сам — это CLI, бот или что-то ещё.
Удали этот заглушечный код и напиши своё.
"""
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    print("Hello from the starter. Replace me with your solution.")
    # Подсказка по структуре (можешь отказаться):
    # 1. Загрузить данные из трёх источников (см. src/data_sources.py)
    # 2. Получить вопрос от пользователя (CLI prompt / Telegram update)
    # 3. Определить, к какому из 3 сценариев он относится (классификатор)
    # 4. Подобрать релевантный контекст
    # 5. Вызвать LLM с подготовленным промптом
    # 6. Вернуть ответ


if __name__ == "__main__":
    main()
