from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from bot.models import Base
from bot.config import config


def get_database_url() -> str:
    """
    Конвертирует DATABASE_URL в формат для async SQLAlchemy.
    Railway даёт postgresql://, нам нужен postgresql+asyncpg://
    Локально используем sqlite+aiosqlite://
    """
    url = config.DATABASE_URL

    # Railway PostgreSQL
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    # Если уже asyncpg — не трогаем
    elif url.startswith("postgresql+asyncpg://"):
        pass

    # SQLite для локальной разработки
    elif url.startswith("sqlite://"):
        url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)

    # Если ничего не указано — SQLite по умолчанию
    elif not url:
        url = "sqlite+aiosqlite:///./freelance_radar.db"

    return url


DATABASE_URL = get_database_url()

# Для PostgreSQL отключаем check_same_thread
connect_args = {}
if "sqlite" in DATABASE_URL:
    connect_args = {"check_same_thread": False}

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """Создание всех таблиц"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"✅ Database initialized: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")


async def get_session() -> AsyncSession:
    async with async_session() as session:
        return session
