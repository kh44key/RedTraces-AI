"""Async SQLAlchemy database configuration."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from common.models import Base


load_dotenv()
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://redtraces:redtraces@localhost:5432/redtracesai",
)

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create tables that do not already exist."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
