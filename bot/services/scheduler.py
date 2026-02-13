import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from bot.database import async_session
from bot.models import User, ParsedOrder
from bot.parsers.manager import parser_manager
from bot.config import config

if TYPE_CHECKING:
    from aiogram import Bot

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self):
        self.bot = None
        self.running = False
        self._parse_task = None
        self._health_task = None

    def start(self, bot):
        self.bot = bot
        self.running = True
        self._parse_task = asyncio.create_task(self._parse_loop())
        self._health_task = asyncio.create_task(self._health_loop())
        print("[Scheduler] Started")

    def stop(self):
        self.running = False
        if self._parse_task:
            self._parse_task.cancel()
        if self._health_task:
            self._health_task.cancel()
        print("[Scheduler] Stopped")

    async def _health_loop(self):
        """Проверка webhook каждые 5 минут"""
        while self.running:
            try:
                await asyncio.sleep(300)  # 5 минут
                await self._check_webhook()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Health] Error: {e}")

    async def _check_webhook(self):
        """Проверка и восстановление webhook"""
        if not self.bot or not config.WEBHOOK_URL:
            return

        try:
            info = await self.bot.get_webhook_info()
            expected_url = f"{config.WEBHOOK_URL}/webhook"

            if info.url != expected_url:
                logger.warning(f"[Health] Webhook URL mismatch! Expected: {expected_url}, Got: {info.url}")
                await self.bot.delete_webhook(drop_pending_updates=True)
                await self.bot.set_webhook(
                    url=expected_url,
                    drop_pending_updates=True,
                    allowed_updates=["message", "callback_query"]
                )
                logger.info(f"[Health] Webhook restored: {expected_url}")

            elif info.last_error_message:
                logger.warning(f"[Health] Webhook error: {info.last_error_message}")
                # Переустанавливаем при ошибках
                if info.last_error_date:
                    error_age = (datetime.utcnow() - info.last_error_date).seconds
                    if error_age < 600:  # Ошибка менее 10 минут назад
                        await self.bot.delete_webhook(drop_pending_updates=True)
                        await asyncio.sleep(2)
                        await self.bot.set_webhook(
                            url=expected_url,
                            drop_pending_updates=True,
                            allowed_updates=["message", "callback_query"]
                        )
                        logger.info("[Health] Webhook re-established after error")

            else:
                logger.info(f"[Health] Webhook OK: {info.url}, pending: {info.pending_update_count}")

        except Exception as e:
            logger.error(f"[Health] Check failed: {e}")

    async def _parse_loop(self):
        """Основной цикл парсинга"""
        while self.running:
            try:
                await asyncio.sleep(config.PARSE_INTERVAL)
                await self._parse_and_notify()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Scheduler] Parse error: {e}")

    async def _parse_and_notify(self):
        """Парсинг и рассылка"""
        async with async_session() as session:
            result = await session.execute(
                select(User).where(
                    User.parser_active == True,
                    User.notifications_enabled == True
                )
            )
            users = result.scalars().all()

        if not users:
            return

        # Фильтруем только с активной подпиской
        active_users = [u for u in users if u.has_active_subscription]
        if not active_users:
            return

        # Собираем ключевые слова
        all_keywords = set()
        for user in active_users:
            if user.categories:
                for cat in user.categories:
                    cat_info = config.CATEGORIES.get(cat)
                    if cat_info:
                        all_keywords.update(cat_info["keywords"])

        if not all_keywords:
            return

        # Парсим
        orders = await parser_manager.parse_all(list(all_keywords))
        if not orders:
            return

        # Рассылаем
        async with async_session() as session:
            for order in orders:
                # Дедупликация
                existing = await session.execute(
                    select(ParsedOrder).where(ParsedOrder.hash == order.hash)
                )
                if existing.scalar_one_or_none():
                    continue

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

                for user in active_users:
                    if parser_manager.is_sent(user.telegram_id, order.hash):
                        continue

                    # Проверяем категории
                    if user.categories:
                        user_keywords = []
                        for cat in user.categories:
                            cat_info = config.CATEGORIES.get(cat)
                            if cat_info:
                                user_keywords.extend(cat_info["keywords"])
                        if not order.matches_keywords(user_keywords):
                            continue

                    # Мин. бюджет
                    if user.min_budget > 0 and order.budget_value > 0:
                        if order.budget_value < user.min_budget:
                            continue

                    # Тихие часы
                    now = datetime.utcnow()
                    hour = (now.hour + 3) % 24
                    if user.quiet_hours_start > user.quiet_hours_end:
                        if hour >= user.quiet_hours_start or hour < user.quiet_hours_end:
                            continue
                    elif user.quiet_hours_start < user.quiet_hours_end:
                        if user.quiet_hours_start <= hour < user.quiet_hours_end:
                            continue

                    try:
                        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(
                                text="✍️ Сгенерировать отклик",
                                callback_data=f"generate_response:{order.hash[:32]}"
                            )],
                            [
                                InlineKeyboardButton(
                                    text="📥 В CRM",
                                    callback_data=f"save_crm:{order.hash[:32]}"
                                ),
                                InlineKeyboardButton(
                                    text="🔍 Проверить",
                                    callback_data=f"check_client:{order.hash[:32]}"
                                ),
                            ],
                            [InlineKeyboardButton(
                                text="🔗 Открыть", url=order.url
                            )] if order.url else []
                        ])

                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=order.to_message(),
                            reply_markup=keyboard,
                            parse_mode="HTML",
                            disable_web_page_preview=True
                        )
                        parser_manager.mark_sent(user.telegram_id, order.hash)
                        user.orders_viewed += 1

                    except Exception as e:
                        logger.error(f"[Notify] Error {user.telegram_id}: {e}")

            await session.commit()


scheduler_service = SchedulerService()
