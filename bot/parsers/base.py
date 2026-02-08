import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class FreelanceOrder:
    """Стандартная модель заказа"""
    title: str
    description: str = ""
    budget: str = ""
    budget_value: float = 0.0
    url: str = ""
    source: str = ""
    category: str = ""
    client_name: str = ""
    deadline: str = ""
    external_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def hash(self) -> str:
        """Уникальный хеш для дедупликации"""
        content = f"{self.source}:{self.title}:{self.url}"
        return hashlib.sha256(content.encode()).hexdigest()

    def matches_keywords(self, keywords: List[str]) -> bool:
        """Проверка совпадения с ключевыми словами"""
        text = f"{self.title} {self.description}".lower()
        return any(kw.lower() in text for kw in keywords)

    def to_message(self) -> str:
        """Форматирование для Telegram"""
        source_emoji = {
            "kwork": "🟢", "fl": "🔵", "habr": "🟠",
            "hh": "🔴", "telegram": "✈️", "freelance_ru": "🟡",
            "weblancer": "🟣"
        }
        emoji = source_emoji.get(self.source, "📌")

        msg = f"{emoji} <b>{self.source.upper()}</b>\n\n"
        msg += f"📋 <b>{self.title}</b>\n\n"

        if self.description:
            desc = self.description[:300]
            if len(self.description) > 300:
                desc += "..."
            msg += f"📝 {desc}\n\n"

        if self.budget:
            msg += f"💰 Бюджет: <b>{self.budget}</b>\n"

        if self.deadline:
            msg += f"⏰ Срок: {self.deadline}\n"

        if self.client_name:
            msg += f"👤 Заказчик: {self.client_name}\n"

        if self.url:
            msg += f"\n🔗 <a href='{self.url}'>Открыть заказ</a>"

        return msg


class BaseParser(ABC):
    """Базовый класс парсера"""

    source_name: str = "unknown"

    @abstractmethod
    async def parse(self, keywords: List[str] = None) -> List[FreelanceOrder]:
        """Парсинг заказов"""
        pass

    async def safe_parse(self, keywords: List[str] = None) -> List[FreelanceOrder]:
        """Безопасный парсинг с обработкой ошибок"""
        try:
            return await self.parse(keywords)
        except Exception as e:
            print(f"[{self.source_name}] Parse error: {e}")
            return []