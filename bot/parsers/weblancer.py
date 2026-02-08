import aiohttp
from bs4 import BeautifulSoup
from typing import List
from bot.parsers.base import BaseParser, FreelanceOrder


class WeblancerParser(BaseParser):
    source_name = "weblancer"
    BASE_URL = "https://www.weblancer.net/jobs/"

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
        items = soup.select(".cols_table.container-fluid .row, .text_list > div")

        for item in items[:20]:
            try:
                title_el = item.select_one("a[class*='title'], h2 a, .title a")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                url = title_el.get("href", "")
                if url and not url.startswith("http"):
                    url = f"https://www.weblancer.net{url}"

                desc_el = item.select_one(".text_list_desc, .description")
                description = desc_el.get_text(strip=True) if desc_el else ""

                price_el = item.select_one(".amount, .price, [class*='cost']")
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