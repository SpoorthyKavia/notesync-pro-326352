from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.core.settings import settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.postgres_url,
            pool_pre_ping=True,
        )
    return _engine


def _get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(bind=_get_engine(), expire_on_commit=False, class_=AsyncSession)
    return _sessionmaker


# PUBLIC_INTERFACE
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an AsyncSession.

    Contract:
    - Inputs: none (engine configured via Settings).
    - Outputs: AsyncSession that is closed after request.
    - Errors: surfaces DB connectivity errors to caller.
    - Side-effects: opens/closes DB connection(s) from pool.
    """
    session_factory = _get_sessionmaker()
    async with session_factory() as session:
        yield session
