from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

pay_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💸 Я оплатил", callback_data="pay_done")]
    ]
)
