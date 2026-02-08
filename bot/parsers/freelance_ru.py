import aiohttp
from bs4 import BeautifulSoup
from typing import List
from bot.parsers.base import BaseParser, FreelanceOrder


class FreelanceRuParser(BaseParser):
    source_name = "freelance_ru"
    BASE_URL = "https://freelance.ru/project/search/pro"

    async def parse(self, keywords: List[str] = None) -> List[FreelanceOrder]:
        orders = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
        projects = soup.select(".project, .project-item, [class*='project-list'] > div")

        for proj in projects[:20]:
            try:
                title_el = proj.select_one("a.project-name, h3 a, .title a")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                url = title_el.get("href", "")
                if url and not url.startswith("http"):
                    url = f"https://freelance.ru{url}"

                desc_el = proj.select_one(".project-desc, .description")
                description = desc_el.get_text(strip=True) if desc_el else ""

                price_el = proj.select_one(".project-price, .price")
                budget = price_el.get_text(strip=True) if price_el else ""

                order = FreelanceOrder(
                    title=title,
                    description=description,
                    budget=budget,
                    url=url,
                    source=self.source_name,
                )

                if keywords is None or order.matches_keywords(keywords):
                    orders.append(order)
            except Exception:
                continue

        return orders