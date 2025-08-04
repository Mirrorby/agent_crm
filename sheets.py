"""
Модуль для взаимодействия с Google Sheets. Использует OAuth2
для авторизации и предоставляет функции для добавления заказов,
обновления статуса и получения списка заказов.

Прежде чем использовать, убедитесь, что API Google Sheets включено
и файл `credentials.json` лежит в корне проекта. При первом
запуске будет создан файл `token.json` с токеном доступа.
"""
from __future__ import annotations

import os
import datetime as dt
from typing import Dict, List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Скоупы позволяют читать и записывать данные в таблицу Google
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_ID")


def _get_service() -> "Resource":
    """Авторизуется и возвращает объект service для API Google Sheets."""
    creds: Optional[Credentials] = None
    token_path = os.path.join(os.path.dirname(__file__), "token.json")
    creds_path = os.path.join(os.path.dirname(__file__), "credentials.json")

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())
    service = build("sheets", "v4", credentials=creds)
    return service


def append_order(order_data: Dict[str, str], items: List[Dict[str, str]]) -> None:
    """
    Добавляет новый заказ в таблицу.

    order_data: словарь с полями, общими для всех товаров в заказе,
    например ID заказа, статус, дата, канал продаж, ФИО и т.д.

    items: список словарей с полями одного товара: артикул, количество,
    сумма заказа, сумма закупа, поставщик, ссылка на фото, комментарий.
    Каждая запись создаёт отдельную строку в таблице; общие поля
    дублируются.
    """
    service = _get_service()
    values: List[List[str]] = []
    for item in items:
        row = [
            order_data.get("id", ""),
            order_data.get("status", "оформлен"),
            order_data.get("date", dt.datetime.now().strftime("%Y-%m-%d %H:%M")),
            item.get("sku", ""),
            order_data.get("channel", ""),
            item.get("supplier", ""),
            item.get("photo", ""),
            item.get("quantity", ""),
            item.get("order_sum", ""),
            item.get("purchase_sum", ""),
            order_data.get("percent", ""),
            order_data.get("extra_costs", ""),
            order_data.get("profit", ""),
            order_data.get("accruals", ""),
            order_data.get("customer_name", ""),
            order_data.get("phone", ""),
            order_data.get("messenger", ""),
            order_data.get("address", ""),
            order_data.get("logistics", ""),
            item.get("comment", ""),
        ]
        values.append(row)

    # Найдём следующую свободную строку в колонке A
    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=SPREADSHEET_ID, range="Orders!A:A")
            .execute()
        )
        existing = result.get("values", [])
        next_row = len(existing) + 1
    except HttpError as err:
        print(f"Ошибка при чтении таблицы: {err}")
        return

    # Записываем сразу несколько строк
    try:
        range_ = f"Orders!A{next_row}:T{next_row + len(values) - 1}"
        body = {"values": values}
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_,
            valueInputOption="RAW",
            body=body,
        ).execute()
    except HttpError as err:
        print(f"Ошибка при записи таблицы: {err}")


def update_status(order_id: str, new_status: str) -> None:
    """Обновляет статус всех строк заказа по ID."""
    service = _get_service()
    try:
        # Считываем все строки заказов
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=SPREADSHEET_ID, range="Orders!A:T")
            .execute()
        )
        rows = result.get("values", [])
        updates: List[Tuple[int, List[str]]] = []
        for idx, row in enumerate(rows, start=1):
            if row and row[0] == order_id:
                # заменяем статус (столбец B, индекс 1)
                while len(row) < 2:
                    row.append("")
                row[1] = new_status
                updates.append((idx, row))
        # производим обновление
        for idx, row in updates:
            range_ = f"Orders!A{idx}:T{idx}"
            body = {"values": [row]}
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=range_,
                valueInputOption="RAW",
                body=body,
            ).execute()
    except HttpError as err:
        print(f"Ошибка при обновлении статуса: {err}")


def get_orders(status: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Возвращает список заказов. Если указан status, фильтрует по статусу.

    Возвращаемая структура представляет собой список словарей с
    агрегированными данными одного заказа (суммарное количество
    позиций, статус и т.д.).
    """
    service = _get_service()
    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=SPREADSHEET_ID, range="Orders!A:T")
            .execute()
        )
        rows = result.get("values", [])
    except HttpError as err:
        print(f"Ошибка при чтении заказов: {err}")
        return []
    orders: Dict[str, Dict[str, str]] = {}
    for row in rows:
        if not row or len(row) < 2:
            continue
        oid = row[0]
        st = row[1] if len(row) > 1 else ""
        if status and st != status:
            continue
        if oid not in orders:
            orders[oid] = {
                "id": oid,
                "status": st,
                "date": row[2] if len(row) > 2 else "",
                "customer_name": row[14] if len(row) > 14 else "",
                "items": [],
            }
        orders[oid]["items"].append(
            {
                "sku": row[3] if len(row) > 3 else "",
                "quantity": row[7] if len(row) > 7 else "",
                "order_sum": row[8] if len(row) > 8 else "",
                "purchase_sum": row[9] if len(row) > 9 else "",
                "supplier": row[5] if len(row) > 5 else "",
            }
        )
    return list(orders.values())