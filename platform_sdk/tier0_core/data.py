"""
platform_sdk.tier0_core.data
──────────────────────────────
Typed ORM access, DB connection lifecycle, transaction boundaries,
query safety, and migration helpers.

Minimal stack: SQLAlchemy 2.x async + Alembic
Configure via: DATABASE_URL
"""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


# ── Base model ────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """All ORM models inherit from this base."""
    pass


# ── Engine / session factory ──────────────────────────────────────────────────

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the singleton async engine. Created on first call."""
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")
        pool_size = int(os.environ.get("DATABASE_POOL_SIZE", "5"))
        max_overflow = int(os.environ.get("DATABASE_MAX_OVERFLOW", "10"))

        kwargs: dict[str, Any] = {"echo": os.getenv("DATABASE_ECHO", "").lower() == "true"}

        # SQLite doesn't support pool settings
        if not url.startswith("sqlite"):
            kwargs["pool_size"] = pool_size
            kwargs["max_overflow"] = max_overflow

        _engine = create_async_engine(url, **kwargs)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that yields a transactional session.
    Commits on clean exit, rolls back on exception, always closes.

    Usage:
        async with get_session() as session:
            result = await session.execute(select(User).where(User.id == uid))
            user = result.scalar_one_or_none()
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def dispose_engine() -> None:
    """Dispose the engine — call on application shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def _reset() -> None:
    """For tests — reset engine and session factory."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None
