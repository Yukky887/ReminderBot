from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone

from bot.config import is_admin
from bot.db.base import AsyncSessionLocal
from bot.db.models import User, Subscription
from bot.keyboards.payment import pay_keyboard

router = Router()

@router.message(CommandStart())
async def start_handler(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.subscription))
            .where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
            )
            session.add(user)
            await session.commit()
            
            await message.answer(
                "👋 Привет!\n\n"
                "Этот бот напоминает об оплате VPN подписки.\n\n"
                "Когда подойдет время оплаты — я пришлю тебе напоминание с кнопкой.\n\n"
                "После оплаты нажми кнопку 'Я оплатил', и админ подтвердит платеж."
            )
            return

        if is_admin(message.from_user.id):
            await message.answer("👑 Админ-панель доступна через команды /activate, /users и т.д.")
            return

        if user.subscription is None:
            await message.answer("ℹ️ У тебя пока нет активной подписки.")
            return

        sub = user.subscription
        days_left = (sub.next_payment - datetime.now(timezone.utc)).days
        
        # Всегда показываем статус, НЕ показываем кнопку
        status_emoji = "✅" if sub.status == "active" else "❌"
        await message.answer(
            f"{status_emoji} <b>Текущий статус подписки</b>\n\n"
            f"📅 Следующий платёж: <b>{sub.next_payment:%d.%m.%Y}</b>\n"
            f"📌 Статус: <b>{sub.status}</b>\n"
            f"⏳ Осталось дней: <b>{max(0, days_left)}</b>\n\n"
            f"<i>Я пришлю напоминание за 3 дня до платежа</i>"
        )

@router.message(Command("status"))
async def status_handler(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.subscription))
            .where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.subscription:
            await message.answer("У вас нет активной подписки")
            return

        sub = user.subscription
        days_left = (sub.next_payment - datetime.now(timezone.utc)).days
        
        await message.answer(
            f"📅 Следующий платёж: <b>{sub.next_payment:%d.%m.%Y}</b>\n"
            f"📌 Статус: <b>{sub.status}</b>\n"
            f"⏳ Осталось дней: <b>{max(0, days_left)}</b>"
        )