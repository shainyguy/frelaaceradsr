import ssl
import json
import aiohttp
import uuid
import logging
from datetime import datetime, timedelta
from bot.config import config

logger = logging.getLogger(__name__)


class GigaChatService:
    AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    API_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

    def __init__(self):
        self.secret = config.GIGACHAT_SECRET
        self.access_token = None
        self.token_expires = None
        self._ssl_context = None

    def _get_ssl(self):
        if not self._ssl_context:
            self._ssl_context = ssl.create_default_context()
            self._ssl_context.check_hostname = False
            self._ssl_context.verify_mode = ssl.CERT_NONE
        return self._ssl_context

    async def _get_token(self) -> str:
        """Получить токен GigaChat"""
        now = datetime.utcnow()

        # Используем кешированный токен
        if self.access_token and self.token_expires and now < self.token_expires:
            return self.access_token

        if not self.secret:
            raise Exception("GIGACHAT_SECRET не задан в переменных окружения")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {self.secret}"
        }

        data = "scope=GIGACHAT_API_PERS"

        logger.info("🔑 Requesting GigaChat token...")

        connector = aiohttp.TCPConnector(ssl=self._get_ssl())
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                self.AUTH_URL,
                headers=headers,
                data=data,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                resp_text = await resp.text()
                logger.info(f"🔑 Token response status: {resp.status}")

                if resp.status == 200:
                    result = json.loads(resp_text)
                    self.access_token = result["access_token"]
                    self.token_expires = now + timedelta(minutes=25)
                    logger.info("✅ GigaChat token obtained")
                    return self.access_token
                else:
                    logger.error(f"❌ GigaChat auth failed: {resp.status} - {resp_text[:500]}")
                    raise Exception(f"GigaChat auth error {resp.status}: {resp_text[:200]}")

    async def _chat(self, messages: list, temperature: float = 0.7,
                     max_tokens: int = 1000) -> str:
        """Отправить запрос в GigaChat"""
        token = await self._get_token()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        payload = {
            "model": "GigaChat",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        logger.info(f"💬 GigaChat request: {len(messages)} messages")

        connector = aiohttp.TCPConnector(ssl=self._get_ssl())
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                resp_text = await resp.text()
                logger.info(f"💬 GigaChat response status: {resp.status}")

                if resp.status == 200:
                    result = json.loads(resp_text)
                    answer = result["choices"][0]["message"]["content"]
                    logger.info(f"✅ GigaChat answer: {len(answer)} chars")
                    return answer
                else:
                    logger.error(f"❌ GigaChat API error: {resp.status} - {resp_text[:500]}")
                    # Если токен протух — сбросим и попробуем ещё раз
                    if resp.status == 401:
                        self.access_token = None
                        self.token_expires = None
                        raise Exception("Token expired, retry needed")
                    raise Exception(f"GigaChat API error {resp.status}: {resp_text[:200]}")

    async def generate_response(self, order_title: str, order_description: str,
                                 user_bio: str = "", user_experience: int = 0) -> str:
        """Генерация отклика на заказ"""
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты — опытный фрилансер-копирайтер, который пишет идеальные "
                    "отклики на заказы на фриланс-биржах. Твои отклики всегда выигрывают. "
                    "Пиши кратко, конкретно, без воды. Показывай что понял задачу. "
                    "Предлагай конкретный план. Длина: 80-150 слов."
                )
            },
            {
                "role": "user",
                "content": self._build_response_prompt(
                    order_title, order_description, user_bio, user_experience
                )
            }
        ]

        try:
            return await self._chat(messages, temperature=0.7, max_tokens=500)
        except Exception as e:
            logger.error(f"Generate response error: {e}")
            # Retry once
            try:
                self.access_token = None
                return await self._chat(messages, temperature=0.7, max_tokens=500)
            except Exception as e2:
                logger.error(f"Generate response retry failed: {e2}")
                raise Exception(f"Не удалось сгенерировать отклик: {e2}")

    def _build_response_prompt(self, title: str, description: str,
                                bio: str, experience: int) -> str:
        prompt = f"Напиши отклик на заказ.\n\n"
        prompt += f"📋 ЗАКАЗ: {title}\n"

        if description:
            prompt += f"📝 ОПИСАНИЕ: {description[:1500]}\n"

        if bio:
            prompt += f"\n👤 ОБО МНЕ: {bio}\n"

        if experience and experience > 0:
            prompt += f"📅 ОПЫТ: {experience} лет\n"

        prompt += (
            "\n\nТребования к отклику:\n"
            "1. Начни с приветствия\n"
            "2. Покажи что понял задачу — перефразируй суть\n"
            "3. Опиши свой релевантный опыт (1-2 предложения)\n"
            "4. Предложи конкретный план/подход (2-3 пункта)\n"
            "5. Укажи примерные сроки\n"
            "6. Закончи призывом к обсуждению деталей\n"
            "7. НЕ пиши про цену — её обсудим отдельно\n"
        )

        return prompt

    async def calculate_price(self, task_description: str, category: str) -> str:
        """Расчёт цены задачи"""
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты — эксперт по ценообразованию фриланс-услуг в России. "
                    "У тебя 10+ лет опыта оценки проектов. "
                    "Ты знаешь реальные рыночные цены 2024 года. "
                    "Давай конкретные цифры в рублях, не уходи в абстракции. "
                    "Всегда структурируй ответ."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Рассчитай стоимость задачи для фрилансера.\n\n"
                    f"Категория: {category}\n"
                    f"Описание задачи: {task_description}\n\n"
                    f"Дай подробный расчёт:\n\n"
                    f"1. 💰 ЦЕНА ДЛЯ JUNIOR (мало опыта):\n"
                    f"   - Конкретная сумма в рублях\n\n"
                    f"2. 💰 ЦЕНА MIDDLE (2-4 года опыта):\n"
                    f"   - Конкретная сумма в рублях\n\n"
                    f"3. 💰 ЦЕНА SENIOR (5+ лет):\n"
                    f"   - Конкретная сумма в рублях\n\n"
                    f"4. ⏱ СРОКИ ВЫПОЛНЕНИЯ:\n"
                    f"   - Минимум\n"
                    f"   - Оптимально\n"
                    f"   - С запасом\n\n"
                    f"5. 📋 ДЕКОМПОЗИЦИЯ (разбей на подзадачи с ценами):\n"
                    f"   - Подзадача 1: X руб\n"
                    f"   - Подзадача 2: X руб\n"
                    f"   - и т.д.\n\n"
                    f"6. ⚠️ СКРЫТЫЕ РАСХОДЫ (что часто забывают учесть):\n\n"
                    f"7. 💡 РЕКОМЕНДАЦИЯ: какую цену поставить чтобы "
                    f"и не продешевить и не отпугнуть заказчика"
                )
            }
        ]

        try:
            return await self._chat(messages, temperature=0.5, max_tokens=1000)
        except Exception as e:
            logger.error(f"Calculate price error: {e}")
            try:
                self.access_token = None
                return await self._chat(messages, temperature=0.5, max_tokens=1000)
            except Exception as e2:
                raise Exception(f"Не удалось рассчитать цену: {e2}")

    async def analyze_client(self, client_name: str, client_info: str) -> str:
        """Анализ надёжности заказчика"""
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты — эксперт по безопасности на фриланс-биржах. "
                    "Ты анализируешь заказчиков и выявляешь мошенников. "
                    "Ты знаешь все красные флаги и типичные схемы обмана. "
                    "Давай конкретные оценки и рекомендации."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Проанализируй заказчика на фриланс-бирже.\n\n"
                    f"Имя/ник: {client_name}\n"
                    f"Информация: {client_info[:2000]}\n\n"
                    f"Дай подробный анализ:\n\n"
                    f"1. 📊 ОБЩАЯ ОЦЕНКА НАДЁЖНОСТИ: X/10\n\n"
                    f"2. 🟢 ПОЛОЖИТЕЛЬНЫЕ СИГНАЛЫ:\n"
                    f"   - что говорит в пользу заказчика\n\n"
                    f"3. 🔴 КРАСНЫЕ ФЛАГИ:\n"
                    f"   - что настораживает\n\n"
                    f"4. ⚠️ ТИПИЧНЫЕ РИСКИ:\n"
                    f"   - какие проблемы могут возникнуть\n\n"
                    f"5. 🛡 КАК ЗАЩИТИТЬСЯ:\n"
                    f"   - конкретные рекомендации\n\n"
                    f"6. ✅ ВЕРДИКТ: работать / с осторожностью / отказаться\n\n"
                    f"7. 💡 РЕКОМЕНДАЦИИ ПО УСЛОВИЯМ:\n"
                    f"   - предоплата\n"
                    f"   - этапы\n"
                    f"   - договор\n"
                    f"   - безопасная сделка"
                )
            }
        ]

        try:
            return await self._chat(messages, temperature=0.4, max_tokens=800)
        except Exception as e:
            logger.error(f"Analyze client error: {e}")
            try:
                self.access_token = None
                return await self._chat(messages, temperature=0.4, max_tokens=800)
            except Exception as e2:
                raise Exception(f"Не удалось проанализировать заказчика: {e2}")

    async def analyze_order(self, title: str, description: str) -> str:
        """Полный анализ заказа"""
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты — опытный фриланс-консультант. "
                    "Ты помогаешь фрилансерам оценивать заказы: "
                    "стоит ли браться, какие подводные камни, "
                    "как правильно оценить сложность."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Проанализируй этот заказ:\n\n"
                    f"Название: {title}\n"
                    f"Описание: {description[:2000]}\n\n"
                    f"Дай анализ:\n"
                    f"1. 📊 Сложность (1-10)\n"
                    f"2. ⏱ Примерные сроки\n"
                    f"3. 💰 Рекомендуемая цена (в рублях)\n"
                    f"4. 🛠 Необходимые навыки\n"
                    f"5. ⚠️ Возможные подводные камни\n"
                    f"6. ✅ Стоит ли браться (да/нет/с условиями)\n"
                    f"7. 💡 Советы по выполнению"
                )
            }
        ]

        try:
            return await self._chat(messages, temperature=0.5, max_tokens=800)
        except Exception as e:
            logger.error(f"Analyze order error: {e}")
            raise Exception(f"Не удалось проанализировать заказ: {e}")


gigachat_service = GigaChatService()
