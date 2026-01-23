from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta 
import logging

from bot.db.base import AsyncSessionLocal
from bot.db.models import Payment, Subscription, User
from bot.config import ADMIN_ID

admin_payments_router = Router()
logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

@admin_payments_router.callback_query(F.data.startswith("pay_confirm:"))
async def confirm_payment(callback: CallbackQuery):
    # Проверка прав админа
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет прав")
        return
    
    # Извлекаем payment_id из callback.data
    try:
        payment_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("Неверный формат данных")
        return
    
    async with AsyncSessionLocal() as session:
        payment = await session.get(Payment, payment_id)
        if not payment:
            await callback.answer("Платеж не найден")
            return
        
        # Загружаем пользователя с подпиской
        result = await session.execute(
            select(User)
            .options(selectinload(User.subscription))
            .where(User.id == payment.user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Пользователь не найден")
            return
        
        # Обновляем подписку
        now = datetime.now()
        if not user.subscription:
            # Создаем новую подписку
            next_month = now + relativedelta(months=1)
            sub = Subscription(
                user_id=user.id,
                next_payment=next_month,
                status="active",
                period_days=30,
                last_reminder_sent=None
            )
            session.add(sub)
        else:
            # Продлеваем существующую подписку
            user.subscription.next_payment = user.subscription.next_payment + relativedelta(months=1)
            user.subscription.status = "active"
            user.subscription.last_reminder_sent = None
        
        payment.status = "confirmed"
        await session.commit()
        
        # Обновляем сообщение админу
        await callback.message.edit_text("✅ Оплата подтверждена, подписка продлена")
        
        # Уведомляем пользователя
        try:
            # Нужно получить обновленную подписку для показа даты
            await session.refresh(user.subscription)
            
            await callback.bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    "✅ Ваш платеж подтвержден!\n\n"
                    f"Подписка продлена на месяц. Следующий платеж: {user.subscription.next_payment:%d.%m.%Y}\n"
                    "Спасибо!"
                )
            )
            logger.info(f"✅ Платеж {payment_id} подтвержден для пользователя {user.telegram_id}")
            
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {user.telegram_id}: {e}")

@admin_payments_router.callback_query(F.data.startswith("pay_reject:"))
async def reject_payment(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет прав")
        return

    # Извлекаем payment_id из callback.data
    try:
        payment_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("Неверный формат данных")
        return

    async with AsyncSessionLocal() as session:
        payment = await session.get(Payment, payment_id)
        if not payment:
            await callback.answer("Платеж не найден")
            return
            
        # Загружаем user чтобы получить telegram_id
        result = await session.execute(
            select(User).where(User.id == payment.user_id)
        )
        user = result.scalar_one_or_none()
        
        payment.status = "rejected"
        await session.commit()

        await callback.message.edit_text("❌ Оплата отклонена")

        # Отправляем сообщение пользователю
        if user:
            try:
                await callback.bot.send_message(
                    chat_id=user.telegram_id,
                    text="❌ Оплата не подтверждена.\n"
                         "Если это ошибка — напиши администратору."
                )
                logger.info(f"❌ Платеж {payment_id} отклонен для пользователя {user.telegram_id}")
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение пользователю {user.telegram_id}: {e}")