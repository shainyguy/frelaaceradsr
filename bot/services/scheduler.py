import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from bot.database import async_session
from bot.models import User, ParsedOrder
from bot.parsers.manager import parser_manager
from bot.config import config

if TYPE_CHECKING:
    from aiogram import Bot


class SchedulerService:
    """Планировщик парсинга"""

    def __init__(self):
        self.bot = None
        self.running = False
        self._task = None

    def start(self, bot):
        self.bot = bot
        self.running = True
        self._task = asyncio.create_task(self._loop())
        print("[Scheduler] Started")

    def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
        print("[Scheduler] Stopped")

    async def _loop(self):
        """Основной цикл парсинга"""
        while self.running:
            try:
                await self._parse_and_notify()
            except Exception as e:
                print(f"[Scheduler] Error: {e}")

            await asyncio.sleep(config.PARSE_INTERVAL)

    async def _parse_and_notify(self):
        """Парсинг и рассылка новых заказов"""
        async with async_session() as session:
            # Получаем всех активных пользователей с включённым парсером
            result = await session.execute(
                select(User).where(
                    User.parser_active == True,
                    User.notifications_enabled == True
                )
            )
            users = result.scalars().all()

        if not users:
            return

        # Собираем все уникальные ключевые слова
        all_keywords = set()
        for user in users:
            if user.categories:
                for cat in user.categories:
                    cat_info = config.CATEGORIES.get(cat)
                    if cat_info:
                        all_keywords.update(cat_info["keywords"])

        if not all_keywords:
            return

        # Парсим все биржи
        orders = await parser_manager.parse_all(list(all_keywords))

        if not orders:
            return

        # Сохраняем в БД и рассылаем
        async with async_session() as session:
            for order in orders:
                # Проверяем дубликат в БД
                existing = await session.execute(
                    select(ParsedOrder).where(ParsedOrder.hash == order.hash)
                )
                if existing.scalar_one_or_none():
                    continue

                # Сохраняем
                parsed = ParsedOrder(
                    external_id=order.external_id,
                    source=order.source,
                    title=order.title,
                    description=order.description,
                    budget=order.budget,
                    budget_value=order.budget_value,
                    url=order.url,
                    category=order.category,
                    client_name=order.client_name,
                    deadline=order.deadline,
                    hash=order.hash,
                )
                session.add(parsed)

                # Рассылаем подходящим пользователям
                for user in users:
                    if not user.has_active_subscription:
                        continue
                    if parser_manager.is_sent(user.telegram_id, order.hash):
                        continue

                    # Проверяем совпадение категорий
                    if user.categories:
                        user_keywords = []
                        for cat in user.categories:
                            cat_info = config.CATEGORIES.get(cat)
                            if cat_info:
                                user_keywords.extend(cat_info["keywords"])
                        if not order.matches_keywords(user_keywords):
                            continue

                    # Проверяем минимальный бюджет
                    if user.min_budget > 0 and order.budget_value > 0:
                        if order.budget_value < user.min_budget:
                            continue

                    # Проверяем тихие часы
                    now = datetime.utcnow()
                    hour = (now.hour + 3) % 24  # МСК
                    if user.quiet_hours_start > user.quiet_hours_end:
                        if hour >= user.quiet_hours_start or hour < user.quiet_hours_end:
                            continue
                    elif user.quiet_hours_start < user.quiet_hours_end:
                        if user.quiet_hours_start <= hour < user.quiet_hours_end:
                            continue

                    # Отправляем
                    try:
                        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="✍️ Сгенерировать отклик",
                                    callback_data=f"generate_response:{order.hash[:32]}"
                                ),
                            ],
                            [
                                InlineKeyboardButton(
                                    text="📥 Сохранить в CRM",
                                    callback_data=f"save_crm:{order.hash[:32]}"
                                ),
                                InlineKeyboardButton(
                                    text="🔍 Проверить заказчика",
                                    callback_data=f"check_client:{order.hash[:32]}"
                                ),
                            ],
                            [
                                InlineKeyboardButton(
                                    text="🔗 Открыть",
                                    url=order.url
                                )
                            ] if order.url else []
                        ])

                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=order.to_message(),
                            reply_markup=keyboard,
                            parse_mode="HTML",
                            disable_web_page_preview=True
                        )
                        parser_manager.mark_sent(user.telegram_id, order.hash)

                        # Обновляем статистику
                        user.orders_viewed += 1

                    except Exception as e:
                        print(f"[Notify] Error sending to {user.telegram_id}: {e}")

            await session.commit()


scheduler_service = SchedulerService()