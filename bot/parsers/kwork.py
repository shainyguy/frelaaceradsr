import aiohttp
from bs4 import BeautifulSoup
from typing import List
from bot.parsers.base import BaseParser, FreelanceOrder
import re


class KworkParser(BaseParser):
    source_name = "kwork"
    BASE_URL = "https://kwork.ru/projects"

    CATEGORY_MAP = {
        "python": "projects?c=41",
        "web": "projects?c=38",
        "design": "projects?c=10",
        "copywriting": "projects?c=15",
        "mobile": "projects?c=39",
        "marketing": "projects?c=33",
    }

    async def parse(self, keywords: List[str] = None) -> List[FreelanceOrder]:
        orders = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9",
        }

        async with aiohttp.ClientSession() as session:
            # Парсим страницу проектов
            try:
                async with session.get(
                    f"{self.BASE_URL}?a=1",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200:
                        return orders
                    html = await resp.text()
            except Exception as e:
                print(f"[kwork] Request error: {e}")
                return orders

        soup = BeautifulSoup(html, "lxml")

        # Поиск карточек заказов
        cards = soup.select(".card__content, .wants-card, [class*='project']")

        for card in cards[:20]:
            try:
                title_el = card.select_one("a[class*='title'], .wants-card__header a, h3 a, .first-link")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                url = title_el.get("href", "")
                if url and not url.startswith("http"):
                    url = f"https://kwork.ru{url}"

                desc_el = card.select_one(".wants-card__description-text, .breakword, p")
                description = desc_el.get_text(strip=True) if desc_el else ""

                price_el = card.select_one(".wants-card__price, .price, [class*='price']")
                budget = price_el.get_text(strip=True) if price_el else ""
                budget_value = 0.0
                if budget:
                    nums = re.findall(r'[\d\s]+', budget.replace(' ', ''))
                    if nums:
                        try:
                            budget_value = float(nums[0].replace(' ', ''))
                        except ValueError:
                            pass

                order = FreelanceOrder(
                    title=title,
                    description=description,
                    budget=budget,
                    budget_value=budget_value,
                    url=url,
                    source=self.source_name,
                )

                if keywords is None or order.matches_keywords(keywords):
                    orders.append(order)
            except Exception as e:
                continue

        return orders