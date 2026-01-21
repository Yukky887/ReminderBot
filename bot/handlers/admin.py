from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command, CommandObject
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta

from bot.config import ADMIN_ID
from bot.db.base import AsyncSessionLocal
from bot.db.models import User, Subscription, Payment

admin_router = Router()

@admin_router.message(Command("activate"))
async def activate_handler(message: Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав администратора.")
        return

    if not command.args:
        target_id = message.from_user.id
        target_user = "вашу"
    else:
        try:
            target_id = int(command.args.strip())
            target_user = f"пользователя {target_id}"
        except ValueError:
            await message.answer("❌ Неверный формат ID. Используйте: /activate <ID_пользователя>")
            return

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(User)
                .options(selectinload(User.subscription))
                .where(User.telegram_id == target_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                user = User(
                    telegram_id=target_id,
                    username=None,
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                
                result = await session.execute(
                    select(User)
                    .options(selectinload(User.subscription))
                    .where(User.id == user.id)
                )
                user = result.scalar_one_or_none()

            if user.subscription is None:
                subscription = Subscription(
                    user_id=user.id,
                    next_payment=datetime.utcnow() + timedelta(days=30),
                    status="active",
                    period_days=30,
                )
                session.add(subscription)
                await session.commit()
                await session.refresh(subscription)
                
                await session.refresh(user)
                result = await session.execute(
                    select(User)
                    .options(selectinload(User.subscription))
                    .where(User.id == user.id)
                )
                user = result.scalar_one_or_none()
            else:
                user.subscription.next_payment = datetime.utcnow() + timedelta(days=30)
                user.subscription.status = "active"
                await session.commit()
                await session.refresh(user.subscription)

            if user.subscription is None:
                await message.answer("❌ Ошибка: не удалось создать/обновить подписку")
                return

            response = (
                f"✅ Подписка {target_user} активирована!\n"
                f"ID: {user.telegram_id}\n"
                f"Следующий платёж: {user.subscription.next_payment:%d.%m.%Y}\n"
                f"Статус: {user.subscription.status}"
            )
            
            await message.answer(response)

            if target_id != message.from_user.id:
                try:
                    await message.bot.send_message(
                        chat_id=target_id,
                        text=(
                            "✅ Ваша подписка VPN активирована!\n\n"
                            f"Следующий платёж: {user.subscription.next_payment:%d.%m.%Y}\n"
                            "Спасибо, что пользуетесь нашим сервисом!"
                        )
                    )
                except Exception as e:
                    await message.answer(f"⚠️ Не удалось отправить уведомление: {str(e)[:100]}")
                    
        except Exception as e:
            await message.answer(f"❌ Ошибка: {str(e)[:200]}")
            print(f"Error in activate: {e}")

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

# В admin.py добавьте:
@admin_router.message(Command("set_waiting"))
async def set_waiting(message: Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return
    
    if not command.args:
        await message.answer("Используйте: /set_waiting <ID_пользователя>")
        return
    
    try:
        user_id = int(command.args.strip())
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User)
                .options(selectinload(User.subscription))
                .where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await message.answer("Пользователь не найден")
                return
            
            if not user.subscription:
                await message.answer("У пользователя нет подписки")
                return
            
            user.subscription.status = "waiting"
            await session.commit()
            
            await message.answer(f"✅ Статус пользователя {user_id} изменен на 'waiting'")
            
            # Уведомляем пользователя
            try:
                await message.bot.send_message(
                    chat_id=user_id,
                    text="💰 Пора оплатить VPN подписку!\n"
                         "Нажмите кнопку 'Я оплатил' после оплаты."
                )
            except:
                pass
                
    except ValueError:
        await message.answer("❌ Неверный формат ID")

@admin_router.message(Command("send_pay_button"))
async def send_pay_button(message: Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return
    
    if not command.args:
        await message.answer("Используйте: /send_pay_button <ID_пользователя>")
        return
    
    try:
        user_id = int(command.args.strip())
        
        # Отправляем кнопку пользователю
        try:
            await message.bot.send_message(
                chat_id=user_id,
                text="💳 Оплата VPN\n\n"
                     "Нажмите кнопку ниже после оплаты:",
                reply_markup=pay_keyboard
            )
            await message.answer(f"✅ Кнопка оплаты отправлена пользователю {user_id}")
        except Exception as e:
            await message.answer(f"❌ Не удалось отправить: {str(e)[:100]}")
            
    except ValueError:
        await message.answer("❌ Неверный формат ID")