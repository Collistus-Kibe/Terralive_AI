import ssl

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from core.config import settings

# Engine and session factory are created lazily at startup so that
# importing this module never fails when TIDB_URL is not yet configured.
engine = None
AsyncSessionLocal = None


def init_db_engine() -> None:
    """Initialise the async engine and session factory (called at startup)."""
    global engine, AsyncSessionLocal

    # TiDB Cloud requires TLS — pass a real SSLContext via connect_args
    ssl_ctx = ssl.create_default_context()
    engine = create_async_engine(
        settings.TIDB_URL,
        echo=True,
        connect_args={"ssl": ssl_ctx},
        pool_recycle=300,       # Recycle connections every 5 min (TiDB drops idle ones)
        pool_pre_ping=True,     # Test connection before use — auto-reconnect stale ones
        pool_size=5,
        max_overflow=10,
    )
    AsyncSessionLocal = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_db():
    """FastAPI dependency that yields an async database session."""
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialised – call init_db_engine() first.")
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_session() -> AsyncSession:
    """
    Return a standalone async session for use outside the FastAPI request
    lifecycle (e.g. inside WebSocket tool-call handlers).

    Usage::

        async with get_session() as session:
            result = await session.execute(...)
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialised – call init_db_engine() first.")
    return AsyncSessionLocal()
