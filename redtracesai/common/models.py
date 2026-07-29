"""Database models shared by collectors and the API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


class CollectedMessage(Base):
    """A message collected from one of the supported platforms."""

    __tablename__ = "collected_messages"
    __table_args__ = (
        CheckConstraint(
            "platform IN "
            "('telegram', 'discord', 'reddit', 'darkweb', 'autodiscovery')",
            name="ck_collected_messages_platform",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(String(512), nullable=True)
    url: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # "metadata" is reserved by SQLAlchemy's declarative API, so the Python
    # attribute is metadata_ while the PostgreSQL column remains "metadata".
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    attachments: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
