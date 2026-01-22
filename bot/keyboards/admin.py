from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def payment_admin_keyboard(payment_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"pay_confirm:{payment_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"pay_reject:{payment_id}"
                ),
            ]
        ]
    )
 