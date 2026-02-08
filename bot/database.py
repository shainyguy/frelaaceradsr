from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from bot.models import Base
from bot.config import config


def get_database_url() -> str:
    url = config.DATABASE_URL

    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql+asyncpg://"):
        pass
    elif url.startswith("sqlite://"):
        url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    elif not url:
        url = "sqlite+aiosqlite:///./freelance_radar.db"

    return url


DATABASE_URL = get_database_url()

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
    """Полная пересоздание БД с CASCADE"""
    async with engine.begin() as conn:
        if "postgresql" in DATABASE_URL:
            # Удаляем ВСЕ таблицы принудительно через CASCADE
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
            await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
            print("✅ Schema dropped and recreated")

        # Создаём все таблицы заново
        await conn.run_sync(Base.metadata.create_all)

    db_display = DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL
    print(f"✅ Database initialized (fresh): {db_display}")


async def get_session() -> AsyncSession:
    async with async_session() as session:
        return session
