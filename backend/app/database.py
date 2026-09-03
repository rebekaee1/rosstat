import json
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


def _json_serializer(obj):
    return json.dumps(obj, default=str)


# О-15: бюджет соединений настраиваемый и посчитанный.
# Дефолт: UVICORN_WORKERS(2) × (pool 5 + overflow 10) = 30 стабильных
# + транзиенты (alembic/seed на старте, pg_dump бэкапа) ≈ 35–40 —
# втрое ниже дефолтного max_connections=100 Postgres. При росте числа
# воркеров сначала пересчитать: workers × (size + overflow) < 80.
#
# 2026-09-03: аналитический контур больше не делит этот пул с витриной.
# Публичные запросы ждут соединение не дольше pool_timeout; statement_timeout
# на стороне Postgres убивает зависший SELECT раньше, чем nginx отдаст 504.

_PUBLIC_SERVER_SETTINGS = {
    "statement_timeout": str(settings.db_statement_timeout_ms),
    "idle_in_transaction_session_timeout": str(
        settings.db_idle_in_transaction_timeout_ms
    ),
}

engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,
    json_serializer=_json_serializer,
    connect_args={"server_settings": _PUBLIC_SERVER_SETTINGS},
)

async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

_ANALYTICS_SERVER_SETTINGS = {
    "statement_timeout": str(settings.analytics_db_statement_timeout_ms),
    "idle_in_transaction_session_timeout": str(
        settings.analytics_db_idle_in_transaction_timeout_ms
    ),
}

analytics_engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_size=settings.analytics_db_pool_size,
    max_overflow=settings.analytics_db_max_overflow,
    pool_timeout=settings.analytics_db_pool_timeout,
    pool_pre_ping=True,
    json_serializer=_json_serializer,
    connect_args={"server_settings": _ANALYTICS_SERVER_SETTINGS},
)

analytics_session = async_sessionmaker(
    analytics_engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


async def get_analytics_db() -> AsyncGenerator[AsyncSession, None]:
    async with analytics_session() as session:
        yield session


def pool_stats(target="public") -> dict[str, int]:
    """Счётчики SQLAlchemy pool для /metrics и алертов. Без исключений."""
    eng = analytics_engine if target == "analytics" else engine
    pool = eng.pool
    checkedout = 0
    overflow = 0
    size = 0
    try:
        checkedout = int(pool.checkedout())
    except Exception:
        pass
    try:
        overflow = int(pool.overflow())
    except Exception:
        pass
    try:
        size = int(pool.size())
    except Exception:
        pass
    return {"checkedout": checkedout, "overflow": overflow, "size": size}
