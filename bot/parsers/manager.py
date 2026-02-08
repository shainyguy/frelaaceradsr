import asyncio
from typing import List, Dict, Set
from datetime import datetime

from bot.parsers.base import FreelanceOrder
from bot.parsers.kwork import KworkParser
from bot.parsers.fl_ru import FLParser
from bot.parsers.habr_freelance import HabrFreelanceParser
from bot.parsers.hh_ru import HHParser
from bot.parsers.telegram_channels import TelegramChannelParser
from bot.parsers.freelance_ru import FreelanceRuParser
from bot.parsers.weblancer import WeblancerParser


class ParserManager:
    """Менеджер всех парсеров"""

    def __init__(self):
        self.parsers = {
            "kwork": KworkParser(),
            "fl": FLParser(),
            "habr": HabrFreelanceParser(),
            "hh": HHParser(),
            "telegram": TelegramChannelParser(),
            "freelance_ru": FreelanceRuParser(),
            "weblancer": WeblancerParser(),
        }
        # Множество хешей уже отправленных заказов для каждого пользователя
        self._sent_hashes: Dict[int, Set[str]] = {}
        self._last_parse: Dict[str, datetime] = {}

    def get_user_sent_hashes(self, user_id: int) -> Set[str]:
        if user_id not in self._sent_hashes:
            self._sent_hashes[user_id] = set()
        return self._sent_hashes[user_id]

    def mark_sent(self, user_id: int, order_hash: str):
        self.get_user_sent_hashes(user_id).add(order_hash)
        # Ограничиваем размер
        if len(self._sent_hashes[user_id]) > 5000:
            # Удаляем половину старых
            hashes_list = list(self._sent_hashes[user_id])
            self._sent_hashes[user_id] = set(hashes_list[2500:])

    def is_sent(self, user_id: int, order_hash: str) -> bool:
        return order_hash in self.get_user_sent_hashes(user_id)

    async def parse_all(self, keywords: List[str] = None,
                        sources: List[str] = None) -> List[FreelanceOrder]:
        """Параллельный парсинг всех бирж"""
        parsers_to_use = self.parsers
        if sources:
            parsers_to_use = {k: v for k, v in self.parsers.items() if k in sources}

        tasks = []
        for name, parser in parsers_to_use.items():
            tasks.append(self._parse_single(name, parser, keywords))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_orders = []
        for result in results:
            if isinstance(result, list):
                all_orders.extend(result)
            elif isinstance(result, Exception):
                print(f"Parse error: {result}")

        # Дедупликация
        seen_hashes = set()
        unique_orders = []
        for order in all_orders:
            h = order.hash
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique_orders.append(order)

        # Сортировка: сначала с бюджетом
        unique_orders.sort(key=lambda o: o.budget_value or 0, reverse=True)

        return unique_orders

    async def _parse_single(self, name: str, parser, keywords: List[str] = None) -> List[FreelanceOrder]:
        """Парсинг одной биржи с таймаутом"""
        try:
            result = await asyncio.wait_for(
                parser.safe_parse(keywords),
                timeout=20
            )
            self._last_parse[name] = datetime.utcnow()
            return result
        except asyncio.TimeoutError:
            print(f"[{name}] Timeout")
            return []

    def get_stats(self) -> str:
        """Статистика парсеров"""
        lines = ["📊 <b>Статус парсеров:</b>\n"]
        for name, parser in self.parsers.items():
            last = self._last_parse.get(name)
            if last:
                ago = (datetime.utcnow() - last).seconds
                status = "🟢" if ago < 120 else "🟡" if ago < 300 else "🔴"
                lines.append(f"{status} {name.upper()} — {ago}с назад")
            else:
                lines.append(f"⚪ {name.upper()} — не запускался")
        return "\n".join(lines)


parser_manager = ParserManager()