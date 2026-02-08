import aiohttp
from bs4 import BeautifulSoup
from typing import List
from bot.parsers.base import BaseParser, FreelanceOrder
import re


class FLParser(BaseParser):
    source_name = "fl"
    BASE_URL = "https://www.fl.ru/projects/"

    async def parse(self, keywords: List[str] = None) -> List[FreelanceOrder]:
        orders = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9",
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    self.BASE_URL,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200:
                        return orders
                    html = await resp.text()
            except Exception:
                return orders

        soup = BeautifulSoup(html, "lxml")
        items = soup.select("[id^='project-item'], .b-post, .b-post__grid")

        for item in items[:20]:
            try:
                title_el = item.select_one("a[class*='title'], .b-post__title a, h2 a")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                url = title_el.get("href", "")
                if url and not url.startswith("http"):
                    url = f"https://www.fl.ru{url}"

                desc_el = item.select_one(".b-post__body, .b-post__txt")
                description = desc_el.get_text(strip=True) if desc_el else ""

                price_el = item.select_one(".b-post__price, [class*='budget']")
                budget = price_el.get_text(strip=True) if price_el else ""

                budget_value = 0.0
                if budget:
                    nums = re.findall(r'[\d\s]+', budget)
                    if nums:
                        try:
                            budget_value = float(nums[0].replace(' ', '').strip())
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
            except Exception:
                continue

        return orders