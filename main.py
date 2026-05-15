"""
CLI entry point для AI-ассистента.
"""
import sys

from dotenv import load_dotenv

from src.cleaning import prepare_data
from src.data_sources import fetch_orders, fetch_products, load_clients
from src.llm import answer_question


def main() -> None:
    load_dotenv()

    question = " ".join(sys.argv[1:]).strip()
    data = prepare_data(load_clients(), fetch_products(), fetch_orders())

    if question:
        answer = answer_question(question, data)
        print(answer)
        return

    print("Введите вопрос. Для выхода: exit, quit или выход.")

    while True:
        question = input("\nВопрос: ").strip()

        if question.lower() in {"exit", "quit", "выход"}:
            break

        if not question:
            print("Пустой вопрос.")
            continue

        answer = answer_question(question, data)
        print(answer)


if __name__ == "__main__":
    main()
