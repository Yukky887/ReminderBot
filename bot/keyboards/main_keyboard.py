# В другом файле, например main_keyboard.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💳 Оплатить", callback_data="make_payment"),
                InlineKeyboardButton(text="📊 Статистика", callback_data="stats")
            ],
            [
                InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")
            ]
        ]
    )