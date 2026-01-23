from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
import logging

from bot.db.base import AsyncSessionLocal
from bot.db.models import Payment, User
from bot.config import ADMIN_ID
from bot.keyboards.admin import payment_admin_keyboard

payments_router = Router()
logger = logging.getLogger(__name__)

@payments_router.callback_query(F.data == "pay_done")
async def user_paid(callback: CallbackQuery):
    """Пользователь нажал 'Я оплатил'"""
    
    async with AsyncSessionLocal() as session:
        try:
            # Находим пользователя с подпиской
            result = await session.execute(
                select(User)
                .options(selectinload(User.subscription))
                .where(User.telegram_id == callback.from_user.id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await callback.answer("Сначала напишите /start")
                return
            
            # Проверяем, есть ли активная подписка
            if not user.subscription or user.subscription.status != "active":
                await callback.answer("У вас нет активной подписки")
                return
            
            # Проверяем, не отправил ли уже заявку сегодня
            today = datetime.now(timezone.utc).date()
            existing_payment = await session.scalar(
                select(Payment)
                .where(
                    and_(
                        Payment.user_id == user.id,
                        Payment.status == "requested",
                        Payment.created_at >= datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
                    )
                )
            )
            
            if existing_payment:
                await callback.answer("Вы уже отправили заявку сегодня")
                return
            
            # Создаем новую заявку
            payment = Payment(
                user_id=user.id,
                status="requested",
                created_at=datetime.now(timezone.utc)
            )
            session.add(payment)
            await session.commit()
            payment_id = payment.id

            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            
            await callback.answer("✅ Заявка отправлена! Админ проверит оплату.")
            
            # Уведомляем админа
            if ADMIN_ID:
                try:
                    await callback.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=(
                            f"💸 Новый платеж!\n"
                            f"Пользователь: @{callback.from_user.username or 'без username'}\n"
                            f"ID: {callback.from_user.id}\n"
                            f"Дата: {payment.created_at:%d.%m.%Y %H:%M}"
                        ),
                        reply_markup=payment_admin_keyboard(payment_id)
                    )
                except Exception as e:
                    logger.error(f"Ошибка уведомления админа: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка в обработке платежа: {e}")
            await callback.answer("Произошла ошибка, попробуйте позже")