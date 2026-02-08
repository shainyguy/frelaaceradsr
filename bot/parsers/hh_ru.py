import aiohttp
from typing import List
from bot.parsers.base import BaseParser, FreelanceOrder


class HHParser(BaseParser):
    source_name = "hh"
    API_URL = "https://api.hh.ru/vacancies"

    SEARCH_QUERIES = {
        "python": "python freelance",
        "web": "frontend разработчик удаленно",
        "design": "дизайнер фриланс",
        "copywriting": "копирайтер удаленно",
        "mobile": "мобильный разработчик удаленно",
    }

    async def parse(self, keywords: List[str] = None) -> List[FreelanceOrder]:
        orders = []

        search_text = " OR ".join(keywords[:5]) if keywords else "фриланс"

        params = {
            "text": search_text,
            "schedule": "remote",
            "per_page": 20,
            "page": 0,
            "order_by": "publication_time",
        }

        headers = {
            "User-Agent": "FreelanceRadarBot/1.0 (contact@example.com)",
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    self.API_URL,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200:
                        return orders
                    data = await resp.json()
            except Exception:
                return orders

        for item in data.get("items", []):
            try:
                title = item.get("name", "")
                url = item.get("alternate_url", "")

                salary = item.get("salary")
                budget = ""
                budget_value = 0.0
                if salary:
                    from_s = salary.get("from")
                    to_s = salary.get("to")
                    currency = salary.get("currency", "RUR")
                    if from_s and to_s:
                        budget = f"{from_s} - {to_s} {currency}"
                        budget_value = float(to_s)
                    elif from_s:
                        budget = f"от {from_s} {currency}"
                        budget_value = float(from_s)
                    elif to_s:
                        budget = f"до {to_s} {currency}"
                        budget_value = float(to_s)

                snippet = item.get("snippet", {})
                description = ""
                if snippet:
                    req = snippet.get("requirement", "") or ""
                    resp_text = snippet.get("responsibility", "") or ""
                    description = f"{req} {resp_text}".strip()

                employer = item.get("employer", {})
                client_name = employer.get("name", "")

                order = FreelanceOrder(
                    title=title,
                    description=description,
                    budget=budget,
                    budget_value=budget_value,
                    url=url,
                    source=self.source_name,
                    client_name=client_name,
                    external_id=str(item.get("id", "")),
                )
                orders.append(order)
            except Exception:
                continue

        return orders