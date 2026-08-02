"""
RekanVault Storage Database Engine & Session Provider
SQLAlchemy 2.x Async Engine & Connection Pool Management.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from apps.api.config import settings


def get_async_engine(db_url: str | None = None) -> AsyncEngine:
    """Create and return an async SQLAlchemy engine."""
    url = db_url or settings.RV_DATABASE_URL
    return create_async_engine(
        url,
        pool_size=settings.RV_DATABASE_POOL_MIN_SIZE,
        max_overflow=settings.RV_DATABASE_POOL_MAX_SIZE - settings.RV_DATABASE_POOL_MIN_SIZE,
        echo=settings.RV_ENV == "development",
        future=True,
    )


_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(db_url: str | None = None) -> None:
    """Initialize global database engine and session factory."""
    global _engine, _async_session_factory
    _engine = get_async_engine(db_url)
    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency provider yielding async database sessions."""
    if _async_session_factory is None:
        init_db()
    assert _async_session_factory is not None
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
