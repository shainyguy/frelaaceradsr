"""
Парсер Telegram каналов с заказами.
Примечание: для работы нужны каналы, куда бот добавлен как участник,
или публичные каналы. Здесь используется простой подход через
пересылку сообщений из каналов.
"""
from typing import List
from bot.parsers.base import BaseParser, FreelanceOrder


class TelegramChannelParser(BaseParser):
    source_name = "telegram"

    # Популярные каналы с заказами
    CHANNELS = [
        "@freelance_orders",
        "@freelancejob",
        "@web_freelancers",
        "@python_jobs",
        "@design_freelance_ru",
    ]

    def __init__(self):
        self._buffer: List[FreelanceOrder] = []

    def add_order(self, order: FreelanceOrder):
        """Добавление заказа из хендлера каналов"""
        self._buffer.append(order)

    async def parse(self, keywords: List[str] = None) -> List[FreelanceOrder]:
        """Возвращает буферизированные заказы"""
        result = []
        for order in self._buffer:
            if keywords is None or order.matches_keywords(keywords):
                result.append(order)

        self._buffer.clear()
        return result