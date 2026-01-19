from aiogram import Router
from aiogram.types import Message
from sqlalchemy import select

from bot.db.base import AsyncSessionLocal
from bot.db.models import User, Subscription

router = Router()


@router.message()
async def start_handler(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
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

        if not user.subscription:
            await message.answer(
                "ℹ️ У тебя пока нет активной подписки.\n"
                "Напиши администратору, чтобы получить VPN."
            )
            return

        sub = user.subscription

        await message.answer(
            f"📅 Следующий платёж: <b>{sub.next_payment:%d.%m.%Y}</b>\n"
            f"📌 Статус: <b>{sub.status}</b>"
        )
