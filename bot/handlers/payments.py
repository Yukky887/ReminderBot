from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from datetime import datetime
import logging

from bot.db.base import AsyncSessionLocal
from bot.db.models import Payment, User
from bot.config import ADMIN_ID
from bot.keyboards.admin import payment_admin_keyboard

payments_router = Router()
logger = logging.getLogger(__name__)

@payments_router.callback_query(F.data == "pay_done")
async def user_paid(callback: CallbackQuery):
    logger.info(f"User {callback.from_user.id} clicked pay_done")
    print(f"DEBUG: pay_done вызван пользователем {callback.from_user.id}")
    
    try:
        async with AsyncSessionLocal() as session:
            print(f"DEBUG: Ищем пользователя {callback.from_user.id} в БД")
            user = await session.scalar(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            
            print(f"DEBUG: Пользователь найден: {user}")
            
            if not user:
                await callback.answer("Пользователь не найден. Сначала напишите /start")
                return
            
            payment = Payment(
                user_id=user.id,
                status="requested",
                created_at=datetime.utcnow()
            )
            session.add(payment)
            await session.commit()
            payment_id = payment.id
            
            print(f"DEBUG: Создан платеж ID: {payment_id}")
            
        await callback.answer("Заявка отправлена 👍")
        
        if ADMIN_ID:
            print(f"DEBUG: Отправляем уведомление админу {ADMIN_ID}")
            try:
                await callback.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"💸 Пользователь @{callback.from_user.username or callback.from_user.id} (ID: {callback.from_user.id}) сообщил об оплате",
                    reply_markup=payment_admin_keyboard(payment_id)
                )
                print("DEBUG: Уведомление отправлено")
            except Exception as e:
                print(f"DEBUG: Ошибка отправки админу: {e}")
                await callback.answer("Ошибка отправки уведомления админу")
                
    except Exception as e:
        print(f"DEBUG: Ошибка в обработке платежа: {e}")
        logger.error(f"Error in user_paid: {e}")
        await callback.answer("Произошла ошибка, попробуйте позже")