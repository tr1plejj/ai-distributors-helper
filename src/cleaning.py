"""
Слой подготовки данных.

Функции здесь приводят сырые JSON/CSV/API-данные к dataclass-моделям.
Некритичные проблемы сохраняются в DataIssue, чтобы аналитика могла не терять полезный контекст.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VALID_ORDER_STATUSES = {"completed", "cancelled", "processing"}


@dataclass
class DataIssue:
    """Проблема качества данных, найденная при подготовке."""
    source: str
    record_id: int | None
    field: str
    message: str


@dataclass
class Client:
    """Клиент из clients.json после приведения типов."""
    id: int
    name: str
    city: str
    contact_person: str
    phone: str
    email: str
    birthday: date | None
    type: str
    notes: str


@dataclass
class Product:
    """Товар из Supabase или локального products.csv после приведения типов."""
    id: int
    sku: str
    name: str
    brand: str
    category: str
    purchase_price: float | None
    retail_price: float | None
    stock_quantity: int | None


@dataclass
class Order:
    """Заказ из Google Sheets CSV после приведения типов."""
    order_id: int
    date: date | None
    client_id: int | None
    product_id: int | None
    quantity: int | None
    total_amount: float | None
    status: str


@dataclass
class PreparedData:
    """Единый контейнер подготовленных данных и найденных проблем."""
    clients: list[Client]
    products: list[Product]
    orders: list[Order]
    issues: list[DataIssue]


def prepare_data(
    raw_clients: list[dict[str, Any]],
    raw_products: list[dict[str, Any]],
    raw_orders: list[dict[str, Any]],
) -> PreparedData:
    """Готовит все источники данных для аналитического слоя."""
    issues: list[DataIssue] = []
    clients = _clean_clients(raw_clients, issues)
    products = _clean_products(raw_products, issues)
    orders = _clean_orders(raw_orders, clients, products, issues)
    return PreparedData(clients=clients, products=products, orders=orders, issues=issues)


def _clean_clients(raw_clients: list[dict[str, Any]], issues: list[DataIssue]) -> list[Client]:
    clients: list[Client] = []

    for raw_client in raw_clients:
        client_id = _to_int(raw_client.get("id"))

        if client_id is None:
            issues.append(DataIssue("clients", None, "id", "Не удалось прочитать id клиента"))
            continue

        email = _to_str(raw_client.get("email"))

        if email and not EMAIL_RE.match(email):
            issues.append(DataIssue("clients", client_id, "email", "Некорректный email"))

        clients.append(
            Client(
                id=client_id,
                name=_to_str(raw_client.get("name")),
                city=_to_str(raw_client.get("city")),
                contact_person=_to_str(raw_client.get("contact_person")),
                phone=_to_str(raw_client.get("phone")),
                email=email,
                birthday=_to_date(raw_client.get("birthday")),
                type=_to_str(raw_client.get("type")),
                notes=_to_str(raw_client.get("notes")),
            )
        )

    return clients


def _clean_products(raw_products: list[dict[str, Any]], issues: list[DataIssue]) -> list[Product]:
    products: list[Product] = []

    for raw_product in raw_products:
        product_id = _to_int(raw_product.get("id"))

        if product_id is None:
            issues.append(DataIssue("products", None, "id", "Не удалось прочитать id товара"))
            continue

        stock_quantity = _to_int(raw_product.get("stock_quantity"))

        if stock_quantity is None:
            issues.append(DataIssue("products", product_id, "stock_quantity", "Пустой или некорректный остаток"))

        products.append(
            Product(
                id=product_id,
                sku=_to_str(raw_product.get("sku")),
                name=_to_str(raw_product.get("name")),
                brand=_to_str(raw_product.get("brand")),
                category=_to_str(raw_product.get("category")),
                purchase_price=_to_float(raw_product.get("purchase_price")),
                retail_price=_to_float(raw_product.get("retail_price")),
                stock_quantity=stock_quantity,
            )
        )

    return products


def _clean_orders(
    raw_orders: list[dict[str, Any]],
    clients: list[Client],
    products: list[Product],
    issues: list[DataIssue],
) -> list[Order]:
    orders: list[Order] = []
    client_ids = {client.id for client in clients}
    product_ids = {product.id for product in products}

    for raw_order in raw_orders:
        order_id = _to_int(raw_order.get("order_id"))

        if order_id is None:
            issues.append(DataIssue("orders", None, "order_id", "Не удалось прочитать id заказа"))
            continue

        order_date = _to_date(raw_order.get("date"))
        client_id = _to_int(raw_order.get("client_id"))
        product_id = _to_int(raw_order.get("product_id"))
        quantity = _to_int(raw_order.get("quantity"))
        total_amount = _to_float(raw_order.get("total_amount"))
        status = _to_str(raw_order.get("status")).lower()

        if order_date is None:
            issues.append(DataIssue("orders", order_id, "date", "Пустая или некорректная дата заказа"))

        if client_id is None:
            issues.append(DataIssue("orders", order_id, "client_id", "Пустой или некорректный id клиента"))
        elif client_id not in client_ids:
            issues.append(DataIssue("orders", order_id, "client_id", "Клиент из заказа не найден в clients.json"))

        if product_id is None:
            issues.append(DataIssue("orders", order_id, "product_id", "Пустой или некорректный id товара"))
        elif product_id not in product_ids:
            issues.append(DataIssue("orders", order_id, "product_id", "Товар из заказа не найден в products"))

        if quantity is None:
            issues.append(DataIssue("orders", order_id, "quantity", "Пустое или некорректное количество"))
        elif quantity < 0:
            issues.append(DataIssue("orders", order_id, "quantity", "Отрицательное количество"))

        if total_amount is None:
            issues.append(DataIssue("orders", order_id, "total_amount", "Пустая или некорректная сумма заказа"))
        elif total_amount < 0:
            issues.append(DataIssue("orders", order_id, "total_amount", "Отрицательная сумма заказа"))

        if not status:
            issues.append(DataIssue("orders", order_id, "status", "Пустой статус заказа"))
        elif status not in VALID_ORDER_STATUSES:
            issues.append(DataIssue("orders", order_id, "status", "Неизвестный статус заказа"))

        orders.append(
            Order(
                order_id=order_id,
                date=order_date,
                client_id=client_id,
                product_id=product_id,
                quantity=quantity,
                total_amount=total_amount,
                status=status,
            )
        )

    return orders


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


if __name__ == "__main__":
    from dotenv import load_dotenv

    try:
        from src.data_sources import fetch_orders, fetch_products, load_clients
    except ModuleNotFoundError:
        from data_sources import fetch_orders, fetch_products, load_clients

    load_dotenv()

    data = prepare_data(load_clients(), fetch_products(), fetch_orders())

    print(f"clients: {len(data.clients)}")
    print(f"products: {len(data.products)}")
    print(f"orders: {len(data.orders)}")
    print(f"issues: {len(data.issues)}")

    for issue in data.issues:
        print(f"- {issue.source} #{issue.record_id}: {issue.field} - {issue.message}")
