import ssl
import aiohttp
import uuid
import json
from datetime import datetime, timedelta
from bot.config import config


class GigaChatService:
    AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    API_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

    def __init__(self):
        self.secret = config.GIGACHAT_SECRET
        self.access_token = None
        self.token_expires = None

    async def _get_token(self):
        """Получить токен авторизации GigaChat"""
        now = datetime.utcnow()
        if self.access_token and self.token_expires and now < self.token_expires:
            return self.access_token

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {self.secret}"
        }

        data = "scope=GIGACHAT_API_PERS"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.AUTH_URL,
                headers=headers,
                data=data,
                ssl=ssl_context
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self.access_token = result["access_token"]
                    self.token_expires = now + timedelta(minutes=25)
                    return self.access_token
                else:
                    text = await resp.text()
                    raise Exception(f"GigaChat auth error {resp.status}: {text}")

    async def generate_response(self, order_title: str, order_description: str,
                                 user_bio: str = "", user_experience: int = 0) -> str:
        """Генерация отклика на заказ"""
        token = await self._get_token()

        prompt = f"""Ты — опытный фрилансер, который пишет идеальные отклики на заказы.
Напиши короткий, убедительный отклик на заказ. Отклик должен:
1. Показать понимание задачи
2. Кратко описать релевантный опыт
3. Предложить подход к решению
4. Быть дружелюбным и профессиональным
5. Быть не длиннее 150 слов

{"Информация об исполнителе: " + user_bio if user_bio else ""}
{"Опыт: " + str(user_experience) + " лет" if user_experience else ""}

Заказ: {order_title}
Описание: {order_description[:1000]}

Напиши отклик:"""

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        payload = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 500
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.API_URL,
                headers=headers,
                json=payload,
                ssl=ssl_context
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    text = await resp.text()
                    raise Exception(f"GigaChat API error {resp.status}: {text}")

    async def analyze_client(self, client_name: str, client_info: str) -> str:
        """Анализ заказчика"""
        token = await self._get_token()

        prompt = f"""Проанализируй заказчика на фриланс-бирже и дай рекомендации.
Имя: {client_name}
Информация: {client_info[:1000]}

Оцени:
1. Надёжность (1-10)
2. Вероятность оплаты
3. Красные флаги
4. Рекомендация работать или нет

Ответь кратко и структурированно."""

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        payload = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 500
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.API_URL,
                headers=headers,
                json=payload,
                ssl=ssl_context
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    return "Не удалось проанализировать. Попробуйте позже."

    async def calculate_price(self, task_description: str, category: str) -> str:
        """Расчёт цены через AI"""
        token = await self._get_token()

        prompt = f"""Ты — эксперт по ценообразованию фриланс-услуг в России.
Категория: {category}
Описание задачи: {task_description[:1000]}

Рассчитай:
1. Минимальная цена (для начинающего)
2. Средняя рыночная цена
3. Цена для опытного специалиста
4. Примерные сроки выполнения
5. На что обратить внимание при оценке

Ответь структурированно, цены в рублях."""

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        payload = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 600
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.API_URL,
                headers=headers,
                json=payload,
                ssl=ssl_context
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    return "Не удалось рассчитать. Попробуйте позже."


gigachat_service = GigaChatService()