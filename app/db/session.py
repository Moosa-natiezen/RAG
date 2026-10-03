from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import HTTPException, status
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _async_database_url(database_url: str) -> tuple[URL, dict[str, str]]:
    url = make_url(database_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+asyncpg")

    query = dict(url.query)
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    url = url.set(query=query)

    connect_args: dict[str, str] = {}
    if sslmode and sslmode != "disable":
        connect_args["ssl"] = "require" if sslmode == "prefer" else sslmode
    elif url.host and url.host.endswith(".neon.tech"):
        connect_args["ssl"] = "require"
    return url, connect_args


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required for protected API routes")
    url, connect_args = _async_database_url(settings.DATABASE_URL)
    return create_async_engine(url, pool_pre_ping=True, connect_args=connect_args)


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    try:
        factory = get_session_factory()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    async with factory() as session:
        yield session