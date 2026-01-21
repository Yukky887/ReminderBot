from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import timedelta

from bot.db.base import AsyncSessionLocal
from bot.db.models import Payment, Subscription, User
from bot.config import ADMIN_ID
from datetime import datetime

admin_payments_router = Router()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

@admin_payments_router.callback_query(F.data.startswith("pay_confirm:"))
async def confirm_payment(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет прав")
        return

    payment_id = int(callback.data.split(":")[1])

    async with AsyncSessionLocal() as session:
        # Загружаем payment с user
        payment = await session.get(Payment, payment_id)
        if not payment:
            await callback.answer("Платеж не найден")
            return
            
        # Загружаем user с subscription
        result = await session.execute(
            select(User)
            .options(selectinload(User.subscription))
            .where(User.id == payment.user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Пользователь не найден")
            return

        if not user.subscription:
            # Создаем подписку если её нет
            sub = Subscription(
                user_id=user.id,
                next_payment=datetime.utcnow() + timedelta(days=30),
                status="active",
                period_days=30,
            )
            session.add(sub)
        else:
            sub = user.subscription
            sub.next_payment = datetime.utcnow() + timedelta(days=sub.period_days)
            sub.status = "active"

        payment.status = "confirmed"
        await session.commit()

    await callback.message.edit_text("✅ Оплата подтверждена")
    
    # Отправляем сообщение пользователю
    try:
        await callback.bot.send_message(
            chat_id=user.telegram_id,
            text=f"✅ Оплата подтверждена. Спасибо!\n"
                 f"Следующий платёж: {sub.next_payment:%d.%m.%Y}"
        )
    except Exception as e:
        print(f"Не удалось отправить сообщение пользователю: {e}")

@admin_payments_router.callback_query(F.data.startswith("pay_reject:"))
async def reject_payment(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет прав")
        return

    payment_id = int(callback.data.split(":")[1])

    async with AsyncSessionLocal() as session:
        payment = await session.get(Payment, payment_id)
        if not payment:
            await callback.answer("Платеж не найден")
            return
            
        # Загружаем user чтобы получить telegram_id
        user = await session.get(User, payment.user_id)
        
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
        except Exception as e:
            print(f"Не удалось отправить сообщение пользователю: {e}")