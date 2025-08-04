"""
Flask-приложение, реализующее WebApp Telegram для управления заказами.

Через этот сервер пользователи в зависимости от своей роли могут:
  * оформить новый заказ (менеджер),
  * просмотреть список заказов по статусу (все роли),
  * изменить статус (сборщик/курьер/админ).

Сервер ожидает, что идентификатор пользователя Telegram (uid) будет
передан в параметре запроса `uid` либо будет получен через
Telegram WebApp. В реальном развёртывании uid можно извлекать из
``window.Telegram.WebApp.initDataUnsafe.user.id`` на фронтенде и
передавать его при запросах.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

from flask import (Flask, abort, jsonify, redirect, render_template,
                   request, url_for)

import sheets

# Создаём приложение Flask
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-key")

# Карта ролей: uid -> роль
# В реальном проекте эти данные лучше хранить в базе или таблице
ROLE_MAP: Dict[str, str] = {
    # пример:
     "379185153": "admin",
    # "234567890": "manager",
    # "345678901": "picker",
    # "456789012": "courier",
}


def get_role(uid: str) -> Optional[str]:
    """Возвращает роль пользователя по его UID."""
    return ROLE_MAP.get(str(uid))


@app.route("/")
def index():
    """Главная страница: меню с кнопками перехода."""
    uid = request.args.get("uid")
    role = get_role(uid) if uid else None
    return render_template("index.html", role=role, uid=uid)


@app.route("/new_order", methods=["GET", "POST"])
def new_order():
    """Страница создания нового заказа."""
    uid = request.args.get("uid")
    role = get_role(uid) if uid else None
    if role not in {"manager", "admin"}:
        return abort(403)
    if request.method == "POST":
        # Получаем общие данные заказа
        order_data = {
            "id": request.form.get("order_id"),
            "status": request.form.get("status"),
            "date": request.form.get("date"),
            "channel": request.form.get("channel"),
            "customer_name": request.form.get("customer_name"),
            "phone": request.form.get("phone"),
            "messenger": request.form.get("messenger"),
            "address": request.form.get("address"),
            "logistics": request.form.get("logistics"),
            # поля для редактирования (пустые на этапе создания)
            "percent": "",
            "extra_costs": "",
            "profit": "",
            "accruals": "",
        }
        # Собираем список товаров (динамические поля)
        items: List[Dict[str, str]] = []
        index = 0
        while True:
            prefix = f"item_{index}_"
            sku = request.form.get(prefix + "sku")
            if not sku:
                break
            item = {
                "sku": sku,
                "supplier": request.form.get(prefix + "supplier"),
                "photo": request.form.get(prefix + "photo"),
                "quantity": request.form.get(prefix + "quantity"),
                "order_sum": request.form.get(prefix + "order_sum"),
                "purchase_sum": request.form.get(prefix + "purchase_sum"),
                "comment": request.form.get(prefix + "comment"),
            }
            items.append(item)
            index += 1
        # Устанавливаем ID если пуст
        if not order_data["id"]:
            # простой порядковый номер — текущий timestamp
            order_data["id"] = str(int(__import__("time").time()))
        # дата
        if not order_data["date"]:
            order_data["date"] = __import__("datetime").datetime.now().strftime(
                "%Y-%m-%d %H:%M"
            )
        order_data["status"] = "оформлен"
        # Записываем в Google Sheets
        sheets.append_order(order_data, items)
        return redirect(url_for("index", uid=uid))
    # GET запрос — отрисовываем форму
    return render_template(
        "new_order.html",
        uid=uid,
        channels=[
            "Телеграм",
            "WKO",
            "Ав-1",
            "Ав-2",
            "ТГ Постоянник",
            "Викео постоянник",
            "Постоянник",
            "Дропер",
            "%",
        ],
        logistics=[
            "СДЕК",
            "Авито СДЕК",
            "Авито Почта РФ",
            "Авито Boxberry",
            "Почта РФ",
            "Самовывоз",
            "Достависта",
            "Яндекс",
            "x EXMAIL",
            "Boxberry",
            "Авито Яндекс",
            "Наш курьер",
            "JDE",
            "Авито Сберлогистика",
            "Авито DPD",
            "Мегатранс",
            "МэджикТранс",
            "Деловые Линии",
            "КИТ",
            "ПЭК",
            "Энергия",
            "5POST",
            "КСЕ",
            "Байкал",
        ],
        suppliers=[
            "У Арута",
            "Мой склад",
            "Пос-Y1 склад",
            "Пос-Y2  склад",
            "Пос-Y30 склад",
            "Пос-S1 склад",
            "Пос-S2 склад",
            "Пос-K1 склад",
            "Пос-Y1",
            "Пос-Y2",
            "Пос-Y3",
            "Пос-Y4",
            "Пос-Y5",
            "Пос-Y6",
            "Пос-Y7",
            "Пос-Y8",
            "Пос-Y9",
            "Пос-Y10",
            "Пос-Y11",
            "Пос-Y12",
            "Пос-Y20",
            "Пос-Y31",
            "Пост-Y30",
            "Пос-Y13",
            "Пост-Y15",
            "Пост-Y14",
            "Пост-17",
            "Через Сахи",
        ],
    )


@app.route("/orders/<status>")
def orders(status: str):
    """Отображение заказов по статусу."""
    uid = request.args.get("uid")
    role = get_role(uid) if uid else None
    # Все роли могут просматривать заказы
    orders_list = sheets.get_orders(status if status != "all" else None)
    return render_template(
        "orders.html",
        uid=uid,
        status=status,
        orders=orders_list,
        role=role,
    )


@app.route("/update_status/<order_id>/<new_status>")
def set_status(order_id: str, new_status: str):
    """Изменяет статус заказа. Доступно сборщику, курьеру и администратору."""
    uid = request.args.get("uid")
    role = get_role(uid) if uid else None
    allowed = {
        "picker": {"оформлен": "ожидает поставки", "ожидает поставки": "сборка"},
        "courier": {"сборка": "доставка", "доставка": "завершён"},
        "admin": None,
    }
    if role not in allowed:
        return abort(403)
    # Если администратор – разрешаем любой переход
    if role != "admin":
        # Получим текущий статус (для проверки перехода)
        order_info = next((o for o in sheets.get_orders() if o["id"] == order_id), None)
        if not order_info:
            return abort(404)
        cur_status = order_info["status"]
        transitions = allowed[role]
        if cur_status not in transitions or transitions[cur_status] != new_status:
            return abort(403)
    # Выполняем обновление
    sheets.update_status(order_id, new_status)
    return redirect(url_for("orders", status=new_status, uid=uid))


if __name__ == "__main__":
    # Запуск в режиме отладки
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
