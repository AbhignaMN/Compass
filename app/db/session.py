"""Async SQLAlchemy engine and session helpers with Neon/Render SSL normalization."""

import ssl
from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


def normalize_database_url(raw_url: str) -> tuple[str, dict[str, Any]]:
    """Normalize postgres/postgresql URLs for asyncpg and extract SSL connect_args."""
    url = raw_url.strip()
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]

    parts = urlsplit(url)
    query_params = dict(parse_qsl(parts.query, keep_blank_values=True))
    connect_args: dict[str, Any] = {}

    sslmode = query_params.pop("sslmode", None)
    # asyncpg does not accept libpq's channel_binding query param
    query_params.pop("channel_binding", None)

    if sslmode in {"require", "verify-ca", "verify-full"}:
        connect_args["ssl"] = ssl.create_default_context()
    elif sslmode == "disable":
        connect_args["ssl"] = False

    clean_url = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query_params), parts.fragment)
    )
    return clean_url, connect_args


def build_engine(database_url: str | None = None) -> AsyncEngine:
    settings = get_settings()
    url, connect_args = normalize_database_url(database_url or settings.database_url)
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args=connect_args,
    )


engine = build_engine()
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
