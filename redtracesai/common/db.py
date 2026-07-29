"""Async SQLAlchemy database configuration."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import text
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
    """Create tables and apply the small pre-Alembic schema compatibility fix."""
    async with engine.begin() as connection:
        # Multiple Compose services may initialize concurrently. The transaction
        # advisory lock serializes this temporary create_all-based migration.
        await connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('redtracesai:init_db'))")
        )
        await connection.run_sync(Base.metadata.create_all)
        constraint_definition = await connection.scalar(
            text(
                """
                SELECT pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conname = 'ck_collected_messages_platform'
                  AND conrelid = 'collected_messages'::regclass
                """
            )
        )
        if constraint_definition and (
            "'discord'" not in constraint_definition
            or "'autodiscovery'" not in constraint_definition
        ):
            await connection.execute(
                text(
                    "ALTER TABLE collected_messages "
                    "DROP CONSTRAINT ck_collected_messages_platform"
                )
            )
            await connection.execute(
                text(
                    """
                    ALTER TABLE collected_messages
                    ADD CONSTRAINT ck_collected_messages_platform
                    CHECK (
                        platform IN (
                            'telegram',
                            'discord',
                            'reddit',
                            'darkweb',
                            'autodiscovery'
                        )
                    )
                    """
                )
            )
