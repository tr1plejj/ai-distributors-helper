"""
Базовый каркас работы с тремя источниками данных.
Это СТАРТОВАЯ ТОЧКА — дорабатывай под свою архитектуру.

Реализованы только сигнатуры и комментарии — внутри каждой функции `pass`.
Твоя задача — реализовать. Можно полностью переписать структуру, если хочется.
"""
import json
import os
from pathlib import Path
from typing import Any

import requests


def load_clients() -> list[dict[str, Any]]:
    """Читает clients.json из репозитория."""
    pass


def fetch_products() -> list[dict[str, Any]]:
    """
    Запрашивает таблицу products из Supabase REST API.
    Доступ: SUPABASE_URL и SUPABASE_ANON_KEY из .env

    Hint: GET {SUPABASE_URL}/rest/v1/products?select=*
    Header: apikey: {SUPABASE_ANON_KEY}
    """
    pass


def fetch_orders() -> list[dict[str, Any]]:
    """
    Тянет публичный CSV из Google Sheets (URL в .env как ORDERS_CSV_URL).
    Распарсивает в список словарей.
    """
    pass


if __name__ == "__main__":
    # Быстрая sanity-проверка, что доступы работают.
    from dotenv import load_dotenv
    load_dotenv()

    clients = load_clients()
    products = fetch_products()
    orders = fetch_orders()

    print(f"clients: {len(clients) if clients else 'НЕ РЕАЛИЗОВАНО'}")
    print(f"products: {len(products) if products else 'НЕ РЕАЛИЗОВАНО'}")
    print(f"orders: {len(orders) if orders else 'НЕ РЕАЛИЗОВАНО'}")
