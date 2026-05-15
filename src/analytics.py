"""
Слой бизнес-аналитики.
Функции принимают подготовленные данные и возвращают факты для трёх сценариев ассистента.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

try:
    from src.cleaning import Client, Order, PreparedData, Product
except ModuleNotFoundError:
    from cleaning import Client, Order, PreparedData, Product


@dataclass
class NameQuantity:
    name: str
    quantity: int


@dataclass
class ProductSales:
    product_id: int
    name: str
    brand: str
    category: str
    quantity: int
    revenue: float


@dataclass
class ClientSales:
    client_id: int
    name: str
    orders_count: int
    revenue: float


@dataclass
class OrderSummary:
    order_id: int
    date: str | None
    product_id: int | None
    product_name: str
    quantity: int | None
    total_amount: float | None
    status: str


@dataclass
class StockRiskItem:
    product_id: int
    sku: str
    name: str
    brand: str
    category: str
    stock_quantity: int
    sold_for_period: int
    avg_daily_sales: float
    estimated_days_left: float | None
    risk_score: float


@dataclass
class ClientProfile:
    found: bool
    query: str
    client: Client | None
    orders_count: int
    total_revenue: float
    average_check: float
    last_order: OrderSummary | None
    top_brands: list[NameQuantity]
    top_categories: list[NameQuantity]
    top_products: list[ProductSales]


@dataclass
class StockRisks:
    period_days: int
    period_start: str | None
    period_end: str | None
    items: list[StockRiskItem]


@dataclass
class SalesSummary:
    period_days: int
    period_start: str | None
    period_end: str | None
    revenue: float
    orders_count: int
    status_counts: dict[str, int]
    top_clients: list[ClientSales]
    top_products: list[ProductSales]
    stock_risks: list[StockRiskItem]
    data_issues: list[dict[str, Any]]


def get_valid_completed_orders(data: PreparedData) -> list[Order]:
    """
    Возвращает completed-заказы, которые безопасно использовать в расчётах.
    Проблемные заказы остаются в PreparedData и DataIssue, но не участвуют в выручке и топах.
    """
    return [
        order
        for order in data.orders
        if order.status == "completed"
        and order.date is not None
        and order.client_id is not None
        and order.product_id is not None
        and order.quantity is not None
        and order.quantity > 0
        and order.total_amount is not None
        and order.total_amount > 0
    ]


def get_client_profile(data: PreparedData, query: str) -> ClientProfile:
    """
    Собирает факты по клиенту: заметки, историю покупок, топ брендов/категорий и последний заказ.
    Клиент ищется по id или фрагменту имени/контактного лица/города/типа.
    """
    client = find_client(data.clients, query)

    if client is None:
        return ClientProfile(
            found=False,
            query=query,
            client=None,
            orders_count=0,
            total_revenue=0,
            average_check=0,
            last_order=None,
            top_brands=[],
            top_categories=[],
            top_products=[],
        )

    products_by_id = _products_by_id(data.products)
    client_orders = [order for order in get_valid_completed_orders(data) if order.client_id == client.id]
    client_orders.sort(key=lambda order: order.date or date.min, reverse=True)

    total_revenue = round(sum(order.total_amount or 0 for order in client_orders), 2)
    average_check = round(total_revenue / len(client_orders), 2) if client_orders else 0

    return ClientProfile(
        found=True,
        query=query,
        client=client,
        orders_count=len(client_orders),
        total_revenue=total_revenue,
        average_check=average_check,
        last_order=_order_to_summary(client_orders[0], products_by_id) if client_orders else None,
        top_brands=_top_product_field(client_orders, products_by_id, "brand"),
        top_categories=_top_product_field(client_orders, products_by_id, "category"),
        top_products=_top_products(client_orders, products_by_id),
    )


def get_stock_risks(data: PreparedData, days: int = 90, limit: int = 10) -> StockRisks:
    """
    Находит товары, где текущий остаток низкий относительно продаж за выбранный период.
    Это не прогноз спроса, а простой сигнал риска для ручной проверки менеджером.
    """
    products_by_id = _products_by_id(data.products)
    completed_orders = get_valid_completed_orders(data)
    dated_orders = [order for order in completed_orders if order.date is not None]

    if not dated_orders:
        return StockRisks(period_days=days, period_start=None, period_end=None, items=[])

    period_end = max(order.date for order in dated_orders if order.date is not None)
    period_start = period_end - timedelta(days=days)
    recent_orders = [order for order in dated_orders if order.date and order.date >= period_start]
    sold_by_product = _sold_quantity_by_product(recent_orders)

    risks: list[StockRiskItem] = []

    for product_id, sold_quantity in sold_by_product.items():
        product = products_by_id.get(product_id)

        if product is None or product.stock_quantity is None:
            continue

        daily_sales = sold_quantity / days
        days_left = round(product.stock_quantity / daily_sales, 1) if daily_sales > 0 else None

        if product.stock_quantity <= 5 or product.stock_quantity < sold_quantity:
            risks.append(
                StockRiskItem(
                    product_id=product.id,
                    sku=product.sku,
                    name=product.name,
                    brand=product.brand,
                    category=product.category,
                    stock_quantity=product.stock_quantity,
                    sold_for_period=sold_quantity,
                    avg_daily_sales=round(daily_sales, 2),
                    estimated_days_left=days_left,
                    risk_score=_stock_risk_score(product.stock_quantity, sold_quantity, days_left),
                )
            )

    risks.sort(key=lambda item: item.risk_score, reverse=True)

    return StockRisks(period_days=days, period_start=period_start.isoformat(), period_end=period_end.isoformat(), items=risks[:limit])


def get_sales_summary(data: PreparedData, days: int = 30) -> SalesSummary:
    """
    Возвращает управленческую сводку по продажам за период:
    выручку, статусы заказов, топ клиентов, топ товаров, риски склада и проблемы данных.
    """
    products_by_id = _products_by_id(data.products)
    clients_by_id = _clients_by_id(data.clients)
    completed_orders = get_valid_completed_orders(data)
    dated_orders = [order for order in completed_orders if order.date is not None]

    if not dated_orders:
        return SalesSummary(
            period_days=days,
            period_start=None,
            period_end=None,
            revenue=0,
            orders_count=0,
            status_counts=dict(Counter(order.status for order in data.orders)),
            top_clients=[],
            top_products=[],
            stock_risks=[],
            data_issues=[_issue_to_dict(issue) for issue in data.issues],
        )

    period_end = max(order.date for order in dated_orders if order.date is not None)
    period_start = period_end - timedelta(days=days)
    period_orders = [order for order in dated_orders if order.date and order.date >= period_start]
    revenue = round(sum(order.total_amount or 0 for order in period_orders), 2)

    return SalesSummary(
        period_days=days,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        revenue=revenue,
        orders_count=len(period_orders),
        status_counts=dict(Counter(order.status or "empty" for order in data.orders)),
        top_clients=_top_clients(period_orders, clients_by_id),
        top_products=_top_products(period_orders, products_by_id),
        stock_risks=get_stock_risks(data, days=days, limit=5).items,
        data_issues=[_issue_to_dict(issue) for issue in data.issues[:10]],
    )


def find_client(clients: list[Client], query: str) -> Client | None:
    """Ищет клиента по id из вопроса или по фрагменту текстовых полей."""
    query_text = query.lower().strip()
    numbers = re.findall(r"\d+", query_text)

    for number in numbers:
        client_id = int(number)
        for client in clients:
            if client.id == client_id:
                return client

    for client in clients:
        values = [client.name, client.contact_person, client.city, client.type]
        if any(query_text and query_text in value.lower() for value in values):
            return client

    return None


def _clients_by_id(clients: list[Client]) -> dict[int, Client]:
    return {client.id: client for client in clients}


def _products_by_id(products: list[Product]) -> dict[int, Product]:
    return {product.id: product for product in products}


def _sold_quantity_by_product(orders: list[Order]) -> dict[int, int]:
    result: dict[int, int] = defaultdict(int)

    for order in orders:
        if order.product_id is not None and order.quantity is not None:
            result[order.product_id] += order.quantity

    return dict(result)


def _top_clients(orders: list[Order], clients_by_id: dict[int, Client], limit: int = 5) -> list[ClientSales]:
    revenue_by_client: dict[int, float] = defaultdict(float)
    orders_by_client: dict[int, int] = defaultdict(int)

    for order in orders:
        if order.client_id is not None and order.total_amount is not None:
            revenue_by_client[order.client_id] += order.total_amount
            orders_by_client[order.client_id] += 1

    result = []

    for client_id, revenue in revenue_by_client.items():
        client = clients_by_id.get(client_id)
        result.append(
            ClientSales(
                client_id=client_id,
                name=client.name if client else "Неизвестный клиент",
                orders_count=orders_by_client[client_id],
                revenue=round(revenue, 2),
            )
        )

    result.sort(key=lambda item: item.revenue, reverse=True)
    return result[:limit]


def _top_products(orders: list[Order], products_by_id: dict[int, Product], limit: int = 5) -> list[ProductSales]:
    quantity_by_product: dict[int, int] = defaultdict(int)
    revenue_by_product: dict[int, float] = defaultdict(float)

    for order in orders:
        if order.product_id is not None and order.quantity is not None:
            quantity_by_product[order.product_id] += order.quantity
        if order.product_id is not None and order.total_amount is not None:
            revenue_by_product[order.product_id] += order.total_amount

    result = []

    for product_id, quantity in quantity_by_product.items():
        product = products_by_id.get(product_id)
        result.append(
            ProductSales(
                product_id=product_id,
                name=product.name if product else "Неизвестный товар",
                brand=product.brand if product else "",
                category=product.category if product else "",
                quantity=quantity,
                revenue=round(revenue_by_product[product_id], 2),
            )
        )

    result.sort(key=lambda item: item.quantity, reverse=True)
    return result[:limit]


def _top_product_field(orders: list[Order], products_by_id: dict[int, Product], field: str, limit: int = 3) -> list[NameQuantity]:
    counter: Counter[str] = Counter()

    for order in orders:
        product = products_by_id.get(order.product_id or 0)

        if product is None or order.quantity is None:
            continue

        value = getattr(product, field)

        if value:
            counter[value] += order.quantity

    return [NameQuantity(name=name, quantity=quantity) for name, quantity in counter.most_common(limit)]


def _stock_risk_score(stock_quantity: int, sold_quantity: int, days_left: float | None) -> float:
    score = sold_quantity - stock_quantity

    if stock_quantity <= 5:
        score += 10

    if days_left is not None and days_left <= 14:
        score += 10

    return round(score, 2)


def _order_to_summary(order: Order, products_by_id: dict[int, Product]) -> OrderSummary:
    product = products_by_id.get(order.product_id or 0)

    return OrderSummary(
        order_id=order.order_id,
        date=order.date.isoformat() if order.date else None,
        product_id=order.product_id,
        product_name=product.name if product else "Неизвестный товар",
        quantity=order.quantity,
        total_amount=order.total_amount,
        status=order.status,
    )


def _issue_to_dict(issue: Any) -> dict[str, Any]:
    return {
        "source": issue.source,
        "record_id": issue.record_id,
        "field": issue.field,
        "message": issue.message,
    }


if __name__ == "__main__":
    from dotenv import load_dotenv

    try:
        from src.cleaning import prepare_data
        from src.data_sources import fetch_orders, fetch_products, load_clients
    except ModuleNotFoundError:
        from cleaning import prepare_data
        from data_sources import fetch_orders, fetch_products, load_clients

    load_dotenv()

    data = prepare_data(load_clients(), fetch_products(), fetch_orders())
    client_profile = get_client_profile(data, "Lana")
    stock_risks = get_stock_risks(data)
    sales_summary = get_sales_summary(data)

    print(f"valid completed orders: {len(get_valid_completed_orders(data))}")
    print(f"client found: {client_profile.found}")
    print(f"client orders: {client_profile.orders_count}")
    print(f"stock risks: {len(stock_risks.items)}")
    print(f"sales revenue: {sales_summary.revenue}")
    print(f"data issues: {len(sales_summary.data_issues)}")
