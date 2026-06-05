"""
DocuMind 2.0 — Database Setup
SQLAlchemy async engine + session factory + Base model.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# ── Async Engine ───────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

# ── Session Factory ────────────────────────────────────────────
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Base Model ─────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""
    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps to models."""
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


def generate_uuid() -> str:
    """Generate a new UUID4 string for primary keys."""
    return str(uuid.uuid4())


# ── Dependency ─────────────────────────────────────────────────
async def get_db() -> AsyncSession:
    """FastAPI dependency that provides an async database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Table Creation ─────────────────────────────────────────────
async def create_all_tables():
    """Create all database tables. Called at application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables():
    """Drop all database tables. Used in testing only."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
