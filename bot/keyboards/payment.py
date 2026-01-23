from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

pay_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплачено", callback_data="pay_done")]
    ]
)
