"""
app/core/database.py
────────────────────
Async SQLAlchemy engine + session factory.

Why async?
  FastAPI is fully async. Using an async engine means database I/O never
  blocks the event loop, so the server can handle many concurrent users
  on a single process.

Switching to PostgreSQL later:
  Change DATABASE_URL in .env from sqlite+aiosqlite:// to postgresql+asyncpg://
  and run `alembic upgrade head`. No Python code changes needed.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────────────
# echo=True logs every SQL statement — turn off in production.
# check_same_thread=False is SQLite-specific; async driver handles threading itself.
engine = create_async_engine(
    settings.database_url,
    echo=(settings.app_env == "development"),
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

# ── Session factory ───────────────────────────────────────────────────────────
# expire_on_commit=False: objects remain usable after commit (needed in async).
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# ── Base class for all ORM models ─────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncSession:
    """
    Yields a database session for one request, then closes it.
    Use with FastAPI's Depends():  db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()      # Auto-commit on clean exit
        except Exception:
            await session.rollback()    # Roll back on any exception
            raise


# ── Startup helper ────────────────────────────────────────────────────────────
async def create_all_tables():
    """
    Called on app startup to create tables that don't exist yet.
    In production, prefer Alembic migrations over this.
    """
    async with engine.begin() as conn:
        from app.models import user, progress   # noqa: import triggers registration
        await conn.run_sync(Base.metadata.create_all)
