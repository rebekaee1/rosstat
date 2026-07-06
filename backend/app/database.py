import json
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings


def _json_serializer(obj):
    return json.dumps(obj, default=str)


# О-15: бюджет соединений настраиваемый и посчитанный.
# Дефолт: UVICORN_WORKERS(2) × (pool 5 + overflow 10) = 30 стабильных
# + транзиенты (alembic/seed на старте, pg_dump бэкапа) ≈ 35–40 —
# втрое ниже дефолтного max_connections=100 Postgres. При росте числа
# воркеров сначала пересчитать: workers × (size + overflow) < 80.
engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    json_serializer=_json_serializer,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
