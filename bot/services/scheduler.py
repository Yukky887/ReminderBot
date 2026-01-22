import asyncio
from datetime import datetime, timedelta  
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload 
import logging

from bot.db.base import AsyncSessionLocal
from bot.db.models import Subscription, User
from bot.keyboards.payment import pay_keyboard

# Константы
CHECK_INTERVAL = 10  # Проверяем каждые 10 секунд
REMIND_BEFORE_DAYS = [3, 1, 0]  # Напоминаем за 3, 1 и 0 дней до платежа

logger = logging.getLogger(__name__)

async def subscription_watcher(bot):
    """Фоновая задача для отправки напоминаний"""
    logger.info("🔄 Напоминания о платежах запущены")
    
    while True:
        try:
            async with AsyncSessionLocal() as session:
                now = datetime.now()
                
                # Находим подписки, по которым нужно отправить напоминание
                result = await session.execute(
                    select(Subscription)
                    .join(User)
                    .options(selectinload(Subscription.user))  # ← Теперь работает!
                    .where(Subscription.status == "active")
                )
                
                all_subs = result.scalars().all()
                
                for sub in all_subs:
                    days_left = (sub.next_payment - now).days
                    
                    # Проверяем, нужно ли отправлять напоминание
                    should_remind = False
                    remind_day = None
                    
                    for days in REMIND_BEFORE_DAYS:
                        if days_left == days:
                            should_remind = True
                            remind_day = days
                            break
                    
                    if should_remind:
                        # Проверяем, не отправляли ли уже напоминание сегодня
                        if sub.last_reminder_sent:
                            last_sent_date = sub.last_reminder_sent.date()
                            if last_sent_date == now.date():
                                continue  # Уже отправляли сегодня
                        
                        # Отправляем напоминание
                        try:
                            if remind_day > 0:
                                message_text = (
                                    f"⏰ Напоминание!\n\n"
                                    f"До следующего платежа по VPN подписке осталось {remind_day} дней.\n"
                                    f"Дата платежа: {sub.next_payment:%d.%m.%Y}\n\n"
                                    f"После оплаты нажмите кнопку ниже:"
                                )
                            else:
                                message_text = (
                                    f"🚨 СРОЧНО!\n\n"
                                    f"Сегодня последний день оплаты VPN подписки!\n"
                                    f"Дата платежа: {sub.next_payment:%d.%m.%Y}\n\n"
                                    f"После оплаты нажмите кнопку ниже:"
                                )
                            
                            await bot.send_message(
                                chat_id=sub.user.telegram_id,
                                text=message_text,
                                reply_markup=pay_keyboard
                            )
                            
                            # Обновляем дату последнего напоминания
                            sub.last_reminder_sent = now
                            await session.commit()
                            
                            logger.info(f"📨 Отправлено напоминание пользователю {sub.user.telegram_id}, дней до платежа: {remind_day}")
                            
                        except Exception as e:
                            logger.error(f"❌ Ошибка отправки пользователю {sub.user.telegram_id}: {e}")
                            continue
                
                # Проверяем просроченные подписки (next_payment уже прошел)
                result = await session.execute(
                    select(Subscription)
                    .join(User)
                    .options(selectinload(Subscription.user))  # ← И здесь тоже!
                    .where(
                        and_(
                            Subscription.status == "active",
                            Subscription.next_payment < now
                        )
                    )
                )
                
                expired_subs = result.scalars().all()
                
                for sub in expired_subs:
                    # Меняем статус на expired
                    sub.status = "expired"
                    
                    # Уведомляем пользователя
                    try:
                        await bot.send_message(
                            chat_id=sub.user.telegram_id,
                            text=(
                                "❌ Ваша VPN подписка истекла!\n\n"
                                "Для продления обратитесь к администратору."
                            )
                        )
                    except Exception as e:
                        logger.error(f"❌ Не удалось уведомить о просрочке {sub.user.telegram_id}: {e}")
                
                await session.commit()
                
        except Exception as e:
            logger.error(f"❌ Ошибка в scheduler: {e}")
        
        await asyncio.sleep(CHECK_INTERVAL)