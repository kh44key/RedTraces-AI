"""Unified, local-first API for normalized CTI findings.

Collectors can submit Telegram, X, forum, or web-monitor records to one
analyst-facing store without exposing their database credentials to the UI.
Run with: uvicorn unified_cti_api:app --host 127.0.0.1 --port 8100
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Float, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from pkcert_config import get_secret


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


DATABASE_URL = get_secret("UNIFIED_CTI_DATABASE_URL", "sqlite:///unified_cti.db")
API_KEY = get_secret("UNIFIED_CTI_API_KEY")
engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


class Finding(Base):
    __tablename__ = "unified_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    source_name: Mapped[str] = mapped_column(String(255), index=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    observables: Mapped[str] = mapped_column(Text, default="[]")
    entities: Mapped[str] = mapped_column(Text, default="[]")
    severity: Mapped[str] = mapped_column(String(16), default="medium", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=50.0)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class FindingIn(BaseModel):
    source_type: Literal["web", "telegram", "x", "forum", "manual"]
    source_name: str = Field(min_length=1, max_length=255)
    source_url: str | None = Field(default=None, max_length=2048)
    external_id: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, max_length=500)
    content: str = Field(min_length=1)
    observables: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    severity: Literal["critical", "high", "medium", "low", "unknown"] = "medium"
    confidence: float = Field(default=50.0, ge=0, le=100)
    occurred_at: datetime | None = None


class FindingOut(FindingIn):
    id: int
    ingested_at: datetime


def _fingerprint(item: FindingIn) -> str:
    identity = item.external_id or item.source_url or item.content
    raw = f"{item.source_type}|{item.source_name}|{identity}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _serialize(row: Finding) -> FindingOut:
    import json

    return FindingOut(
        id=row.id, source_type=row.source_type, source_name=row.source_name,
        source_url=row.source_url, external_id=row.external_id, title=row.title,
        content=row.content, observables=json.loads(row.observables),
        entities=json.loads(row.entities), severity=row.severity,
        confidence=row.confidence, occurred_at=row.occurred_at,
        ingested_at=row.ingested_at,
    )


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """Protect write endpoints; local read-only demo use stays frictionless."""
    if not API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="UNIFIED_CTI_API_KEY is not configured; write API is disabled.",
        )
    if not x_api_key or not __import__("hmac").compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


app = FastAPI(title="Unified CTI API", version="1.0.0")


@app.on_event("startup")
def initialize_database() -> None:
    Base.metadata.create_all(engine)


@app.get("/api/v1/health")
def health() -> dict[str, str | bool]:
    return {"service": "unified-cti-api", "status": "ok", "write_api_configured": bool(API_KEY)}


@app.post("/api/v1/findings", response_model=FindingOut, status_code=status.HTTP_201_CREATED,
          dependencies=[Depends(require_api_key)])
def ingest_finding(item: FindingIn) -> FindingOut:
    import json

    fingerprint = _fingerprint(item)
    with SessionLocal() as session:
        existing = session.scalar(select(Finding).where(Finding.fingerprint == fingerprint))
        if existing:
            return _serialize(existing)
        row = Finding(fingerprint=fingerprint, **item.model_dump())
        row.observables = json.dumps(item.observables)
        row.entities = json.dumps(item.entities)
        session.add(row)
        session.commit()
        session.refresh(row)
        return _serialize(row)


@app.get("/api/v1/findings", response_model=list[FindingOut])
def list_findings(
    source_type: str | None = None,
    severity: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[FindingOut]:
    with SessionLocal() as session:
        query = select(Finding).order_by(Finding.ingested_at.desc()).limit(limit)
        if source_type:
            query = query.where(Finding.source_type == source_type)
        if severity:
            query = query.where(Finding.severity == severity)
        return [_serialize(row) for row in session.scalars(query)]

