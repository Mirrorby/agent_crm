"""
Telegram‑бот, который выдаёт ссылку на мини‑приложение и отправляет
уведомления. Для упрощения примера основной интерфейс реализован в
WebApp, поэтому в боте только команда /start и регистрация команд.

Бот использует библиотеку python‑telegram‑bot (асинхронный режим).
"""
import os
from typing import Dict, Optional

from telegram import (Update, KeyboardButton, ReplyKeyboardMarkup,
                      WebAppInfo)
from telegram.ext import (Application, CommandHandler,
                          ContextTypes, MessageHandler, filters)


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:5000")

# Роли пользователей – такие же, как в app.py
ROLE_MAP: Dict[str, str] = {
    # "123456789": "admin",
    # "234567890": "manager",
    # "345678901": "picker",
    # "456789012": "courier",
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start: отправляет кнопку для открытия WebApp."""
    uid = update.effective_user.id
    role = ROLE_MAP.get(str(uid))
    # Кнопка для открытия WebApp. UID передаётся через query string
    url_with_uid = f"{WEBAPP_URL}?uid={uid}"
    button = KeyboardButton(
        text="Открыть CRM",
        web_app=WebAppInfo(url=url_with_uid),
    )
    keyboard = ReplyKeyboardMarkup([[button]], resize_keyboard=True)
    text = "Добро пожаловать в CRM! Нажмите кнопку, чтобы открыть мини‑приложение."
    if not role:
        text += "\n\nУ вас пока не назначена роль. Обратитесь к администратору."
    await update.message.reply_text(text, reply_markup=keyboard)


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ответ на неизвестные команды."""
    await update.message.reply_text("Неизвестная команда. Используйте /start.")


def main():
    """Запускает бота."""
    if not TOKEN:
        raise RuntimeError("Не задан токен TELEGRAM_BOT_TOKEN")
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))
    application.run_polling()


if __name__ == "__main__":
    main()