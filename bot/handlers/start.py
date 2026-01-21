from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime

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
                "Этот бот нужен для напоминаний об оплате VPN.\n\n"
                "Если ты здесь впервые — напиши администратору, "
                "он выдаст конфиг и расскажет про оплату.\n\n"
                "После этого бот будет сам напоминать о платеже."
            )
            return

        # Проверяем админа
        if is_admin(message.from_user.id):
            await message.answer(
                "👑 Админ-панель\n\n"
                "/activate — активировать подписку\n"
                "/users — список пользователей\n"
                "/status — статус подписки"
            )
            return

        # Проверяем наличие подписки
        if user.subscription is None:
            await message.answer(
                "ℹ️ У тебя пока нет активной подписки.\n"
                "Напиши администратору, чтобы получить VPN."
            )
            return

        sub = user.subscription
        
        # Показываем кнопку если статус waiting
        if sub.status == "waiting":
            # Вычисляем сколько дней осталось до платежа
            days_left = (sub.next_payment - datetime.utcnow()).days
            
            if days_left <= 0:
                message_text = "🚨 СРОЧНО! Подписка истекла! Нужно оплатить VPN!\nПосле оплаты нажми кнопку ниже 👇"
            elif days_left <= 3:
                message_text = f"💰 Срочно! Пора оплатить VPN (осталось {days_left} дней)\nПосле оплаты нажми кнопку ниже 👇"
            else:
                message_text = "💰 Пора оплатить VPN\nПосле оплаты нажми кнопку ниже 👇"
            
            await message.answer(
                message_text,
                reply_markup=pay_keyboard
            )
        else:
            # Показываем обычный статус
            days_left = (sub.next_payment - datetime.utcnow()).days
            
            status_emoji = {
                "active": "✅",
                "expired": "❌",
                "suspended": "⏸️"
            }.get(sub.status, "📌")
            
            await message.answer(
                f"{status_emoji} <b>Текущий статус подписки</b>\n\n"
                f"📅 Следующий платёж: <b>{sub.next_payment:%d.%m.%Y}</b>\n"
                f"📌 Статус: <b>{sub.status}</b>\n"
                f"⏳ Осталось дней: <b>{max(0, days_left)}</b>"
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

        if not user:
            await message.answer("Напишите /start чтобы начать")
            return

        if user.subscription is None:
            await message.answer("У вас нет активной подписки")
            return

        sub = user.subscription
        days_left = (sub.next_payment - datetime.utcnow()).days
        
        if sub.status == "waiting":
            await message.answer(
                f"💰 Статус: <b>{sub.status}</b>\n"
                f"📅 Платёж до: <b>{sub.next_payment:%d.%m.%Y}</b>\n"
                f"⏳ Осталось дней: <b>{max(0, days_left)}</b>\n\n"
                f"<i>Нажмите /start чтобы оплатить</i>"
            )
        else:
            await message.answer(
                f"📅 Следующий платёж: <b>{sub.next_payment:%d.%m.%Y}</b>\n"
                f"📌 Статус: <b>{sub.status}</b>\n"
                f"⏳ Осталось дней: <b>{max(0, days_left)}</b>"
            )

# Тестовая команда для получения кнопки
@router.message(Command("pay"))
async def pay_command(message: Message):
    """Команда для получения кнопки оплаты"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.subscription))
            .where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.subscription:
            await message.answer("Сначала нужно активировать подписку")
            return
            
        # Всегда показываем кнопку при вызове /pay
        await message.answer(
            "💳 Оплата VPN\n\n"
            "Оплатите подписку и нажмите кнопку ниже:",
            reply_markup=pay_keyboard
        )