import asyncio
import asyncpg

from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import BOT_TOKEN, DATABASE_URL
from bot.db.base import engine, Base
from bot.db import models  # 👈 ОБЯЗАТЕЛЬНО

from bot.handlers.start import router as start_router
from bot.handlers.payments import payments_router 
from bot.handlers.admin_payments import admin_payments_router
from bot.handlers.admin import admin_router  

from bot.services.scheduler import subscription_watcher
from bot.config import DATABASE_URL_ASYNCPG

async def wait_for_db(url):
    for i in range(30):
        try:
            print(f"Waiting for DB... ({i+1}/30)")
            conn = await asyncpg.connect(url)
            await conn.close()
            print("DB is ready")
            return
        except Exception as e:
            await asyncio.sleep(2)

    raise RuntimeError("Database is not available")



async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("DB initialized")


async def main():
    print("BOT TOKEN =", BOT_TOKEN)

    await wait_for_db(DATABASE_URL_ASYNCPG)
    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    asyncio.create_task(subscription_watcher(bot))

    dp = Dispatcher()

    dp.include_router(start_router)
    dp.include_router(payments_router)
    dp.include_router(admin_payments_router)
    dp.include_router(admin_router)

    print("Bot started, polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
