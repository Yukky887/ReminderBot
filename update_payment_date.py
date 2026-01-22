import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.db.base import AsyncSessionLocal
from bot.db.models import User, Subscription

async def update_payment_date(telegram_id: int, days_from_now: int = 1):
    """
    Обновить дату платежа пользователя
    
    :param telegram_id: ID пользователя в Telegram
    :param days_from_now: через сколько дней (0 = сегодня, 1 = завтра и т.д.)
    """
    async with AsyncSessionLocal() as session:
        # Находим пользователя
        result = await session.execute(
            select(User)
            .options(selectinload(User.subscription))
            .where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"❌ Пользователь с telegram_id={telegram_id} не найден")
            return
        
        # Считаем новую дату
        new_date = datetime.now(timezone.utc) + timedelta(days=days_from_now)
        
        if not user.subscription:
            print(f"❌ У пользователя нет подписки")
            return
        
        # Обновляем дату
        user.subscription.next_payment = new_date
        user.subscription.last_reminder_sent = None  # Сбрасываем напоминания
        
        await session.commit()
        
        print(f"✅ Обновлено для пользователя @{user.username or telegram_id}")
        print(f"   Новая дата платежа: {new_date:%d.%m.%Y %H:%M}")
        print(f"   Через дней: {days_from_now}")
        
        # Показываем когда придут напоминания
        if days_from_now <= 3:
            print(f"   🔔 Напоминание придет СЕГОДНЯ (за {days_from_now} дня/дней)")
        else:
            print(f"   🔔 Напоминание придет через {days_from_now - 3} дней")

async def list_all_users():
    """Показать всех пользователей"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.subscription))
            .order_by(User.created_at.desc())
        )
        users = result.scalars().all()
        
        print("\n📋 Все пользователи:")
        print("=" * 70)
        for user in users:
            has_sub = "✅" if user.subscription else "❌"
            sub_info = ""
            if user.subscription:
                now = datetime.now(timezone.utc)
                days_left = (user.subscription.next_payment - now).days
                sub_info = f" | Платеж: {user.subscription.next_payment:%d.%m.%Y} | Дней: {days_left}"
            
            print(f"{has_sub} ID: {user.telegram_id} | @{user.username or 'нет'}{sub_info}")
        print("=" * 70)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Использование: python update_payment_date.py TELEGRAM_ID DAYS_FROM_NOW
        telegram_id = int(sys.argv[1])
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        
        print(f"🔄 Обновление даты платежа для пользователя {telegram_id}")
        asyncio.run(update_payment_date(telegram_id, days))
    else:
        # Показать всех пользователей
        asyncio.run(list_all_users())
        print("\n📝 Использование:")
        print("  python update_payment_date.py TELEGRAM_ID [DAYS_FROM_NOW]")
        print("  Пример: python update_payment_date.py 123456789 1  (платеж через 1 день)")
        print("  Пример: python update_payment_date.py 123456789 0  (платеж сегодня)")
        print("  Пример: python update_payment_date.py 123456789 -1 (просроченный платеж)")