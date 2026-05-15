"""
Базовый каркас работы с тремя источниками данных.
"""
import csv
import json
import os
from io import StringIO
from pathlib import Path
from typing import Any

import requests


BASE_DIR = Path(__file__).resolve().parent.parent


def load_clients() -> list[dict[str, Any]]:
    """Читает clients.json из репозитория."""
    path = BASE_DIR / "test-data" / "clients.json"
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def fetch_products() -> list[dict[str, Any]]:
    """
    Запрашивает таблицу products из Supabase REST API.
    Доступ: SUPABASE_URL и SUPABASE_ANON_KEY из .env

    Hint: GET {SUPABASE_URL}/rest/v1/products?select=*
    Header: apikey: {SUPABASE_ANON_KEY}
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")

    if supabase_url and supabase_key:
        try:
            response = requests.get(
                f"{supabase_url.rstrip('/')}/rest/v1/products?select=*",
                headers={"apikey": supabase_key},
                timeout=15,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError):
            pass

    path = BASE_DIR / "test-data" / "products.csv"
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def fetch_orders() -> list[dict[str, Any]]:
    """
    Тянет публичный CSV из Google Sheets (URL в .env как ORDERS_CSV_URL).
    Распарсивает в список словарей.
    """
    orders_csv_url = os.getenv("ORDERS_CSV_URL")

    if orders_csv_url:
        try:
            response = requests.get(orders_csv_url, timeout=15)
            response.raise_for_status()
            return list(csv.DictReader(StringIO(response.text)))
        except requests.RequestException:
            pass

    path = BASE_DIR / "test-data" / "orders.csv"
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


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
