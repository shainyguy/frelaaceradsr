import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    WEBAPP_URL: str = os.getenv("WEBAPP_URL", "")
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")

    # GigaChat
    GIGACHAT_SECRET: str = os.getenv("GIGACHAT_SECRET", "")

    # YooKassa
    YOOKASSA_SHOP_ID: str = os.getenv("YOOKASSA_SHOP_ID", "")
    YOOKASSA_SECRET_KEY: str = os.getenv("YOOKASSA_SECRET_KEY", "")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./freelance_radar.db")

    # Server
    PORT: int = int(os.getenv("PORT", 8080))

    # Subscription
    TRIAL_DAYS: int = 1
    SUBSCRIPTION_PRICE: int = 690  # рублей
    SUBSCRIPTION_DAYS: int = 30

    # Parser intervals (seconds)
    PARSE_INTERVAL: int = 60

    # Categories
    CATEGORIES: dict = field(default_factory=lambda: {
        "python": {
            "name": "🐍 Python разработка",
            "keywords": ["python", "django", "flask", "fastapi", "бот", "парсер",
                         "telegram bot", "скрипт", "автоматизация", "asyncio"]
        },
        "web": {
            "name": "🌐 Веб-разработка",
            "keywords": ["html", "css", "javascript", "react", "vue", "angular",
                         "frontend", "верстка", "лендинг", "сайт"]
        },
        "design": {
            "name": "🎨 Дизайн",
            "keywords": ["дизайн", "figma", "photoshop", "логотип", "баннер",
                         "ui/ux", "макет", "брендинг", "иллюстрация"]
        },
        "copywriting": {
            "name": "✍️ Копирайтинг",
            "keywords": ["текст", "копирайт", "статья", "seo", "контент",
                         "рерайт", "описание", "блог", "пост"]
        },
        "mobile": {
            "name": "📱 Мобильная разработка",
            "keywords": ["android", "ios", "flutter", "react native", "мобильное",
                         "приложение", "swift", "kotlin"]
        },
        "marketing": {
            "name": "📊 Маркетинг",
            "keywords": ["маркетинг", "smm", "таргет", "реклама", "продвижение",
                         "контекст", "яндекс директ", "google ads"]
        },
        "data": {
            "name": "📈 Данные и аналитика",
            "keywords": ["data", "аналитика", "excel", "power bi", "tableau",
                         "sql", "базы данных", "ml", "machine learning"]
        },
        "devops": {
            "name": "⚙️ DevOps",
            "keywords": ["devops", "docker", "kubernetes", "ci/cd", "linux",
                         "aws", "сервер", "nginx", "deploy"]
        }
    })


config = Config()