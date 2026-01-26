from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command, CommandObject
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, timezone

from bot.config import ADMIN_ID
from bot.db.base import AsyncSessionLocal
from bot.db.models import User, Subscription, Payment

admin_router = Router()

@admin_router.message(Command("activate"))
async def activate_handler(message: Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав администратора.")
        return

    # Кого активируем
    if command.args:
        try:
            target_id = int(command.args.strip())
            target_user_text = f"пользователю {target_id}"
        except ValueError:
            await message.answer("❌ Используй: /activate <telegram_id>")
            return
    else:
        target_id = message.from_user.id
        target_user_text = "вам"

    async with AsyncSessionLocal() as session:
        try:
            # Ищем пользователя
            result = await session.execute(
                select(User)
                .options(selectinload(User.subscription))
                .where(User.telegram_id == target_id)
            )
            user = result.scalar_one_or_none()

            # Если нет — создаём
            if not user:
                user = User(
                    telegram_id=target_id,
                    username=message.from_user.username if target_id == message.from_user.id else None,
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

            now = datetime.now(timezone.utc)

            # Если нет подписки — создаём
            if not user.subscription:
                subscription = Subscription(
                    user_id=user.id,
                    status="active",
                    period_days=30,
                    next_payment=now + timedelta(days=30),
                )
                session.add(subscription)
                await session.commit()
                await session.refresh(subscription)

            else:
                sub = user.subscription

                # Гарантируем timezone-aware
                if sub.next_payment.tzinfo is None:
                    sub.next_payment = sub.next_payment.replace(tzinfo=timezone.utc)

                # Если просрочена — стартуем заново
                if sub.next_payment < now:
                    sub.next_payment = now + timedelta(days=30)
                else:
                    sub.next_payment += timedelta(days=30)

                sub.status = "active"
                await session.commit()

            sub = user.subscription

            await message.answer(
                f"✅ Подписка {target_user_text} активирована\n\n"
                f"ID: {user.telegram_id}\n"
                f"Следующий платёж: {sub.next_payment:%d.%m.%Y}\n"
                f"Статус: {sub.status}"
            )

            # Уведомляем пользователя
            if target_id != message.from_user.id:
                try:
                    await message.bot.send_message(
                        chat_id=target_id,
                        text=(
                            "✅ Ваша VPN подписка активирована!\n\n"
                            f"Следующий платёж: {sub.next_payment:%d.%m.%Y}"
                        )
                    )
                except Exception:
                    pass

        except Exception as e:
            await message.answer(f"❌ Ошибка: {str(e)[:200]}")
            
@admin_router.message(Command("payments"))
async def list_payments(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Payment)
            .join(User)
            .order_by(Payment.created_at.desc())
            .limit(10)
        )
        payments = result.scalars().all()
        
        if not payments:
            await message.answer("📭 Платежей нет")
            return
            
        text = "📋 Последние платежи:\n\n"
        for p in payments:
            text += f"💰 ID: {p.id}\n"
            text += f"   Пользователь: {p.user.telegram_id}\n"
            text += f"   Статус: {p.status}\n"
            text += f"   Дата: {p.created_at:%d.%m.%Y %H:%M}\n"
            text += "─" * 20 + "\n"
        
        await message.answer(text)

@admin_router.message(Command("users"))
async def list_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.subscription))
            .order_by(User.created_at.desc())
            .limit(20)
        )
        users = result.scalars().all()

        if not users:
            await message.answer("📭 Пользователей нет")
            return

        text = "📋 Последние пользователи:\n\n"
        for user in users:
            status = user.subscription.status if user.subscription else "нет подписки"
            text += f"👤 ID: {user.telegram_id}\n"
            text += f"   Username: @{user.username or 'нет'}\n"
            text += f"   Статус: {status}\n"
            text += f"   Создан: {user.created_at:%d.%m.%Y}\n"
            if user.subscription:
                text += f"   Платёж: {user.subscription.next_payment:%d.%m.%Y}\n"
            text += "─" * 20 + "\n"

        await message.answer(text)

@admin_router.message(Command("find"))
async def find_user(message: Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return

    if not command.args:
        await message.answer("Используйте: /find <ID или username>")
        return

    search = command.args.strip()

    async with AsyncSessionLocal() as session:
        if search.isdigit():
            result = await session.execute(
                select(User)
                .options(selectinload(User.subscription))
                .where(User.telegram_id == int(search))
            )
        else:
            result = await session.execute(
                select(User)
                .options(selectinload(User.subscription))
                .where(User.username.ilike(f"%{search}%"))
            )

        user = result.scalar_one_or_none()

        if not user:
            await message.answer("👤 Пользователь не найден")
            return

        status = user.subscription.status if user.subscription else "нет подписки"
        text = f"👤 Информация о пользователе:\n\n"
        text += f"ID: {user.telegram_id}\n"
        text += f"Username: @{user.username or 'нет'}\n"
        text += f"Статус подписки: {status}\n"
        text += f"Дата регистрации: {user.created_at:%d.%m.%Y %H:%M}\n"
        
        if user.subscription:
            text += f"Следующий платёж: {user.subscription.next_payment:%d.%m.%Y}\n"
            text += f"Период: {user.subscription.period_days} дней\n"
            text += f"Статус: {user.subscription.status}"

        await message.answer(text)