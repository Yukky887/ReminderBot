import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import BOT_TOKEN
from bot.db.base import engine, Base
from bot.handlers.start import router as start_router

from bot.handlers.payments import payments_router 
from bot.handlers.admin_payments import admin_payments_router
from bot.handlers.admin import admin_router  


import asyncio
import asyncpg
from bot.config import DATABASE_URL

async def wait_for_db(url):
    for _ in range(10):
        try:
            conn = await asyncpg.connect(url)
            await conn.close()
            return
        except Exception:
            await asyncio.sleep(2)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main():
    print("BOT TOKEN =", BOT_TOKEN)

    await wait_for_db(DATABASE_URL)

    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    dp.include_router(start_router)
    dp.include_router(payments_router)
    dp.include_router(admin_payments_router)
    dp.include_router(admin_router)


    print("Bot started, polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
